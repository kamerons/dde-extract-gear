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
from shared.recommendation_engine import TaskCancelledError

EVAL_INTERVAL_SEC = 10
EVAL_THREAD_JOIN_TIMEOUT_SEC = 15

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TaskWorker:
    """Worker that processes tasks from Redis queues. Only one task runs at a time."""

    QUEUE_NAME = "recommendation_tasks"
    CURRENT_TASK_KEY = "recommendation_current_task_id"
    TRAINING_QUEUE_NAME = "training_tasks"
    TRAINING_CURRENT_TASK_KEY = "training_current_task_id"
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
            augment_shift_regular=self.config.EXTRACT_AUGMENT_SHIFT_REGULAR,
            augment_shift_blueprint=self.config.EXTRACT_AUGMENT_SHIFT_BLUEPRINT,
            augment_fill=self.config.EXTRACT_AUGMENT_FILL,
            augment_count=self.config.EXTRACT_AUGMENT_COUNT,
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
        from tensorflow import keras

        config = self.config
        # Match processor: current checkpoint is saved with .keras extension
        current_path = repo_root / (config.BOX_DETECTOR_MODEL_PATH + "_current.keras")
        data_dir = repo_root / config.DATA_DIR

        while True:
            if stop_event.wait(timeout=EVAL_INTERVAL_SEC):
                break
            if not current_path.exists():
                continue
            try:
                model = keras.models.load_model(str(current_path))
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
                    augment=False,
                    shift_regular=config.EXTRACT_AUGMENT_SHIFT_REGULAR,
                    shift_blueprint=config.EXTRACT_AUGMENT_SHIFT_BLUEPRINT,
                    fill_mode=config.EXTRACT_AUGMENT_FILL,
                    augment_count=config.EXTRACT_AUGMENT_COUNT,
                )
                metrics = _compute_test_metrics(model, X_test, y_test)
                self.redis_client.setex(
                    f"task:{task_id}:eval",
                    3600,
                    json.dumps(metrics),
                )
            except Exception as e:
                logger.debug("Eval thread skip: %s", e)

    def process_training_task(self, task_data: Dict) -> None:
        """Process a single training task (e.g. box detector)."""
        task_id = task_data["task_id"]
        model_type = task_data.get("model_type", "box_detector")

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

    def run(self) -> None:
        """Run the worker loop."""
        logger.info("Starting task worker...")
        logger.info(f"Connecting to Redis at {self.config.REDIS_HOST}:{self.config.REDIS_PORT}")

        # Test Redis connection
        try:
            self.redis_client.ping()
            logger.info("✓ Connected to Redis")
        except redis.ConnectionError as e:
            logger.error(f"✗ Failed to connect to Redis: {e}")
            sys.exit(1)

        self.running = True

        # Handle shutdown signals
        def signal_handler(sig, frame):
            logger.info("Received shutdown signal, stopping worker...")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Main loop: listen to both training and recommendation queues
        while self.running:
            try:
                task_data_str = self.redis_client.brpop(
                    [self.TRAINING_QUEUE_NAME, self.QUEUE_NAME],
                    timeout=int(self.POLL_INTERVAL)
                )

                if task_data_str:
                    queue_name, data = task_data_str
                    task_data = json.loads(data)
                    if queue_name == self.TRAINING_QUEUE_NAME:
                        self.process_training_task(task_data)
                    else:
                        self.process_task(task_data)
                else:
                    continue

            except redis.ConnectionError as e:
                logger.error(f"Redis connection error: {e}")
                logger.info("Retrying in 5 seconds...")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected error in worker loop: {e}")
                time.sleep(1)

        logger.info("Task worker stopped")


def main():
    """Main entry point for the worker."""
    worker = TaskWorker()
    worker.run()


if __name__ == "__main__":
    main()
