"""Task worker for processing recommendation tasks from Redis."""

import json
import logging
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Optional

import redis
from task.config import Config
from task.processors.recommendation_processor import RecommendationProcessor
from task.processors.box_detector_processor import (
    BoxDetectorProcessor,
    _build_arrays,
    _compute_test_metrics,
    _labeled_dirs,
    _scan_sources,
    _split_train_test,
)
from task.processors.evaluation_processor import (
    _load_box_detector_model as load_box_detector_with_format,
    build_preview_items,
    run_evaluate as eval_run_evaluate,
    run_preview as eval_run_preview,
)
from shared.recommendation_engine import TaskCancelledError

EVAL_INTERVAL_SEC = 10
EVAL_THREAD_JOIN_TIMEOUT_SEC = 15
LATEST_PREVIEW_KEY = "extract:training:latest_preview"
PREVIEW_TTL = 3600

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TaskWorker:
    """
    Worker that processes tasks from Redis queues.
    One long-running slot (training or recommendation, mutually exclusive) plus
    a pool of evaluation workers that run in parallel.
    """

    QUEUE_NAME = "recommendation_tasks"
    CURRENT_TASK_KEY = "recommendation_current_task_id"
    TRAINING_QUEUE_NAME = "training_tasks"
    TRAINING_CURRENT_TASK_KEY = "training_current_task_id"
    EVALUATION_QUEUE_NAME = "evaluation_tasks"
    CURRENT_TASK_EXPIRY = 3600  # seconds (clears if worker dies)
    POLL_INTERVAL = 1.0  # seconds

    def __init__(self):
        """Initialize task worker."""
        self.config = Config()
        self.redis_client = redis.Redis(
            host=self.config.REDIS_HOST,
            port=self.config.REDIS_PORT,
            db=self.config.REDIS_DB,
            password=self.config.REDIS_PASSWORD,
            decode_responses=True
        )
        self.processor = RecommendationProcessor(self.config.DATA_FILE_PATH)
        self.training_processor = BoxDetectorProcessor(
            data_dir=self.config.DATA_DIR,
            model_path=self.config.BOX_DETECTOR_MODEL_PATH,
            test_ratio=self.config.BOX_DETECTOR_TEST_RATIO,
            epochs=self.config.TRAINING_EPOCHS,
            augment_shift_regular=self.config.augment_shifts_regular,
            augment_shift_blueprint=self.config.augment_shifts_blueprint,
            augment_fill=self.config.EXTRACT_AUGMENT_FILL,
            augment_count=self.config.EXTRACT_AUGMENT_COUNT,
            test_blueprint_fraction=self.config.BOX_DETECTOR_TEST_BLUEPRINT_FRACTION,
            scale_regular=self.config.EXTRACT_REGULAR_SCALE,
            scale_blueprint=self.config.EXTRACT_BLUEPRINT_SCALE,
        )
        self.running = False

    def update_task_status(
        self,
        task_id: str,
        status: str,
        results: Optional[Dict] = None,
        error: Optional[str] = None
    ) -> None:
        """
        Update task status in Redis.

        Args:
            task_id: Task ID
            status: New status (processing, completed, failed)
            results: Results dictionary (if completed)
            error: Error message (if failed)
        """
        meta_key = f"task:{task_id}:meta"
        result_key = f"task:{task_id}:result"
        error_key = f"task:{task_id}:error"

        # Update metadata
        updates = {
            "status": status,
        }
        self.redis_client.hset(meta_key, mapping=updates)

        # Store results or error
        if status == "completed" and results:
            self.redis_client.setex(
                result_key,
                3600,  # 1 hour expiry
                json.dumps(results)
            )
        elif status in ("failed", "cancelled") and error:
            self.redis_client.setex(
                error_key,
                3600,  # 1 hour expiry
                error
            )

    def update_task_progress(
        self,
        task_id: str,
        evaluated: int,
        total_planned: int,
        partial_results: Optional[Dict] = None
    ) -> None:
        """
        Update task progress and optionally partial results in Redis.
        Does not change status (task remains "processing").

        Args:
            task_id: Task ID
            evaluated: Number of combinations evaluated so far
            total_planned: Total number of combinations to evaluate
            partial_results: Optional {"recommendations": [...], "count": N}
        """
        meta_key = f"task:{task_id}:meta"
        result_key = f"task:{task_id}:result"

        self.redis_client.hset(meta_key, mapping={
            "evaluated": str(evaluated),
            "total_planned": str(total_planned),
        })

        if partial_results is not None:
            self.redis_client.setex(
                result_key,
                3600,
                json.dumps(partial_results)
            )

    def _clear_current_task(self, current_key: str) -> None:
        """Clear the current-processing task id in Redis."""
        try:
            self.redis_client.delete(current_key)
        except Exception as e:
            logger.warning(f"Failed to clear current task key: {e}")

    def _eval_loop(
        self,
        stop_event: threading.Event,
        task_id: str,
        repo_root: Path,
    ) -> None:
        """Background thread: every 10s load current model and write test metrics to Redis."""
        config = self.config
        # Match processor: checkpoint under DATA_DIR/models/box_detector
        data_dir = repo_root / config.DATA_DIR
        model_dir = data_dir / "models" / "box_detector"
        stem = Path(config.BOX_DETECTOR_MODEL_PATH).name
        if stem.endswith(".keras") or stem.endswith(".h5"):
            stem = Path(stem).stem
        current_path = model_dir / (stem + "_current.keras")

        while True:
            if stop_event.wait(timeout=EVAL_INTERVAL_SEC):
                break
            if not current_path.exists():
                continue
            try:
                model, _ = load_box_detector_with_format(current_path)
            except Exception as e:
                logger.debug("Eval thread skip load: %s", e)
                continue
            try:
                labeled = _labeled_dirs(data_dir)
                if not labeled:
                    continue
                sources = _scan_sources(labeled)
                if not sources:
                    continue
                _, test_sources = _split_train_test(
                    sources, config.BOX_DETECTOR_TEST_RATIO
                )
                if not test_sources:
                    continue
                X_test, y_test = _build_arrays(
                    test_sources,
                    augment=True,
                    shift_regular=config.augment_shifts_regular,
                    shift_blueprint=config.augment_shifts_blueprint,
                    fill_mode=config.EXTRACT_AUGMENT_FILL,
                    augment_count=config.EXTRACT_AUGMENT_COUNT,
                )
                metrics = _compute_test_metrics(model, X_test, y_test)
                self.redis_client.setex(
                    f"task:{task_id}:eval",
                    3600,
                    json.dumps(metrics),
                )
                # Only write preview when we've reached a multiple of PREVIEW_EVERY_N_EPOCHS
                evaluated_str = self.redis_client.hget(f"task:{task_id}:meta", "evaluated")
                try:
                    evaluated = int(evaluated_str) if evaluated_str else 0
                except (ValueError, TypeError):
                    evaluated = 0
                last_preview_str = self.redis_client.get(f"task:{task_id}:last_preview_epoch")
                last_preview_epoch = int(last_preview_str) if last_preview_str else -1
                preview_interval = config.PREVIEW_EVERY_N_EPOCHS
                if (
                    evaluated > 0
                    and evaluated % preview_interval == 0
                    and evaluated != last_preview_epoch
                ):
                    try:
                        expected_ms = len(test_sources) * config.PREVIEW_MS_PER_IMAGE
                        self.redis_client.setex(
                            f"task:{task_id}:preview_expected_duration_ms",
                            PREVIEW_TTL,
                            str(expected_ms),
                        )
                        t0 = time.perf_counter()
                        items, sr, sb = build_preview_items(
                            model,
                            test_sources,
                            config.EXTRACT_REGULAR_SCALE,
                            config.EXTRACT_BLUEPRINT_SCALE,
                            config.augment_shifts_regular,
                            config.augment_shifts_blueprint,
                            config.EXTRACT_AUGMENT_FILL,
                            config.EXTRACT_AUGMENT_COUNT,
                        )
                        elapsed_ms = int((time.perf_counter() - t0) * 1000)
                        preview_payload = {"items": items, "scale_regular": sr, "scale_blueprint": sb}
                        preview_json = json.dumps(preview_payload)
                        self.redis_client.setex(f"task:{task_id}:latest_preview", PREVIEW_TTL, preview_json)
                        self.redis_client.setex(LATEST_PREVIEW_KEY, PREVIEW_TTL, preview_json)
                        self.redis_client.setex(f"task:{task_id}:last_preview_epoch", PREVIEW_TTL, str(evaluated))
                        logger.info(
                            "Preview generated in %d ms (%d items)",
                            elapsed_ms,
                            len(items),
                        )
                    except Exception as pe:
                        logger.warning("Eval thread preview failed: %s", pe)
            except Exception as e:
                logger.debug("Eval thread skip: %s", e)

    def process_training_task(self, task_data: Dict) -> None:
        """Process a single training task (e.g. box detector)."""
        task_id = task_data["task_id"]
        model_type = task_data.get("model_type", "box_detector")
        resume_from_existing = task_data.get("resume_from_existing", False)
        if isinstance(resume_from_existing, str):
            resume_from_existing = resume_from_existing.lower() == "true"

        logger.info(f"Processing training task {task_id} (model_type={model_type})")

        self.redis_client.setex(
            self.TRAINING_CURRENT_TASK_KEY,
            self.CURRENT_TASK_EXPIRY,
            task_id
        )
        self.redis_client.hset(
            f"task:{task_id}:meta",
            mapping={"status": "processing", "task_type": "training"}
        )

        def progress_callback(epoch: int, total_epochs: int, metrics: Dict) -> None:
            self.update_task_progress(
                task_id,
                evaluated=epoch,
                total_planned=total_epochs,
                partial_results=metrics
            )

        def check_cancelled() -> bool:
            cancelled = self.redis_client.get(f"task:{task_id}:cancelled")
            return cancelled == "1"

        stop_eval_event = threading.Event()
        eval_thread: Optional[threading.Thread] = None
        repo_root = Path(__file__).resolve().parent.parent

        if model_type == "box_detector":
            eval_thread = threading.Thread(
                target=self._eval_loop,
                args=(stop_eval_event, task_id, repo_root),
                daemon=False,
            )
            eval_thread.start()

        try:
            if model_type == "box_detector":
                results = self.training_processor.process(
                    task_id=task_id,
                    progress_callback=progress_callback,
                    check_cancelled=check_cancelled,
                    resume_from_existing=resume_from_existing,
                )
            else:
                self._clear_current_task(self.TRAINING_CURRENT_TASK_KEY)
                self.update_task_status(
                    task_id, "failed",
                    error=f"Unknown model_type: {model_type}"
                )
                return

            if "error" in results:
                self._clear_current_task(self.TRAINING_CURRENT_TASK_KEY)
                self.update_task_status(
                    task_id, "failed",
                    error=results.get("message", results.get("error", "Unknown error"))
                )
                return

            data_dir = repo_root / self.config.DATA_DIR
            logger.info("Running completion preview (data_dir=%s)", data_dir)
            t0 = time.perf_counter()
            preview_result = eval_run_preview(
                data_dir,
                self.config.BOX_DETECTOR_TEST_RATIO,
                self.config.augment_shifts_regular,
                self.config.augment_shifts_blueprint,
                self.config.EXTRACT_AUGMENT_FILL,
                self.config.EXTRACT_AUGMENT_COUNT,
                self.config.EXTRACT_REGULAR_SCALE,
                self.config.EXTRACT_BLUEPRINT_SCALE,
                self.config.BOX_DETECTOR_TEST_BLUEPRINT_FRACTION,
            )
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            if "error" not in preview_result:
                preview_payload = {
                    "items": preview_result["items"],
                    "scale_regular": preview_result["scale_regular"],
                    "scale_blueprint": preview_result["scale_blueprint"],
                }
                preview_json = json.dumps(preview_payload)
                self.redis_client.setex(f"task:{task_id}:latest_preview", PREVIEW_TTL, preview_json)
                self.redis_client.setex(LATEST_PREVIEW_KEY, PREVIEW_TTL, preview_json)
                logger.info(
                    "Completion preview generated in %d ms (%d items)",
                    elapsed_ms,
                    len(preview_result["items"]),
                )
            else:
                logger.warning(
                    "Completion preview not written: %s",
                    preview_result.get("message", preview_result.get("error", "unknown")),
                )

            self._clear_current_task(self.TRAINING_CURRENT_TASK_KEY)
            self.update_task_status(task_id, "completed", results=results)
            logger.info(f"Completed training task {task_id}")

        except TaskCancelledError:
            self._clear_current_task(self.TRAINING_CURRENT_TASK_KEY)
            self.update_task_status(
                task_id, "cancelled",
                error="Training cancelled"
            )
            logger.info(f"Training task {task_id} was cancelled")

        except Exception as e:
            self._clear_current_task(self.TRAINING_CURRENT_TASK_KEY)
            error_msg = str(e)
            logger.error(f"Failed to process training task {task_id}: {error_msg}")
            self.update_task_status(task_id, "failed", error=error_msg)

        finally:
            if eval_thread is not None:
                stop_eval_event.set()
                eval_thread.join(timeout=EVAL_THREAD_JOIN_TIMEOUT_SEC)
                if eval_thread.is_alive():
                    logger.warning("Eval thread did not stop within timeout")

    def process_task(self, task_data: Dict) -> None:
        """
        Process a single task. Only one task runs at a time; if this task was
        cancelled (a new task was started), status is set to cancelled.
        """
        task_id = task_data["task_id"]
        weights = json.loads(task_data["weights"])
        constraints = json.loads(task_data["constraints"])
        limit = int(task_data["limit"])

        logger.info(f"Processing task {task_id}")

        # Claim as the current recommendation task (so API can cancel it when a new one is created)
        self.redis_client.setex(
            self.CURRENT_TASK_KEY,
            self.CURRENT_TASK_EXPIRY,
            task_id
        )

        # Update status to processing
        self.update_task_status(task_id, "processing")

        def progress_callback(
            evaluated: int,
            total_planned: int,
            partial_results: Optional[Dict]
        ) -> None:
            self.update_task_progress(
                task_id,
                evaluated=evaluated,
                total_planned=total_planned,
                partial_results=partial_results
            )

        def check_cancelled() -> bool:
            cancelled = self.redis_client.get(f"task:{task_id}:cancelled")
            return cancelled == "1"

        try:
            results = self.processor.process(
                weights=weights,
                constraints=constraints,
                limit=limit,
                progress_callback=progress_callback,
                check_cancelled=check_cancelled
            )

            self._clear_current_task(self.CURRENT_TASK_KEY)
            self.update_task_status(task_id, "completed", results=results)
            logger.info(f"Completed task {task_id}")

        except TaskCancelledError:
            self._clear_current_task(self.CURRENT_TASK_KEY)
            self.update_task_status(task_id, "cancelled", error="Cancelled (a new task was started)")
            logger.info(f"Task {task_id} was cancelled")

        except Exception as e:
            self._clear_current_task(self.CURRENT_TASK_KEY)
            error_msg = str(e)
            logger.error(f"Failed to process task {task_id}: {error_msg}")
            self.update_task_status(task_id, "failed", error=error_msg)

    def process_evaluation_task(self, task_data: Dict) -> None:
        """Process a single evaluation task (evaluate or preview)."""
        task_id = task_data["task_id"]
        eval_type = task_data.get("type", "evaluate")

        logger.info("Processing evaluation task %s (type=%s)", task_id, eval_type)

        self.redis_client.hset(
            f"task:{task_id}:meta",
            mapping={"status": "processing", "task_type": "evaluation"}
        )

        repo_root = Path(__file__).resolve().parent.parent
        data_dir = (repo_root / self.config.DATA_DIR).resolve()

        try:
            if eval_type == "evaluate":
                result = eval_run_evaluate(
                    data_dir=data_dir,
                    test_ratio=self.config.BOX_DETECTOR_TEST_RATIO,
                    shift_regular=self.config.augment_shifts_regular,
                    shift_blueprint=self.config.augment_shifts_blueprint,
                    fill_mode=self.config.EXTRACT_AUGMENT_FILL,
                    augment_count=self.config.EXTRACT_AUGMENT_COUNT,
                    test_blueprint_fraction=self.config.BOX_DETECTOR_TEST_BLUEPRINT_FRACTION,
                )
            elif eval_type == "preview":
                result = eval_run_preview(
                    data_dir=data_dir,
                    test_ratio=self.config.BOX_DETECTOR_TEST_RATIO,
                    shift_regular=self.config.augment_shifts_regular,
                    shift_blueprint=self.config.augment_shifts_blueprint,
                    fill_mode=self.config.EXTRACT_AUGMENT_FILL,
                    augment_count=self.config.EXTRACT_AUGMENT_COUNT,
                    scale_regular=self.config.EXTRACT_REGULAR_SCALE,
                    scale_blueprint=self.config.EXTRACT_BLUEPRINT_SCALE,
                    test_blueprint_fraction=self.config.BOX_DETECTOR_TEST_BLUEPRINT_FRACTION,
                )
            else:
                self.update_task_status(
                    task_id, "failed",
                    error=f"Unknown evaluation type: {eval_type}",
                )
                return

            if "error" in result:
                self.update_task_status(
                    task_id, "failed",
                    error=result.get("message", result.get("error", "Unknown error")),
                )
                return

            # Store model_format in Redis for get_task_status to expose
            model_format = result.pop("model_format", None)
            if model_format is not None:
                self.redis_client.setex(
                    f"task:{task_id}:model_format",
                    self.CURRENT_TASK_EXPIRY,
                    model_format,
                )
            self.update_task_status(task_id, "completed", results=result)
            logger.info("Completed evaluation task %s", task_id)

        except Exception as e:
            error_msg = str(e)
            logger.exception("Failed to process evaluation task %s", task_id)
            self.update_task_status(task_id, "failed", error=error_msg)

    def _long_running_loop(self) -> None:
        """Single thread: process one training or one recommendation at a time."""
        while self.running:
            try:
                task_data_str = self.redis_client.brpop(
                    [self.TRAINING_QUEUE_NAME, self.QUEUE_NAME],
                    timeout=int(self.POLL_INTERVAL),
                )
                if not task_data_str:
                    continue
                queue_name, data = task_data_str
                task_data = json.loads(data)
                if queue_name == self.TRAINING_QUEUE_NAME:
                    self.process_training_task(task_data)
                else:
                    self.process_task(task_data)
            except redis.ConnectionError as e:
                logger.error("Long-running slot Redis error: %s", e)
                time.sleep(5)
            except Exception as e:
                logger.error("Unexpected error in long-running slot: %s", e)
                time.sleep(1)

    def _evaluation_worker_loop(self) -> None:
        """One of N threads: process evaluation tasks from evaluation_tasks queue."""
        while self.running:
            try:
                task_data_str = self.redis_client.brpop(
                    self.EVALUATION_QUEUE_NAME,
                    timeout=int(self.POLL_INTERVAL),
                )
                if not task_data_str:
                    continue
                _queue_name, data = task_data_str
                task_data = json.loads(data)
                self.process_evaluation_task(task_data)
            except redis.ConnectionError as e:
                logger.error("Evaluation worker Redis error: %s", e)
                time.sleep(5)
            except Exception as e:
                logger.error("Unexpected error in evaluation worker: %s", e)
                time.sleep(1)

    def run(self) -> None:
        """Run the worker: one long-running slot thread + evaluation worker pool."""
        logger.info("Starting task worker...")
        logger.info("Connecting to Redis at %s:%s", self.config.REDIS_HOST, self.config.REDIS_PORT)

        try:
            self.redis_client.ping()
            logger.info("Connected to Redis")
        except redis.ConnectionError as e:
            logger.error("Failed to connect to Redis: %s", e)
            sys.exit(1)

        self.running = True

        def signal_handler(sig, frame):
            logger.info("Received shutdown signal, stopping worker...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Long-running slot: one thread for training or recommendation
        long_run_thread = threading.Thread(target=self._long_running_loop, daemon=False)
        long_run_thread.start()

        # Evaluation pool: N threads for evaluate/preview tasks
        eval_count = self.config.EVALUATION_WORKER_COUNT
        logger.info("Starting %d evaluation worker(s)", eval_count)
        eval_threads = [
            threading.Thread(target=self._evaluation_worker_loop, daemon=False)
            for _ in range(eval_count)
        ]
        for t in eval_threads:
            t.start()

        long_run_thread.join()
        for t in eval_threads:
            t.join()

        logger.info("Task worker stopped")


def main():
    """Main entry point for the worker."""
    worker = TaskWorker()
    worker.run()


if __name__ == "__main__":
    main()
