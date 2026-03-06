"""Task worker for processing recommendation tasks from Redis."""

import json
import logging
import signal
import sys
import time
from typing import Dict, Optional

import redis
from armor_select.task.config import Config
from armor_select.task.processors.recommendation_processor import RecommendationProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TaskWorker:
    """Worker that processes tasks from Redis queue."""

    QUEUE_NAME = "recommendation_tasks"
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
        elif status == "failed" and error:
            self.redis_client.setex(
                error_key,
                3600,  # 1 hour expiry
                error
            )

    def process_task(self, task_data: Dict) -> None:
        """
        Process a single task.

        Args:
            task_data: Task data dictionary with task_id, weights, constraints, limit
        """
        task_id = task_data["task_id"]
        weights = json.loads(task_data["weights"])
        constraints = json.loads(task_data["constraints"])
        limit = int(task_data["limit"])

        logger.info(f"Processing task {task_id}")

        # Update status to processing
        self.update_task_status(task_id, "processing")

        try:
            # Process recommendation
            results = self.processor.process(
                weights=weights,
                constraints=constraints,
                limit=limit
            )

            # Update status to completed
            self.update_task_status(task_id, "completed", results=results)
            logger.info(f"Completed task {task_id}")

        except Exception as e:
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
