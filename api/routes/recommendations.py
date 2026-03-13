"""Recommendation endpoints."""

import logging
from pathlib import Path
from typing import Dict

from fastapi import APIRouter, HTTPException, Query

from shared.models import (
    RecommendationRequest,
    RecommendationResponse,
    Recommendation,
    RecommendationPiece
)
from shared.recommendation_engine import RecommendationEngine, TooManyCombinationsError
from api.config import Config
from api.services.task_service import TaskService

logger = logging.getLogger(__name__)

router = APIRouter()
task_service = TaskService()
config = Config()

DATA_COLLECTED_PREFIX = "data/collected/"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _collected_dir() -> Path:
    return (_repo_root() / config.DATA_DIR / "collected").resolve()


def _normalize_data_file(value: str | None) -> str | None:
    """Return path like data/collected/sample.json or None. Reject path traversal."""
    if not value or not value.strip():
        return None
    value = value.strip()
    if ".." in value or value.startswith("/") or (len(value) > 1 and value[1] == ":"):
        return None
    if "/" not in value:
        return DATA_COLLECTED_PREFIX + value if value.endswith(".json") else DATA_COLLECTED_PREFIX + value + ".json"
    if value.startswith(DATA_COLLECTED_PREFIX):
        return value
    return None

# Global state for loaded data (will be initialized in lifespan)
inventory: list[Dict] = []
recommendation_engine: RecommendationEngine = None


def set_recommendation_engine(engine: RecommendationEngine, inv: list[Dict]):
    """Set the global recommendation engine and inventory."""
    global recommendation_engine, inventory
    recommendation_engine = engine
    inventory = inv


@router.get("/api/data-files")
async def list_data_files():
    """
    List JSON filenames in data/collected/ for the Recommendations data-file dropdown.
    Returns {"files": ["sample.json", "run1.json", ...]}.
    """
    collected = _collected_dir()
    if not collected.exists():
        return {"files": []}
    files = sorted(
        p.name for p in collected.iterdir()
        if p.is_file() and p.suffix.lower() == ".json"
    )
    return {"files": files}


@router.get("/api/recommendations")
async def get_recommendations(
    limit: int = Query(default=10, ge=1, le=100, description="Maximum number of recommendations")
):
    """
    Get top armor set recommendations (simple GET version - synchronous).

    Query Parameters:
        limit: Maximum number of recommendations (default: 10, max: 100)

    Note: For requests with weights and constraints, use POST /api/recommendations
          which will create an async task.

    Returns:
        JSON response with list of recommendations
    """
    if recommendation_engine is None:
        raise HTTPException(
            status_code=503,
            detail="Recommendation engine not initialized. Check server logs."
        )

    # Use empty weights and constraints for GET
    weights = {}
    constraints = {}

    # Log request
    logger.info(f"New GET request received: limit={limit}")

    # Get recommendations
    try:
        recommendations_data = recommendation_engine.get_recommendations(
            weights=weights,
            constraints=constraints,
            limit=limit
        )
    except TooManyCombinationsError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error generating recommendations: {str(e)}"
        ) from e

    # Convert to response models
    recommendations = []
    for rec_data in recommendations_data:
        pieces = [
            RecommendationPiece(**piece)
            for piece in rec_data['pieces']
        ]
        recommendation = Recommendation(
            set_id=rec_data['set_id'],
            pieces=pieces,
            current_stats=rec_data['current_stats'],
            upgraded_stats=rec_data['upgraded_stats'],
            effective_stats=rec_data['effective_stats'],
            wasted_points=rec_data['wasted_points'],
            score=rec_data['score'],
            score_breakdown=rec_data.get('score_breakdown'),
            potential_score=rec_data['potential_score'],
            flexibility_score=rec_data['flexibility_score']
        )
        recommendations.append(recommendation)

    return RecommendationResponse(
        recommendations=recommendations,
        incremental_changes=None  # Phase 3 feature
    )


@router.post("/api/recommendations")
async def post_recommendations(request: RecommendationRequest):
    """
    Create a recommendation task (async).

    Request Body (JSON):
        weights: Dictionary mapping stat names to weights (e.g., {"defense": 0.5, "attack": 0.3})
        constraints: Dictionary with "min" key containing minimum stat requirements
        limit: Maximum number of recommendations (default: 10)

    Returns:
        JSON response with task_id and status
    """
    # Extract weights and constraints
    weights = request.weights or {}
    constraints = request.constraints.min if request.constraints else {}
    limit = request.limit or 10
    data_file = None
    if request.data_file:
        data_file = _normalize_data_file(request.data_file)
        if data_file is None:
            raise HTTPException(
                status_code=400,
                detail="data_file must be a filename under data/collected/ (e.g. sample.json or data/collected/sample.json)",
            )

    # Log request
    logger.info(f"New POST request received: weights={weights}, constraints={constraints}, limit={limit}, data_file={data_file}")

    # Create task
    try:
        task_id = task_service.create_task(
            weights=weights,
            constraints=constraints,
            limit=limit,
            data_file=data_file,
        )
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create task: {str(e)}"
        ) from e

    return {
        "task_id": task_id,
        "status": "pending",
        "message": "Task created. Poll /api/tasks/{task_id} for results."
    }
