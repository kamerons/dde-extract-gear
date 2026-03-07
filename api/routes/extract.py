"""Extract pipeline endpoints: screenshots, region boxes, and box detector training."""

import logging
import re
import shutil
import tempfile
import zipfile
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

    # Log why we found nothing so logs show what the API actually sees
    try:
        exists = model_dir.exists()
        listing = list(model_dir.iterdir()) if exists else []
        logger.warning(
            "Box detector model not found: model_dir=%s (exists=%s), stem=%s, files=%s. "
            "Check DATA_DIR, BOX_DETECTOR_MODEL_PATH, and that the API has the same data volume as the worker.",
            model_dir, exists, stem, [p.name for p in listing[:20]],
        )
    except OSError as e:
        logger.warning(
            "Box detector model not found: model_dir=%s, stem=%s; listdir failed: %s",
            model_dir, stem, e,
        )
    return (None, model_dir, stem)


def _box_detector_not_found_detail(model_dir: Path, stem: str) -> str:
    """Message for 404 when no box detector model is found; includes path we looked in."""
    return (
        f"Box detector model not found. Looked in {model_dir} for "
        f"{stem}_current.keras, {stem}_<timestamp>.keras, or {stem}.keras. "
        "Run training first or check DATA_DIR and BOX_DETECTOR_MODEL_PATH (and volume mount if using Docker)."
    )


def _box_detector_404_debug(model_dir: Path, stem: str) -> dict:
    """Debug info to include in 404 response so the client can see what the API saw."""
    current_path = model_dir / (stem + "_current.keras")
    try:
        listing = sorted(p.name for p in model_dir.iterdir()) if model_dir.exists() else []
    except OSError as e:
        listing = [f"listdir error: {e}"]
    return {
        "model_dir": str(model_dir),
        "stem": stem,
        "model_dir_exists": model_dir.exists(),
        "current_exists": current_path.exists(),
        "listing": listing,
    }


def _load_box_detector_model(load_path: Path):
    """
    Load Keras model from path. Copies to a temp file then loads, so Keras can read it
    reliably (it often raises 'File not found' on bind-mounted paths even when the file exists).
    If the file is not a .keras zip (e.g. legacy HDF5 saved with .keras extension), we copy
    to a temp file with .h5 suffix so load_model treats it as HDF5.
    """
    from tensorflow import keras

    is_zip = zipfile.is_zipfile(load_path)
    suffix = ".keras" if is_zip else ".h5"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        tmp_path = Path(f.name)
    try:
        shutil.copy2(load_path, tmp_path)
        # HDF5 from tf.keras (task) can have compile config that this Keras can't deserialize;
        # we only need the model for inference, so skip loading loss/optimizer/metrics.
        compile_load = True if is_zip else False
        return keras.models.load_model(str(tmp_path), compile=compile_load)
    finally:
        tmp_path.unlink(missing_ok=True)


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


@router.get("/api/extract/training/model-debug")
async def training_model_debug():
    """
    Return resolved box-detector paths and config as seen by this process.
    Use to debug 404s when models exist on disk (e.g. volume vs config).
    """
    load_path, model_dir, stem = _box_detector_load_path()
    current_path = model_dir / (stem + "_current.keras")
    legacy_path = model_dir / (stem + ".keras")
    try:
        listing = [p.name for p in model_dir.iterdir()] if model_dir.exists() else []
    except OSError as e:
        listing = [f"error: {e}"]
    return {
        "DATA_DIR": config.DATA_DIR,
        "BOX_DETECTOR_MODEL_PATH": config.BOX_DETECTOR_MODEL_PATH,
        "model_dir": str(model_dir),
        "stem": stem,
        "current_path": str(current_path),
        "current_exists": current_path.exists(),
        "legacy_path": str(legacy_path),
        "legacy_exists": legacy_path.exists(),
        "listing": sorted(listing),
        "load_path": str(load_path) if load_path else None,
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

    load_path, model_dir, stem = _box_detector_load_path()
    if load_path is None:
        current_path = model_dir / (stem + "_current.keras")
        legacy_path = model_dir / (stem + ".keras")
        if current_path.exists():
            load_path = current_path
        else:
            timestamped = sorted(
                model_dir.glob(f"{stem}_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9].keras"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if timestamped:
                load_path = timestamped[0]
            elif legacy_path.exists():
                load_path = legacy_path
    if load_path is None:
        raise HTTPException(
            status_code=404,
            detail={
                "message": _box_detector_not_found_detail(model_dir, stem),
                "debug": _box_detector_404_debug(model_dir, stem),
            },
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
        augment=True,
        shift_regular=config.EXTRACT_AUGMENT_SHIFT_REGULAR,
        shift_blueprint=config.EXTRACT_AUGMENT_SHIFT_BLUEPRINT,
        fill_mode=config.EXTRACT_AUGMENT_FILL,
        augment_count=config.EXTRACT_AUGMENT_COUNT,
    )

    try:
        model = _load_box_detector_model(load_path)
    except Exception as e:
        err_msg = str(e)
        logger.warning(
            "training_evaluate: Keras load_model failed for path=%s: %s",
            load_path, err_msg,
            exc_info=True,
        )
        if isinstance(e, ValueError) and ("File not found" in err_msg or "filepath=" in err_msg):
            raise HTTPException(
                status_code=404,
                detail={
                    "message": f"Model file found at {load_path} but Keras failed to load it: {err_msg}",
                    "debug": {"load_path": str(load_path), "error": err_msg},
                },
            ) from e
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load box detector model from {load_path}: {err_msg}",
        ) from e

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

    load_path, model_dir, stem = _box_detector_load_path()
    logger.info(
        "training_preview: after _box_detector_load_path: load_path=%s, model_dir=%s, stem=%s",
        load_path, model_dir, stem,
    )
    # Second-chance: resolve from one debug snapshot (same source for decision and 404 body)
    debug = None
    if load_path is None:
        debug = _box_detector_404_debug(model_dir, stem)
        logger.info(
            "training_preview: second-chance debug snapshot: current_exists=%s, model_dir_exists=%s, listing=%s",
            debug.get("current_exists"), debug.get("model_dir_exists"), debug.get("listing"),
        )
        if debug.get("current_exists"):
            load_path = model_dir / (stem + "_current.keras")
            logger.info("training_preview: second-chance resolved from current_exists -> %s", load_path)
        elif debug.get("listing"):
            current_name = stem + "_current.keras"
            legacy_name = stem + ".keras"
            if current_name in debug["listing"]:
                load_path = model_dir / current_name
                logger.info("training_preview: second-chance resolved from listing (current) -> %s", load_path)
            elif legacy_name in debug["listing"]:
                load_path = model_dir / legacy_name
                logger.info("training_preview: second-chance resolved from listing (legacy) -> %s", load_path)
            else:
                ts_pattern = re.compile(rf"^{re.escape(stem)}_(\d{{8}})_(\d{{6}})\.keras$")
                timestamped = [n for n in debug["listing"] if ts_pattern.match(n)]
                timestamped.sort(reverse=True)
                if timestamped:
                    load_path = model_dir / timestamped[0]
                    logger.info("training_preview: second-chance resolved from listing (timestamped) -> %s", load_path)
    if load_path is None:
        logger.warning(
            "training_preview: RAISING 404 — load_path still None after second-chance. "
            "model_dir=%s stem=%s debug_current_exists=%s debug_listing=%s",
            model_dir, stem, debug.get("current_exists") if debug else None, debug.get("listing") if debug else None,
        )
        raise HTTPException(
            status_code=404,
            detail={
                "message": _box_detector_not_found_detail(model_dir, stem),
                "debug": debug if debug is not None else _box_detector_404_debug(model_dir, stem),
            },
        )

    logger.info(
        "training_preview: load_path=%s, model_dir=%s, stem=%s",
        load_path, model_dir, stem,
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

    try:
        model = _load_box_detector_model(load_path)
    except Exception as e:
        err_msg = str(e)
        logger.warning(
            "training_preview: Keras load_model failed for path=%s: %s",
            load_path, err_msg,
            exc_info=True,
        )
        if isinstance(e, ValueError) and ("File not found" in err_msg or "filepath=" in err_msg):
            raise HTTPException(
                status_code=404,
                detail={
                    "message": f"Model file found at {load_path} but Keras failed to load it: {err_msg}",
                    "debug": {"load_path": str(load_path), "error": err_msg},
                },
            ) from e
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load box detector model from {load_path}: {err_msg}",
        ) from e
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
