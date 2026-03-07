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


def _box_detector_load_path() -> tuple[Path | None, Path, str]:
    """
    Path to load for box detector: interim _current (during training), latest
    timestamped final model (stem_YYYYMMDD_HHMMSS.keras), or legacy stem.keras.
    All under DATA_DIR/models/box_detector to match the processor.
    Returns (load_path or None, model_dir, stem) so callers can show where we looked on 404.
    """
    model_dir = (_data_dir() / "models" / "box_detector").resolve()
    stem = Path(config.BOX_DETECTOR_MODEL_PATH).name
    if stem.endswith(".keras") or stem.endswith(".h5"):
        stem = Path(stem).stem
    current_path = model_dir / (stem + "_current.keras")
    legacy_path = model_dir / (stem + ".keras")

    # 1) During training: use current checkpoint
    if current_path.exists():
        return (current_path, model_dir, stem)
    # 2) Latest timestamped final model (saved when training completes)
    timestamped = sorted(
        model_dir.glob(f"{stem}_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9].keras"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if timestamped:
        return (timestamped[0], model_dir, stem)
    # 3) Legacy single file
    if legacy_path.exists():
        return (legacy_path, model_dir, stem)

    try:
        if not model_dir.exists():
            logger.warning("Box detector model not found: model_dir=%s (missing), stem=%s", model_dir, stem)
        else:
            logger.warning("Box detector model not found: model_dir=%s, stem=%s", model_dir, stem)
    except OSError as e:
        logger.warning("Box detector model not found: model_dir=%s, stem=%s; %s", model_dir, stem, e)
    return (None, model_dir, stem)


def _box_detector_not_found_detail(model_dir: Path, stem: str) -> str:
    """Message for 404 when no box detector model is found; includes path we looked in."""
    return (
        f"Box detector model not found. Looked in {model_dir} for "
        f"{stem}_current.keras, {stem}_<timestamp>.keras, or {stem}.keras. "
        "Run training first or check DATA_DIR and BOX_DETECTOR_MODEL_PATH (and volume mount if using Docker)."
    )


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
        "augment_count": config.EXTRACT_AUGMENT_COUNT,
        "preview_every_n_epochs": config.PREVIEW_EVERY_N_EPOCHS,
        "preview_expected_duration_ms": config.PREVIEW_EXPECTED_DURATION_MS,
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


def _labeled_counts_for_subdir(base: Path) -> list[str]:
    """Return sorted list of image filenames that have a companion .txt (origin) in base."""
    if not base.exists():
        return []
    has_origin = []
    for p in base.iterdir():
        if p.suffix.lower() in (".png", ".jpg", ".jpeg") and (p.with_suffix(".txt")).exists():
            has_origin.append(p.name)
    return sorted(has_origin)


@router.get("/api/extract/training-data")
async def get_training_data():
    """
    Return counts of labeled screenshots (source images with companion .txt) per subdir,
    plus augmentation config so the frontend can show how many augmented samples
    are used. Each source image is expanded to augment_count samples per epoch.
    """
    data_dir = _data_dir()
    regular_dir = data_dir / "labeled" / "screenshots" / "regular"
    blueprint_dir = data_dir / "labeled" / "screenshots" / "blueprint"
    regular_count = len(_labeled_counts_for_subdir(regular_dir))
    blueprint_count = len(_labeled_counts_for_subdir(blueprint_dir))
    total_sources = regular_count + blueprint_count
    augment_count = config.EXTRACT_AUGMENT_COUNT
    return {
        "total": total_sources,
        "regular": regular_count,
        "blueprint": blueprint_count,
        "augment_count": augment_count,
        "augmented_samples_per_epoch_max": total_sources * augment_count,
    }


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
        out = {"filenames": []}
        if subdir in LABELED_SCREENSHOT_SUBDIRS_WRITABLE:
            out["has_origin"] = []
        return out
    filenames = sorted(
        p.name for p in base.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg")
    )
    out = {"filenames": filenames}
    if subdir in LABELED_SCREENSHOT_SUBDIRS_WRITABLE:
        out["has_origin"] = [
            name for name in filenames
            if (base / name).with_suffix(".txt").exists()
        ]
    return out


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
    resume_from_existing: bool = False


@router.post("/api/extract/training/start")
async def training_start(body: TrainingStartRequest | None = None):
    """
    Start a box detector training task. Returns task_id to poll via GET /api/tasks/{task_id}.
    Body is optional; default model_type is box_detector.
    """
    model_type = (body.model_type if body is not None else "box_detector") or "box_detector"
    if model_type != "box_detector":
        raise HTTPException(status_code=400, detail="Only model_type 'box_detector' is supported")
    resume_from_existing = body.resume_from_existing if body is not None else False
    try:
        task_id = task_service.create_training_task(
            model_type=model_type,
            resume_from_existing=resume_from_existing,
        )
    except Exception as e:
        logger.exception("Failed to create training task")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"task_id": task_id, "status": "pending"}


@router.post("/api/extract/training/stop")
async def training_stop():
    """Cancel the current training task, if any."""
    cancelled = task_service.cancel_training_task()
    return {"ok": True, "cancelled": cancelled, "message": "Training cancel requested" if cancelled else "No training task was running"}


@router.post("/api/extract/training/evaluate")
async def training_evaluate_start():
    """
    Start an evaluation task: run box detector on the test set.
    Returns task_id; poll GET /api/tasks/{task_id} for results (metrics) and model_format.
    """
    try:
        task_id = task_service.create_evaluation_task(eval_type="evaluate")
    except Exception as e:
        logger.exception("Failed to create evaluation task")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"task_id": task_id, "status": "pending"}


@router.get("/api/extract/training/preview/latest")
async def training_preview_latest():
    """
    Return the latest training preview (items, scale_regular, scale_blueprint)
    written automatically during training or on completion. Returns null when no preview is available yet.
    """
    preview = task_service.get_latest_preview()
    return preview if preview is not None else None


@router.post("/api/extract/training/preview")
async def training_preview_start():
    """
    Start a preview task: test set items with ground-truth and predicted origins.
    Returns task_id; poll GET /api/tasks/{task_id} for results (items, scale_regular, scale_blueprint) and model_format.
    """
    try:
        task_id = task_service.create_evaluation_task(eval_type="preview")
    except Exception as e:
        logger.exception("Failed to create preview task")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"task_id": task_id, "status": "pending"}
