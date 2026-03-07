"""Extract pipeline endpoints: screenshots and region boxes."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.config import Config
from shared.extract_regions import compute_boxes

logger = logging.getLogger(__name__)

router = APIRouter()
config = Config()

# Allowed subdirs under DATA_DIR for listing/serving (path traversal protection)
ALLOWED_SCREENSHOT_SUBDIRS = (
    "unlabeled/screenshots",
    "labeled/screenshots/regular",
    "labeled/screenshots/blueprint",
)


def _data_dir() -> Path:
    """Return absolute path to data directory (relative to repo root)."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    return (repo_root / config.DATA_DIR).resolve()


def _screenshot_path(filename: str, subdir: str = "unlabeled/screenshots") -> Path:
    """Resolve screenshot path; raise if outside allowed dirs."""
    if subdir not in ALLOWED_SCREENSHOT_SUBDIRS:
        raise HTTPException(status_code=400, detail="Invalid screenshot subdir")
    base = (_data_dir() / subdir).resolve()
    path = (base / filename).resolve()
    try:
        path.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return path


class BoxesRequest(BaseModel):
    """Request body for POST /api/extract/boxes."""

    origin_x: int
    origin_y: int
    scale: float
    image_type: str  # "regular" | "blueprint"


@router.get("/api/extract/screenshots")
async def list_screenshots(
    subdir: str = "unlabeled/screenshots",
):
    """
    List screenshot filenames in the given subdir.

    Query params:
        subdir: One of unlabeled/screenshots, labeled/screenshots/regular, labeled/screenshots/blueprint
    """
    if subdir not in ALLOWED_SCREENSHOT_SUBDIRS:
        raise HTTPException(status_code=400, detail="Invalid subdir")
    base = _data_dir() / subdir
    if not base.exists():
        return {"filenames": []}
    filenames = sorted(
        p.name for p in base.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg")
    )
    return {"filenames": filenames}


@router.get("/api/extract/screenshots/{filename}")
async def serve_screenshot(
    filename: str,
    subdir: str = "unlabeled/screenshots",
):
    """Serve a single screenshot image."""
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = _screenshot_path(filename, subdir)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Screenshot not found")
    return FileResponse(path, media_type="image/png")


@router.post("/api/extract/boxes")
async def post_boxes(body: BoxesRequest):
    """
    Compute region boxes for the first card given origin and scale.

    Returns list of boxes: x, y, width, height, type (card, set, stat, level).
    """
    if body.image_type not in ("regular", "blueprint"):
        raise HTTPException(
            status_code=400,
            detail="image_type must be 'regular' or 'blueprint'",
        )
    if body.scale <= 0:
        raise HTTPException(status_code=400, detail="scale must be positive")
    boxes = compute_boxes(
        origin_x=body.origin_x,
        origin_y=body.origin_y,
        scale=body.scale,
        image_type=body.image_type,
    )
    return {"boxes": boxes}
