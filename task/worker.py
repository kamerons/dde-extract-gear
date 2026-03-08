"""Task worker for processing recommendation tasks from Redis."""

import gc
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Dict, Optional

import redis
from task.config import Config
from task.processors.recommendation_processor import RecommendationProcessor
from task.processors.box_detector_processor import BoxDetectorProcessor, _clear_keras_session
from task.processors.evaluation_processor import (
    run_evaluate as eval_run_evaluate,
    run_evaluate_all_labeled as eval_run_evaluate_all_labeled,
    run_model_evaluation_combined as eval_run_model_evaluation_combined,
    run_model_results as eval_run_model_results,
    run_preview as eval_run_preview,
)
from shared.recommendation_engine import TaskCancelledError

LATEST_PREVIEW_KEY = "extract:training:latest_preview"
PREVIEW_TTL = 3600

# Configure logging (LOG_LEVEL env: DEBUG, INFO, WARNING, ERROR; default INFO)
_log_level_name = (os.environ.get("LOG_LEVEL") or "INFO").upper()
_log_level = getattr(logging, _log_level_name, logging.INFO)
logging.basicConfig(
    level=_log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Quiet PIL so LOG_LEVEL=DEBUG doesn't flood with PngImagePlugin STREAM messages
logging.getLogger("PIL").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class TaskWorker:
    """
    Worker that processes tasks from Redis queues.
    One long-running thread handles training, recommendation, and evaluation;
    training yields at preview-epoch boundaries when evaluation tasks are pending
    (checkpoint saved, GPU freed, eval run, then training resumes).
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
            preview_every_n_epochs=self.config.PREVIEW_EVERY_N_EPOCHS,
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
            # Write eval metrics to Redis at preview epochs so API can return latest_eval
            if (
                epoch > 0
                and self.config.PREVIEW_EVERY_N_EPOCHS > 0
                and epoch % self.config.PREVIEW_EVERY_N_EPOCHS == 0
            ):
                self.redis_client.setex(
                    f"task:{task_id}:eval",
                    3600,
                    json.dumps(metrics),
                )

        def preview_callback(epoch: int, metrics: Dict, preview_payload: Dict) -> None:
            """Called by processor at preview epochs; write preview to Redis."""
            n_items = len(preview_payload.get("items", []))
            expected_ms = n_items * self.config.PREVIEW_MS_PER_IMAGE
            self.redis_client.setex(
                f"task:{task_id}:preview_expected_duration_ms",
                PREVIEW_TTL,
                str(expected_ms),
            )
            preview_json = json.dumps(preview_payload)
            self.redis_client.setex(f"task:{task_id}:latest_preview", PREVIEW_TTL, preview_json)
            self.redis_client.setex(LATEST_PREVIEW_KEY, PREVIEW_TTL, preview_json)
            self.redis_client.setex(f"task:{task_id}:last_preview_epoch", PREVIEW_TTL, str(epoch))
            logger.info(
                "Preview generated at epoch %d (%d items)",
                epoch,
                n_items,
            )

        def check_cancelled() -> bool:
            cancelled = self.redis_client.get(f"task:{task_id}:cancelled")
            return cancelled == "1"

        def check_pending_evaluation() -> bool:
            return self.redis_client.llen(self.EVALUATION_QUEUE_NAME) > 0

        repo_root = Path(__file__).resolve().parent.parent

        try:
            if model_type == "box_detector":
                resume_epoch = None
                use_resume_existing = resume_from_existing
                while True:
                    results = self.training_processor.process(
                        task_id=task_id,
                        progress_callback=progress_callback,
                        preview_callback=preview_callback,
                        check_cancelled=check_cancelled,
                        resume_from_existing=use_resume_existing,
                        resume_from_epoch=resume_epoch,
                        check_pending_evaluation=check_pending_evaluation,
                    )
                    if results.get("suspended"):
                        current_epoch = results.get("next_epoch", 1) - 1
                        eval_queue_len = self.redis_client.llen(self.EVALUATION_QUEUE_NAME)
                        logger.info(
                            "Stopping training at epoch %d to process %d pending evaluation task(s); "
                            "checkpoint saved. Will resume after evaluation.",
                            current_epoch,
                            eval_queue_len,
                        )
                        eval_tasks_processed = 0
                        while self.redis_client.llen(self.EVALUATION_QUEUE_NAME) > 0:
                            task_data_str = self.redis_client.brpop(
                                self.EVALUATION_QUEUE_NAME,
                                timeout=int(self.POLL_INTERVAL),
                            )
                            if task_data_str:
                                _qn, data = task_data_str
                                self.process_evaluation_task(json.loads(data))
                                eval_tasks_processed += 1
                                logger.debug(
                                    "Processed evaluation task %d of queue; %d left in queue",
                                    eval_tasks_processed,
                                    self.redis_client.llen(self.EVALUATION_QUEUE_NAME),
                                )
                        logger.info(
                            "Clearing Keras session before resuming training (processed %d evaluation task(s))",
                            eval_tasks_processed,
                        )
                        # Clear Keras/TF session so GPU memory is released before we load the
                        # training model; TF's allocator may not fully release after eval cleanup.
                        _clear_keras_session()
                        gc.collect()
                        next_epoch = results.get("next_epoch", 1)
                        logger.info(
                            "Resuming training from epoch %d after processing evaluation task(s).",
                            next_epoch,
                        )
                        resume_epoch = next_epoch
                        use_resume_existing = True
                        continue
                    break
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

            # Use in-process final_preview when present to avoid re-running the test set on GPU
            final_preview = results.get("final_preview")
            if final_preview and isinstance(final_preview, dict) and "items" in final_preview:
                preview_json = json.dumps(final_preview)
                self.redis_client.setex(f"task:{task_id}:latest_preview", PREVIEW_TTL, preview_json)
                self.redis_client.setex(LATEST_PREVIEW_KEY, PREVIEW_TTL, preview_json)
                n_items = len(final_preview.get("items", []))
                logger.info("Completion preview from processor (%d items), skipped eval_run_preview", n_items)
            else:
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

            # Store results without final_preview to avoid duplicating large payload in task result
            results_for_status = {k: v for k, v in results.items() if k != "final_preview"}
            self._clear_current_task(self.TRAINING_CURRENT_TASK_KEY)
            self.update_task_status(task_id, "completed", results=results_for_status)
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
            elif eval_type == "model_evaluation":
                model_id = task_data.get("model_id")
                scope = task_data.get("scope", "all")
                if scope not in ("all", "test"):
                    scope = "all"
                result = eval_run_model_evaluation_combined(
                    data_dir=data_dir,
                    shift_regular=self.config.augment_shifts_regular,
                    shift_blueprint=self.config.augment_shifts_blueprint,
                    fill_mode=self.config.EXTRACT_AUGMENT_FILL,
                    augment_count=self.config.EXTRACT_AUGMENT_COUNT,
                    scale_regular=self.config.EXTRACT_REGULAR_SCALE,
                    scale_blueprint=self.config.EXTRACT_BLUEPRINT_SCALE,
                    test_ratio=self.config.BOX_DETECTOR_TEST_RATIO,
                    test_blueprint_fraction=self.config.BOX_DETECTOR_TEST_BLUEPRINT_FRACTION,
                    model_id=model_id,
                    scope=scope,
                )
                if "error" in result:
                    self.update_task_status(
                        task_id, "failed",
                        error=result.get("message", result.get("error", "Unknown error")),
                    )
                    return
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

    def run(self) -> None:
        """Run the worker: single long-running thread (training, recommendation, and evaluation)."""
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

        self._long_running_loop()
        logger.info("Task worker stopped")


def main():
    """Main entry point for the worker."""
    worker = TaskWorker()
    worker.run()


if __name__ == "__main__":
    main()
