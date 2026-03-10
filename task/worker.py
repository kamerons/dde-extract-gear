"""Task worker: orchestrates tasks from Redis by running each unit of work in a subprocess."""

import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict

import redis

from task.config import Config
from task.redis_updates import update_task_status

# Configure logging (LOG_LEVEL env: DEBUG, INFO, WARNING, ERROR; default INFO)
_log_level_name = (os.environ.get("LOG_LEVEL") or "INFO").upper()
_log_level = getattr(logging, _log_level_name, logging.INFO)
logging.basicConfig(
    level=_log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logging.getLogger("PIL").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class TaskWorker:
    """
    Orchestrator that pops from Redis queues and runs each task in a separate subprocess.
    One subprocess per unit of work (training run, evaluation task, recommendation task);
    when a subprocess exits, GPU/process memory is fully released.
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

    def _spawn_run_task(self, task_type: str, payload: Dict) -> subprocess.CompletedProcess:
        """Run task.run_task in a subprocess. Returns CompletedProcess with stdout/stderr captured."""
        cmd = [
            sys.executable,
            "-m",
            "task.run_task",
            task_type,
            json.dumps(payload),
        ]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            env=os.environ,
            cwd=str(self._repo_root),
        )

    def process_training_task(self, task_data: Dict) -> None:
        """Orchestrate a training task: run training in subprocess(es), drain evaluation on suspend."""
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
            proc = self._spawn_run_task("training", payload)
            stdout = (proc.stdout or "").strip()
            try:
                result = json.loads(stdout) if stdout else {}
            except json.JSONDecodeError:
                result = {}
                if proc.returncode != 0 and stdout:
                    logger.warning("Training subprocess stdout (not JSON): %s", stdout[:500])

            if proc.returncode != 0 and not result.get("suspended"):
                self._clear_current_task(self.TRAINING_CURRENT_TASK_KEY)
                status = self.redis_client.hget(f"task:{task_id}:meta", "status")
                if status == "processing":
                    error_msg = result.get("message", result.get("error")) or (proc.stderr or "Subprocess failed")[:500]
                    update_task_status(
                        self.redis_client, task_id, "failed", error=error_msg
                    )
                return

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
                        eval_proc = self._spawn_run_task("evaluation", eval_payload)
                        if eval_proc.returncode != 0:
                            logger.warning(
                                "Evaluation subprocess exited with code %s for task %s",
                                eval_proc.returncode,
                                eval_payload.get("task_id"),
                            )
                logger.info("Resuming training from epoch %d after evaluation drain.", next_epoch)
                payload["resume_from_epoch"] = next_epoch
                payload["resume_from_existing"] = True
                continue

            self._clear_current_task(self.TRAINING_CURRENT_TASK_KEY)
            logger.info("Completed training task %s", task_id)
            return

    def process_verification_task(self, task_data: Dict) -> None:
        """Run one verification task in a subprocess (loads icon/digit models on task container)."""
        task_id = task_data.get("task_id", "")
        logger.info("Processing verification task %s", task_id)
        self.redis_client.hset(
            f"task:{task_id}:meta",
            mapping={"status": "processing", "task_type": "verification"},
        )
        proc = self._spawn_run_task("verification", task_data)
        if proc.returncode != 0:
            status = self.redis_client.hget(f"task:{task_id}:meta", "status")
            if status == "processing":
                error_msg = (proc.stderr or "Verification subprocess failed")[:500]
                update_task_status(self.redis_client, task_id, "failed", error=error_msg)

    def process_task(self, task_data: Dict) -> None:
        """Orchestrate a recommendation task: run in subprocess, then clear current key."""
        task_id = task_data["task_id"]
        logger.info("Processing task %s", task_id)

        self.redis_client.setex(
            self.CURRENT_TASK_KEY,
            self.CURRENT_TASK_EXPIRY,
            task_id,
        )
        self.redis_client.hset(
            f"task:{task_id}:meta",
            mapping={"status": "processing"},
        )

        proc = self._spawn_run_task("recommendation", task_data)
        self._clear_current_task(self.CURRENT_TASK_KEY)

        if proc.returncode != 0:
            status = self.redis_client.hget(f"task:{task_id}:meta", "status")
            if status == "processing":
                update_task_status(
                    self.redis_client,
                    task_id,
                    "failed",
                    error=(proc.stderr or "Subprocess failed")[:500],
                )

    def _long_running_loop(self) -> None:
        """Single thread: pop one training, verification, or recommendation task at a time, run in subprocess."""
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
                if queue_name == self.TRAINING_QUEUE_NAME:
                    self.process_training_task(task_data)
                elif queue_name == self.VERIFICATION_QUEUE_NAME:
                    self.process_verification_task(task_data)
                else:
                    self.process_task(task_data)
            except redis.ConnectionError as e:
                logger.error("Long-running slot Redis error: %s", e)
                time.sleep(5)
            except Exception as e:
                logger.error("Unexpected error in long-running slot: %s", e)
                time.sleep(1)

    def run(self) -> None:
        """Run the worker: pop from queues and run each task in a subprocess."""
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
