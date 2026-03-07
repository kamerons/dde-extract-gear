"""Extract pipeline endpoints: screenshots, region boxes, and box detector training."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.config import Config
from api.services.task_service import TaskService
from shared.extract_regions import compute_boxes

logger = logging.getLogger(__name__)

router = APIRouter()
config = Config()
task_service = TaskService()

# Allowed subdirs under DATA_DIR for listing/serving (path traversal protection)
ALLOWED_SCREENSHOT_SUBDIRS = (
    "unlabeled/screenshots",
    "labeled/screenshots/regular",
    "labeled/screenshots/blueprint",
    "labeled/augmented/regular",
    "labeled/augmented/blueprint",
)

# Subdirs that allow saving origin (.txt) next to the screenshot
LABELED_SCREENSHOT_SUBDIRS_WRITABLE = (
    "labeled/screenshots/regular",
    "labeled/screenshots/blueprint",
)


def _repo_root() -> Path:
    """Return absolute path to repo root."""
    return Path(__file__).resolve().parent.parent.parent


def _data_dir() -> Path:
    """Return absolute path to data directory (relative to repo root)."""
    return (_repo_root() / config.DATA_DIR).resolve()


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


class SaveOriginRequest(BaseModel):
    """Request body for POST /api/extract/screenshots/save-origin."""

    filename: str
    subdir: str  # labeled/screenshots/regular | labeled/screenshots/blueprint
    origin_x: int
    origin_y: int


@router.get("/api/extract/config")
async def get_extract_config():
    """
    Return extract pipeline config from env (scale and augmentation).
    Used by the frontend for .env display and augmentation preview.
    """
    return {
        "regular_scale": config.EXTRACT_REGULAR_SCALE,
        "blueprint_scale": config.EXTRACT_BLUEPRINT_SCALE,
        "augment_shift_regular": config.EXTRACT_AUGMENT_SHIFT_REGULAR,
        "augment_shift_blueprint": config.EXTRACT_AUGMENT_SHIFT_BLUEPRINT,
        "augment_fill": config.EXTRACT_AUGMENT_FILL,
    }


@router.post("/api/extract/screenshots/save-origin")
async def save_origin(body: SaveOriginRequest):
    """
    Persist the box origin for a labeled screenshot. Writes a .txt file
    next to the image with one line: origin_x origin_y.
    """
    if body.subdir not in LABELED_SCREENSHOT_SUBDIRS_WRITABLE:
        raise HTTPException(
            status_code=400,
            detail="subdir must be labeled/screenshots/regular or labeled/screenshots/blueprint",
        )
    if "/" in body.filename or "\\" in body.filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    base = (_data_dir() / body.subdir).resolve()
    base.mkdir(parents=True, exist_ok=True)
    png_path = (base / body.filename).resolve()
    try:
        png_path.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if png_path.suffix.lower() not in (".png", ".jpg", ".jpeg"):
        raise HTTPException(status_code=400, detail="Filename must be an image")
    txt_path = png_path.with_suffix(".txt")
    try:
        txt_path.write_text(f"{body.origin_x} {body.origin_y}\n")
    except OSError as e:
        logger.exception("Failed to write origin .txt")
        if getattr(e, "errno", None) == 30:
            raise HTTPException(
                status_code=503,
                detail="The data directory is read-only. If running in Docker, mount the data volume with write access (e.g. a writable bind mount for ./data).",
            ) from e
        raise HTTPException(status_code=500, detail="Failed to save origin") from e
    return {"ok": True, "path": str(txt_path.relative_to(_data_dir()))}


@router.get("/api/extract/screenshots")
async def list_screenshots(
    subdir: str = "unlabeled/screenshots",
):
    """
    List screenshot filenames in the given subdir.

    Query params:
        subdir: One of unlabeled/screenshots, labeled/screenshots/regular,
                labeled/screenshots/blueprint, labeled/augmented/regular,
                labeled/augmented/blueprint
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


class TrainingStartRequest(BaseModel):
    """Request body for POST /api/extract/training/start."""

    model_type: str = "box_detector"


@router.post("/api/extract/training/start")
async def training_start(body: TrainingStartRequest | None = None):
    """
    Start a box detector training task. Returns task_id to poll via GET /api/tasks/{task_id}.
    Body is optional; default model_type is box_detector.
    """
    model_type = (body.model_type if body is not None else "box_detector") or "box_detector"
    if model_type != "box_detector":
        raise HTTPException(status_code=400, detail="Only model_type 'box_detector' is supported")
    try:
        task_id = task_service.create_training_task(model_type=model_type)
    except Exception as e:
        logger.exception("Failed to create training task")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"task_id": task_id, "status": "pending"}


@router.post("/api/extract/training/stop")
async def training_stop():
    """Cancel the current training task, if any."""
    cancelled = task_service.cancel_training_task()
    return {"ok": True, "cancelled": cancelled, "message": "Training cancel requested" if cancelled else "No training task was running"}


@router.get("/api/extract/training/evaluate")
async def training_evaluate():
    """
    Evaluate the saved box detector model on the test set (same split logic as training).
    Returns test metrics. 404 if no model exists.
    """
    from task.processors.box_detector_processor import (
        _build_arrays,
        _compute_test_metrics,
        _labeled_dirs,
        _scan_sources,
        _split_train_test,
    )

    # Processor saves with .keras extension; support both for backwards compatibility
    model_path = _repo_root() / config.BOX_DETECTOR_MODEL_PATH
    load_path = (
        model_path
        if model_path.exists()
        else Path(str(model_path) + ".keras")
    )
    if not load_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Box detector model not found. Run training first.",
        )

    data_dir = _data_dir()
    labeled = _labeled_dirs(data_dir)
    if not labeled:
        raise HTTPException(
            status_code=400,
            detail="No labeled screenshots found.",
        )
    sources = _scan_sources(labeled)
    if not sources:
        raise HTTPException(
            status_code=400,
            detail="No valid (image, .txt) pairs found.",
        )
    _, test_sources = _split_train_test(sources, config.BOX_DETECTOR_TEST_RATIO)
    if not test_sources:
        raise HTTPException(
            status_code=400,
            detail="No test set after split.",
        )

    X_test, y_test = _build_arrays(
        test_sources,
        augment=False,
        shift_regular=config.EXTRACT_AUGMENT_SHIFT_REGULAR,
        shift_blueprint=config.EXTRACT_AUGMENT_SHIFT_BLUEPRINT,
        fill_mode=config.EXTRACT_AUGMENT_FILL,
        augment_count=config.EXTRACT_AUGMENT_COUNT,
    )

    from tensorflow import keras
    model = keras.models.load_model(str(load_path))
    metrics = _compute_test_metrics(model, X_test, y_test)
    return metrics


@router.get("/api/extract/training/preview")
async def training_preview():
    """
    Return test set items with ground-truth and predicted origins for box detector.
    Frontend can draw boxes for both and show next/previous. 404 if no model.
    """
    from task.processors.box_detector_processor import (
        INPUT_HEIGHT,
        INPUT_WIDTH,
        _build_arrays,
        _labeled_dirs,
        _load_image,
        _scan_sources,
        _split_train_test,
    )

    model_path = _repo_root() / config.BOX_DETECTOR_MODEL_PATH
    load_path = (
        model_path
        if model_path.exists()
        else Path(str(model_path) + ".keras")
    )
    if not load_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Box detector model not found. Run training first.",
        )

    data_dir = _data_dir()
    labeled = _labeled_dirs(data_dir)
    if not labeled:
        raise HTTPException(
            status_code=400,
            detail="No labeled screenshots found.",
        )
    sources = _scan_sources(labeled)
    if not sources:
        raise HTTPException(
            status_code=400,
            detail="No valid (image, .txt) pairs found.",
        )
    _, test_sources = _split_train_test(sources, config.BOX_DETECTOR_TEST_RATIO)
    if not test_sources:
        raise HTTPException(
            status_code=400,
            detail="No test set after split.",
        )

    X_test, _ = _build_arrays(
        test_sources,
        augment=False,
        shift_regular=config.EXTRACT_AUGMENT_SHIFT_REGULAR,
        shift_blueprint=config.EXTRACT_AUGMENT_SHIFT_BLUEPRINT,
        fill_mode=config.EXTRACT_AUGMENT_FILL,
        augment_count=config.EXTRACT_AUGMENT_COUNT,
    )

    from tensorflow import keras
    model = keras.models.load_model(str(load_path))
    pred = model.predict(X_test, verbose=0)

    items = []
    for i, (typename, filename, png_path, ox, oy) in enumerate(test_sources):
        img = _load_image(png_path)
        w, h = img.size
        scale_x = INPUT_WIDTH / w
        scale_y = INPUT_HEIGHT / h
        pred_x = int(round(float(pred[i, 0]) / scale_x))
        pred_y = int(round(float(pred[i, 1]) / scale_y))
        subdir = f"labeled/screenshots/{typename}"
        items.append({
            "filename": filename,
            "subdir": subdir,
            "origin_x": ox,
            "origin_y": oy,
            "pred_x": pred_x,
            "pred_y": pred_y,
        })

    return {
        "items": items,
        "scale_regular": config.EXTRACT_REGULAR_SCALE,
        "scale_blueprint": config.EXTRACT_BLUEPRINT_SCALE,
    }
