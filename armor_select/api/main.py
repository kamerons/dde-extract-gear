"""FastAPI application for armor selection API."""

import logging
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from armor_select.shared.data_loader import DataLoader
from armor_select.shared.recommendation_engine import RecommendationEngine
from armor_select.api.routes import recommendations, tasks

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    # Startup: Load data
    try:
        loader = DataLoader()
        inventory = loader.load()
        recommendation_engine = RecommendationEngine(inventory)

        # Set the engine in the recommendations router
        recommendations.set_recommendation_engine(recommendation_engine, inventory)

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

# Include routers
app.include_router(recommendations.router)
app.include_router(tasks.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Armor Selection API",
        "version": "1.0.0",
        "endpoints": {
            "recommendations": "/api/recommendations",
            "tasks": "/api/tasks/{task_id}"
        }
    }
