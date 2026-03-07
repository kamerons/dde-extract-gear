"""Task service for managing recommendation tasks in Redis. Only one task runs at a time."""

import json
import uuid
import logging
from typing import Dict, Optional, Any
from datetime import datetime, timedelta

import redis
from api.config import Config

logger = logging.getLogger(__name__)


class TaskService:
    """Service for managing tasks in Redis."""

    TASK_EXPIRY_SECONDS = 3600  # 1 hour
    CURRENT_TASK_KEY = "recommendation_current_task_id"
    QUEUE_KEY = "recommendation_tasks"
    TRAINING_QUEUE_KEY = "training_tasks"
    TRAINING_CURRENT_TASK_KEY = "training_current_task_id"
    EVALUATION_QUEUE_KEY = "evaluation_tasks"
    LATEST_PREVIEW_KEY = "extract:training:latest_preview"

    def __init__(self):
        """Initialize task service with Redis connection."""
        self.config = Config()
        self.redis_client = redis.Redis(
            host=self.config.REDIS_HOST,
            port=self.config.REDIS_PORT,
            db=self.config.REDIS_DB,
            password=self.config.REDIS_PASSWORD,
            decode_responses=True
        )

    def create_task(
        self,
        weights: Dict[str, float],
        constraints: Dict[str, int],
        limit: int = 10
    ) -> str:
        """
        Create a new recommendation task. Cancels any currently running task and
        clears the queue so only this task runs (one task at a time).

        Args:
            weights: Dictionary mapping stat names to weights
            constraints: Dictionary mapping stat names to minimum values
            limit: Maximum number of recommendations to return

        Returns:
            Task ID (UUID string)
        """
        task_id = str(uuid.uuid4())

        # Cancel the currently processing recommendation task (if any)
        current_id = self.redis_client.get(self.CURRENT_TASK_KEY)
        if current_id:
            self.redis_client.setex(
                f"task:{current_id}:cancelled",
                self.TASK_EXPIRY_SECONDS,
                "1"
            )
            logger.info(f"Cancelled previous recommendation task {current_id} in favour of {task_id}")

        # Clear only the recommendation queue so the new task is next (do not clear training_tasks)
        self.redis_client.delete(self.QUEUE_KEY)

        # Store task metadata
        task_meta = {
            "task_id": task_id,
            "weights": json.dumps(weights),
            "constraints": json.dumps(constraints),
            "limit": limit,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }

        meta_key = f"task:{task_id}:meta"
        self.redis_client.hset(meta_key, mapping=task_meta)
        self.redis_client.expire(meta_key, self.TASK_EXPIRY_SECONDS)

        # Add only this task to the queue
        task_data = {
            "task_id": task_id,
            "weights": json.dumps(weights),
            "constraints": json.dumps(constraints),
            "limit": limit,
        }
        self.redis_client.rpush(self.QUEUE_KEY, json.dumps(task_data))

        logger.info(f"Created task {task_id}")
        return task_id

    def create_training_task(self, model_type: str = "box_detector") -> str:
        """
        Create a new training task. Cancels any currently running training task.

        Returns:
            Task ID (UUID string)
        """
        task_id = str(uuid.uuid4())
        current_id = self.redis_client.get(self.TRAINING_CURRENT_TASK_KEY)
        if current_id:
            self.redis_client.setex(
                f"task:{current_id}:cancelled",
                self.TASK_EXPIRY_SECONDS,
                "1"
            )
            logger.info(f"Cancelled previous training task {current_id} in favour of {task_id}")

        # Clear only the training queue (do not clear recommendation_tasks)
        self.redis_client.delete(self.TRAINING_QUEUE_KEY)

        task_meta = {
            "task_id": task_id,
            "status": "pending",
            "task_type": "training",
            "model_type": model_type,
            "created_at": datetime.utcnow().isoformat(),
        }
        meta_key = f"task:{task_id}:meta"
        self.redis_client.hset(meta_key, mapping=task_meta)
        self.redis_client.expire(meta_key, self.TASK_EXPIRY_SECONDS)

        task_data = {"task_id": task_id, "model_type": model_type}
        self.redis_client.rpush(self.TRAINING_QUEUE_KEY, json.dumps(task_data))

        logger.info(f"Created training task {task_id}")
        return task_id

    def create_evaluation_task(self, eval_type: str = "evaluate") -> str:
        """
        Create an evaluation task (evaluate or preview). Does not cancel other evaluation tasks.

        Args:
            eval_type: "evaluate" or "preview"

        Returns:
            Task ID (UUID string)
        """
        if eval_type not in ("evaluate", "preview"):
            eval_type = "evaluate"
        task_id = str(uuid.uuid4())
        task_meta = {
            "task_id": task_id,
            "status": "pending",
            "task_type": "evaluation",
            "evaluation_type": eval_type,
            "created_at": datetime.utcnow().isoformat(),
        }
        meta_key = f"task:{task_id}:meta"
        self.redis_client.hset(meta_key, mapping=task_meta)
        self.redis_client.expire(meta_key, self.TASK_EXPIRY_SECONDS)

        task_data = {"task_id": task_id, "type": eval_type}
        self.redis_client.rpush(self.EVALUATION_QUEUE_KEY, json.dumps(task_data))

        logger.info(f"Created evaluation task {task_id} (type={eval_type})")
        return task_id

    def cancel_training_task(self) -> bool:
        """Signal the current training task to cancel. Returns True if a task was running."""
        current_id = self.redis_client.get(self.TRAINING_CURRENT_TASK_KEY)
        if not current_id:
            return False
        self.redis_client.setex(
            f"task:{current_id}:cancelled",
            self.TASK_EXPIRY_SECONDS,
            "1"
        )
        logger.info(f"Requested cancel for training task {current_id}")
        return True

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get task status and results.

        Args:
            task_id: Task ID

        Returns:
            Dictionary with task status, results (if completed), and error (if failed)
        """
        meta_key = f"task:{task_id}:meta"
        result_key = f"task:{task_id}:result"

        # Get task metadata
        meta = self.redis_client.hgetall(meta_key)
        if not meta:
            return {
                "task_id": task_id,
                "status": "not_found",
                "error": "Task not found"
            }

        status = meta.get("status", "unknown")
        response = {
            "task_id": task_id,
            "status": status,
            "created_at": meta.get("created_at"),
        }
        if meta.get("task_type"):
            response["task_type"] = meta.get("task_type")

        # Progress (while processing or completed)
        evaluated_str = meta.get("evaluated")
        total_planned_str = meta.get("total_planned")
        if evaluated_str is not None and total_planned_str is not None:
            try:
                response["progress"] = {
                    "evaluated": int(evaluated_str),
                    "total_planned": int(total_planned_str),
                }
            except (ValueError, TypeError):
                pass

        # Results: when completed, or partial results when still processing
        if status == "completed" or status == "processing":
            result_data = self.redis_client.get(result_key)
            if result_data:
                try:
                    response["results"] = json.loads(result_data)
                except json.JSONDecodeError:
                    if status == "completed":
                        response["error"] = "Failed to parse results"
                        response["status"] = "failed"
        elif status in ("failed", "cancelled"):
            error_data = self.redis_client.get(f"task:{task_id}:error")
            if error_data:
                response["error"] = error_data

        # Latest periodic eval (written by worker's background thread during training)
        eval_data = self.redis_client.get(f"task:{task_id}:eval")
        if eval_data is not None:
            try:
                response["latest_eval"] = json.loads(eval_data)
            except json.JSONDecodeError:
                pass

        # Latest preview (written by worker's eval loop or on training completion)
        preview_data = self.redis_client.get(f"task:{task_id}:latest_preview")
        if preview_data is not None:
            try:
                response["latest_preview"] = json.loads(preview_data)
            except json.JSONDecodeError:
                pass

        # Expected preview duration in ms (worker sets from test_sources count * PREVIEW_MS_PER_IMAGE)
        expected_duration_str = self.redis_client.get(
            f"task:{task_id}:preview_expected_duration_ms"
        )
        if expected_duration_str is not None:
            try:
                response["preview_expected_duration_ms"] = int(expected_duration_str)
            except (ValueError, TypeError):
                pass

        # Model format (.keras vs HDF5) when task loaded a box detector model (e.g. evaluation)
        model_format = self.redis_client.get(f"task:{task_id}:model_format")
        if model_format is not None:
            response["model_format"] = model_format
        elif status == "completed" and response.get("results") and isinstance(response["results"], dict) and "model_format" in response["results"]:
            response["model_format"] = response["results"]["model_format"]

        return response

    def update_task_status(
        self,
        task_id: str,
        status: str,
        results: Optional[Dict] = None,
        error: Optional[str] = None
    ) -> None:
        """
        Update task status (called by worker).

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
            "updated_at": datetime.utcnow().isoformat(),
        }
        self.redis_client.hset(meta_key, mapping=updates)
        self.redis_client.expire(meta_key, self.TASK_EXPIRY_SECONDS)

        # Store results or error
        if status == "completed" and results:
            self.redis_client.setex(
                result_key,
                self.TASK_EXPIRY_SECONDS,
                json.dumps(results)
            )
        elif status == "failed" and error:
            self.redis_client.setex(
                error_key,
                self.TASK_EXPIRY_SECONDS,
                error
            )

        logger.info(f"Updated task {task_id} to status {status}")

    def get_latest_preview(self) -> Optional[Dict[str, Any]]:
        """
        Get the latest training preview (items, scale_regular, scale_blueprint)
        written by the worker's eval loop or on training completion.
        Returns None if no preview is available.
        Tries global key first, then current training task's latest_preview.
        """
        data = self.redis_client.get(self.LATEST_PREVIEW_KEY)
        if data is not None:
            try:
                return json.loads(data)
            except json.JSONDecodeError:
                pass
        current_id = self.redis_client.get(self.TRAINING_CURRENT_TASK_KEY)
        if current_id:
            task_preview = self.redis_client.get(f"task:{current_id}:latest_preview")
            if task_preview is not None:
                try:
                    return json.loads(task_preview)
                except json.JSONDecodeError:
                    pass
        return None
