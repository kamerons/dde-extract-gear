"""Shared Redis task status and progress updates. Single place for the task Redis key contract."""

import json
from typing import Any, Dict, Optional


RESULT_EXPIRY_SECONDS = 3600


def update_task_status(
    redis_client: Any,
    task_id: str,
    status: str,
    results: Optional[Dict] = None,
    error: Optional[str] = None,
) -> None:
    """
    Update task status in Redis.

    Args:
        redis_client: Redis client (decode_responses=True).
        task_id: Task ID.
        status: New status (processing, completed, failed, cancelled).
        results: Results dictionary (if completed).
        error: Error message (if failed or cancelled).
    """
    meta_key = f"task:{task_id}:meta"
    result_key = f"task:{task_id}:result"
    error_key = f"task:{task_id}:error"

    redis_client.hset(meta_key, mapping={"status": status})

    if status == "completed" and results:
        redis_client.setex(result_key, RESULT_EXPIRY_SECONDS, json.dumps(results))
    elif status in ("failed", "cancelled") and error:
        redis_client.setex(error_key, RESULT_EXPIRY_SECONDS, error)


def update_task_progress(
    redis_client: Any,
    task_id: str,
    evaluated: int,
    total_planned: int,
    partial_results: Optional[Dict] = None,
) -> None:
    """
    Update task progress and optionally partial results in Redis.
    Does not change status (task remains "processing").

    Args:
        redis_client: Redis client (decode_responses=True).
        task_id: Task ID.
        evaluated: Number of items evaluated so far.
        total_planned: Total number of items to evaluate.
        partial_results: Optional partial results (e.g. metrics or recommendations).
    """
    meta_key = f"task:{task_id}:meta"
    result_key = f"task:{task_id}:result"

    redis_client.hset(
        meta_key,
        mapping={
            "evaluated": str(evaluated),
            "total_planned": str(total_planned),
        },
    )
    if partial_results is not None:
        redis_client.setex(
            result_key,
            RESULT_EXPIRY_SECONDS,
            json.dumps(partial_results),
        )
