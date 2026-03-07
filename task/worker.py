"""Task worker for processing recommendation tasks from Redis."""

import json
import logging
import signal
import sys
import time
from typing import Dict, Optional

import redis
from task.config import Config
from task.processors.recommendation_processor import RecommendationProcessor
from shared.recommendation_engine import TaskCancelledError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TaskWorker:
    """Worker that processes tasks from Redis queue. Only one task runs at a time."""

    QUEUE_NAME = "recommendation_tasks"
    CURRENT_TASK_KEY = "recommendation_current_task_id"
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

    def _clear_current_task(self) -> None:
        """Clear the current-processing task id in Redis."""
        try:
            self.redis_client.delete(self.CURRENT_TASK_KEY)
        except Exception as e:
            logger.warning(f"Failed to clear current task key: {e}")

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

        # Claim as the current processing task (so API can cancel it when a new one is created)
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

            self._clear_current_task()
            self.update_task_status(task_id, "completed", results=results)
            logger.info(f"Completed task {task_id}")

        except TaskCancelledError:
            self._clear_current_task()
            self.update_task_status(task_id, "cancelled", error="Cancelled (a new task was started)")
            logger.info(f"Task {task_id} was cancelled")

        except Exception as e:
            self._clear_current_task()
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

        # Main loop
        while self.running:
            try:
                # Blocking pop from queue (wait up to POLL_INTERVAL seconds)
                task_data_str = self.redis_client.brpop(
                    self.QUEUE_NAME,
                    timeout=int(self.POLL_INTERVAL)
                )

                if task_data_str:
                    # task_data_str is a tuple: (queue_name, data)
                    _, data = task_data_str
                    task_data = json.loads(data)
                    self.process_task(task_data)
                else:
                    # Timeout - continue loop to check if still running
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
