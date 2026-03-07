"""Task status endpoints."""

import logging
from fastapi import APIRouter, HTTPException, Path

from api.services.task_service import TaskService

logger = logging.getLogger(__name__)

router = APIRouter()
task_service = TaskService()


@router.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str = Path(..., description="Task ID")):
    """
    Get task status and results.

    Path Parameters:
        task_id: Task ID returned from POST /api/recommendations

    Returns:
        JSON response with task status, results (if completed), and error (if failed)
    """
    try:
        status = task_service.get_task_status(task_id)

        if status["status"] == "not_found":
            raise HTTPException(
                status_code=404,
                detail=f"Task {task_id} not found"
            )

        return status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get task status: {str(e)}"
        ) from e
