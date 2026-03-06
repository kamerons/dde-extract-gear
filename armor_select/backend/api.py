"""FastAPI application for armor selection API."""

from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from armor_select.backend.data_loader import DataLoader
from armor_select.backend.models import (
    RecommendationRequest,
    RecommendationResponse,
    Recommendation,
    RecommendationPiece
)
from armor_select.backend.recommendation_engine import RecommendationEngine


# Global state for loaded data
inventory: list[Dict] = []
recommendation_engine: RecommendationEngine = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup: Load data
    global inventory, recommendation_engine

    try:
        loader = DataLoader()
        inventory = loader.load()
        recommendation_engine = RecommendationEngine(inventory)
        print(f"✓ Loaded {len(inventory)} armor pieces")
        print(f"✓ Initialized recommendation engine")
    except FileNotFoundError as e:
        print(f"✗ ERROR: {e}")
        raise
    except ValueError as e:
        print(f"✗ ERROR: {e}")
        raise
    except Exception as e:
        print(f"✗ ERROR: Failed to load data: {e}")
        raise

    yield

    # Shutdown: Cleanup (if needed)
    pass


# Create FastAPI app
app = FastAPI(
    title="Armor Selection API",
    description="API for recommending optimal armor sets",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Armor Selection API",
        "version": "1.0.0",
        "endpoints": {
            "recommendations": "/api/recommendations"
        }
    }


@app.get("/api/recommendations")
async def get_recommendations(
    limit: int = Query(default=10, ge=1, le=100, description="Maximum number of recommendations")
):
    """
    Get top armor set recommendations (simple GET version).

    Query Parameters:
        limit: Maximum number of recommendations (default: 10, max: 100)

    Note: For requests with weights and constraints, use POST /api/recommendations

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

    # Get recommendations
    try:
        recommendations_data = recommendation_engine.get_recommendations(
            weights=weights,
            constraints=constraints,
            limit=limit
        )
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
            potential_score=rec_data['potential_score'],
            flexibility_score=rec_data['flexibility_score']
        )
        recommendations.append(recommendation)

    return RecommendationResponse(
        recommendations=recommendations,
        incremental_changes=None  # Phase 3 feature
    )


@app.post("/api/recommendations")
async def post_recommendations(request: RecommendationRequest):
    """
    Get top armor set recommendations (POST version for requests with weights/constraints).

    Request Body (JSON):
        weights: Dictionary mapping stat names to weights (e.g., {"defense": 0.5, "attack": 0.3})
        constraints: Dictionary with "min" key containing minimum stat requirements
        limit: Maximum number of recommendations (default: 10)

    Returns:
        JSON response with list of recommendations
    """
    if recommendation_engine is None:
        raise HTTPException(
            status_code=503,
            detail="Recommendation engine not initialized. Check server logs."
        )

    # Extract weights and constraints
    weights = request.weights or {}
    constraints = request.constraints.min if request.constraints else {}
    limit = request.limit or 10

    # Get recommendations
    try:
        recommendations_data = recommendation_engine.get_recommendations(
            weights=weights,
            constraints=constraints,
            limit=limit
        )
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
            potential_score=rec_data['potential_score'],
            flexibility_score=rec_data['flexibility_score']
        )
        recommendations.append(recommendation)

    return RecommendationResponse(
        recommendations=recommendations,
        incremental_changes=None  # Phase 3 feature
    )
