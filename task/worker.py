"""Task worker: orchestrates tasks from Redis by running each unit of work in-process (no subprocess)."""

import json
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Dict

import redis

from task.config import Config
from task.redis_updates import update_task_status
from task.run_task import (
    run_evaluation,
    run_recommendation,
    run_training,
    run_verification,
)

# Configure logging (LOG_LEVEL env: DEBUG, INFO, WARNING, ERROR; default INFO)
# Use DEBUG to see verify_card and level-detection details.
_log_level_name = (os.environ.get("LOG_LEVEL") or "INFO").upper()
_log_level = getattr(logging, _log_level_name, logging.INFO)


class FlushingStreamHandler(logging.StreamHandler):
    """StreamHandler that flushes after each emit so docker logs show output immediately."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


def _configure_logging() -> None:
    root = logging.getLogger()
    if not root.handlers:
        handler = FlushingStreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        root.addHandler(handler)
        root.setLevel(_log_level)
    logging.getLogger("PIL").setLevel(logging.WARNING)


_configure_logging()
logger = logging.getLogger(__name__)


class TaskWorker:
    """
    Orchestrator that pops from Redis queues and runs each task in-process.
    Logs from training, verification, and evaluation are visible in the worker process.
    """

    QUEUE_NAME = "recommendation_tasks"
    CURRENT_TASK_KEY = "recommendation_current_task_id"
    TRAINING_QUEUE_NAME = "training_tasks"
    TRAINING_CURRENT_TASK_KEY = "training_current_task_id"
    EVALUATION_QUEUE_NAME = "evaluation_tasks"
    VERIFICATION_QUEUE_NAME = "verification_tasks"
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
            decode_responses=True,
        )
        self.running = False
        self._repo_root = Path(__file__).resolve().parent.parent

    def _clear_current_task(self, current_key: str) -> None:
        """Clear the current-processing task id in Redis."""
        try:
            self.redis_client.delete(current_key)
        except Exception as e:
            logger.warning("Failed to clear current task key: %s", e)

    def process_training_task(self, task_data: Dict) -> None:
        """Orchestrate a training task: run training in-process, drain evaluation on suspend."""
        task_id = task_data["task_id"]
        model_type = task_data.get("model_type", "box_detector")
        resume_from_existing = task_data.get("resume_from_existing", False)
        if isinstance(resume_from_existing, str):
            resume_from_existing = resume_from_existing.lower() == "true"

        logger.info("Processing training task %s (model_type=%s)", task_id, model_type)

        self.redis_client.setex(
            self.TRAINING_CURRENT_TASK_KEY,
            self.CURRENT_TASK_EXPIRY,
            task_id,
        )
        self.redis_client.hset(
            f"task:{task_id}:meta",
            mapping={"status": "processing", "task_type": "training"},
        )

        payload = {
            "task_id": task_id,
            "model_type": model_type,
            "resume_from_existing": resume_from_existing,
            "resume_from_epoch": None,
        }
        if task_data.get("training_epochs") is not None:
            payload["training_epochs"] = task_data["training_epochs"]
        if task_data.get("initial_learning_rate") is not None:
            payload["initial_learning_rate"] = task_data["initial_learning_rate"]

        while True:
            result = run_training(self.redis_client, self.config, payload)
            if result.get("suspended"):
                next_epoch = result.get("next_epoch", 1)
                eval_queue_len = self.redis_client.llen(self.EVALUATION_QUEUE_NAME)
                logger.info(
                    "Training suspended at epoch %d to process %d pending evaluation task(s); will resume after.",
                    next_epoch - 1,
                    eval_queue_len,
                )
                while self.redis_client.llen(self.EVALUATION_QUEUE_NAME) > 0:
                    task_data_str = self.redis_client.brpop(
                        self.EVALUATION_QUEUE_NAME,
                        timeout=int(self.POLL_INTERVAL),
                    )
                    if task_data_str:
                        _qn, data = task_data_str
                        eval_payload = json.loads(data)
                        run_evaluation(self.redis_client, self.config, eval_payload)
                logger.info("Resuming training from epoch %d after evaluation drain.", next_epoch)
                payload["resume_from_epoch"] = next_epoch
                payload["resume_from_existing"] = True
                continue

            self._clear_current_task(self.TRAINING_CURRENT_TASK_KEY)
            logger.info("Completed training task %s", task_id)
            return

    def process_verification_task(self, task_data: Dict) -> None:
        """Run one verification task in-process (loads icon/digit models)."""
        try:
            run_verification(self.redis_client, self.config, task_data)
        except Exception:
            logger.exception("Verification task failed")
            task_id = task_data.get("task_id", "")
            update_task_status(
                self.redis_client,
                task_id,
                "failed",
                error="Verification raised an exception (check worker logs)",
            )

    def process_task(self, task_data: Dict) -> None:
        """Orchestrate a recommendation task: run in-process, then clear current key."""
        run_recommendation(self.redis_client, self.config, task_data)

    def _long_running_loop(self) -> None:
        """Single thread: pop one training, verification, or recommendation task at a time, run in-process."""
        while self.running:
            try:
                task_data_str = self.redis_client.brpop(
                    [
                        self.TRAINING_QUEUE_NAME,
                        self.VERIFICATION_QUEUE_NAME,
                        self.QUEUE_NAME,
                    ],
                    timeout=int(self.POLL_INTERVAL),
                )
                if not task_data_str:
                    continue
                queue_name, data = task_data_str
                task_data = json.loads(data)
                task_id = task_data.get("task_id", "?")
                logger.info("Popped task from %s (task_id=%s)", queue_name, task_id)
                if queue_name == self.TRAINING_QUEUE_NAME:
                    self.process_training_task(task_data)
                elif queue_name == self.VERIFICATION_QUEUE_NAME:
                    self.process_verification_task(task_data)
                else:
                    self.process_task(task_data)
                logger.debug("Finished task %s from %s", task_id, queue_name)
            except redis.ConnectionError as e:
                logger.error("Long-running slot Redis error: %s", e)
                time.sleep(5)
            except Exception:
                logger.exception("Unexpected error in long-running slot")
                time.sleep(1)

    def run(self) -> None:
        """Run the worker: pop from queues and run each task in-process."""
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
    logger.info("Worker process starting (in-process task execution)")
    worker = TaskWorker()
    worker.run()


if __name__ == "__main__":
    main()
