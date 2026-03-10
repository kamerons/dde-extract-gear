"""Extract pipeline endpoints: screenshots, region boxes, and box detector training."""

import io
import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from PIL import Image
from pydantic import BaseModel

from api.config import Config
from api.services.task_service import TaskService
from shared.box_detector_augment import compute_translation_margin_lines, crop_to_inner_rect
from shared.extract_regions import compute_boxes
from shared.stat_normalizer import StatNormalizer

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

# Valid stat types for stat icon labeling (STAT_GROUPS keys + "none")
VALID_STAT_TYPES = frozenset(list(StatNormalizer.STAT_GROUPS.keys()) + ["none"])


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


def _box_detector_stem() -> str:
    """Stem for box detector model filenames (no .keras/.h5)."""
    stem = Path(config.BOX_DETECTOR_MODEL_PATH).name
    if stem.endswith(".keras") or stem.endswith(".h5"):
        stem = Path(stem).stem
    return stem


def _box_detector_path_for_model_id(model_dir: Path, stem: str, model_id: str) -> Path | None:
    """
    Resolve model_id to a .keras path under model_dir. Only allows known ids:
    stem_current, stem_YYYYMMDD_HHMMSS, or stem. Returns None if invalid or file missing.
    """
    if not model_id or not isinstance(model_id, str):
        return None
    # Restrict to alphanumeric and underscore
    if not model_id.replace("_", "").isalnum():
        return None
    path = (model_dir / (model_id + ".keras")).resolve()
    try:
        path.relative_to(model_dir.resolve())
    except ValueError:
        return None
    if not path.exists() or not path.is_file():
        return None
    # Allow stem_current, stem (legacy), or stem_YYYYMMDD_HHMMSS
    if model_id == stem or model_id == stem + "_current":
        return path
    if model_id.startswith(stem + "_") and len(model_id) == len(stem) + 1 + 15:
        suffix = model_id[len(stem) + 1 :]
        if len(suffix) == 15 and suffix[8:9] == "_":
            try:
                int(suffix[:8])
                int(suffix[9:])
                return path
            except ValueError:
                pass
    return None


def _box_detector_not_found_detail(model_dir: Path, stem: str) -> str:
    """Message for 404 when no box detector model is found; includes path we looked in."""
    return (
        f"Box detector model not found. Looked in {model_dir} for "
        f"{stem}_current.keras, {stem}_<timestamp>.keras, or {stem}.keras. "
        "Run training first or check DATA_DIR and BOX_DETECTOR_MODEL_PATH (and volume mount if using Docker)."
    )


def _list_box_detector_models() -> list[dict]:
    """List available box detector models for dropdown. Returns list of { id, display_name, is_current? }."""
    model_dir = (_data_dir() / "models" / "box_detector").resolve()
    stem = _box_detector_stem()
    out = []
    current_path = model_dir / (stem + "_current.keras")
    if current_path.exists():
        out.append({"id": stem + "_current", "display_name": "Current (checkpoint)", "is_current": True})
    timestamped = sorted(
        model_dir.glob(f"{stem}_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9].keras"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for p in timestamped:
        # display from stem suffix e.g. 20240308_120000 -> "2024-03-08 12:00:00"
        suf = p.stem[len(stem) + 1 :]
        if len(suf) == 15 and suf[8:9] == "_":
            display = f"{suf[:4]}-{suf[4:6]}-{suf[6:8]} {suf[9:11]}:{suf[11:13]}:{suf[13:15]}"
        else:
            display = p.stem
        out.append({"id": p.stem, "display_name": display})
    legacy_path = model_dir / (stem + ".keras")
    if legacy_path.exists() and not any(x["id"] == stem for x in out):
        out.append({"id": stem, "display_name": "Legacy"})
    return out


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
    image_width: int | None = None
    image_height: int | None = None


class SaveOriginRequest(BaseModel):
    """Request body for POST /api/extract/screenshots/save-origin."""

    filename: str
    subdir: str  # labeled/screenshots/regular | labeled/screenshots/blueprint
    origin_x: int
    origin_y: int


@router.get("/api/extract/models")
async def list_models():
    """
    List available box detector models (current checkpoint, timestamped, legacy).
    Returns list of { id, display_name, is_current? } for dropdown.
    """
    return _list_box_detector_models()


class ModelEvaluationStartBody(BaseModel):
    """Optional body for POST /api/extract/model-evaluation/start."""

    model_id: str | None = None
    scope: str = "all"


@router.post("/api/extract/model-evaluation/start")
async def model_evaluation_start(body: ModelEvaluationStartBody | None = None):
    """
    Start a model evaluation task on the worker (metrics + per-image results).
    Poll GET /api/tasks/{task_id} until status is completed or failed; then results
    contain metrics, items, scale_regular, scale_blueprint.
    """
    if body is None:
        body = ModelEvaluationStartBody()
    scope = body.scope if body.scope in ("all", "test") else "all"
    task_id = task_service.create_evaluation_task(
        eval_type="model_evaluation",
        model_id=body.model_id,
        scope=scope,
    )
    return {"task_id": task_id, "status": "pending"}


@router.get("/api/extract/config")
async def get_extract_config():
    """
    Return extract pipeline config from config.yaml (scale and augmentation).
    Used by the frontend for config display and augmentation preview.
    """
    r = config.augment_shifts_regular
    b = config.augment_shifts_blueprint
    return {
        "regular_scale": config.EXTRACT_REGULAR_SCALE,
        "blueprint_scale": config.EXTRACT_BLUEPRINT_SCALE,
        "augment_shift_regular": {"x_neg": r[0], "x_pos": r[1], "y_neg": r[2], "y_pos": r[3]},
        "augment_shift_blueprint": {"x_neg": b[0], "x_pos": b[1], "y_neg": b[2], "y_pos": b[3]},
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


def _serve_cropped_image(path: Path, subdir: str):
    """Load image, apply config crop for subdir (labeled/screenshots/regular or blueprint), return PNG bytes."""
    img = Image.open(path).convert("RGB")
    if subdir == "labeled/screenshots/regular":
        bounds = config.augment_shifts_regular
    elif subdir == "labeled/screenshots/blueprint":
        bounds = config.augment_shifts_blueprint
    else:
        raise HTTPException(status_code=400, detail="Crop only allowed for labeled/screenshots/regular or blueprint")
    x_neg, x_pos, y_neg, y_pos = bounds
    cropped, _, _ = crop_to_inner_rect(img, x_neg, x_pos, y_neg, y_pos)
    buf = io.BytesIO()
    cropped.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


@router.get("/api/extract/screenshots/{filename}/origin")
async def get_screenshot_origin(
    filename: str,
    subdir: str,
):
    """
    Return the saved origin (origin_x, origin_y) for a labeled screenshot.
    Reads the companion .txt file. Returns 404 if the file has no saved origin.
    """
    if subdir not in LABELED_SCREENSHOT_SUBDIRS_WRITABLE:
        raise HTTPException(
            status_code=400,
            detail="subdir must be labeled/screenshots/regular or labeled/screenshots/blueprint",
        )
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    base = (_data_dir() / subdir).resolve()
    path = (base / filename).resolve()
    try:
        path.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    txt_path = path.with_suffix(".txt")
    if not txt_path.exists():
        raise HTTPException(status_code=404, detail="No saved origin for this screenshot")
    try:
        line = txt_path.read_text().strip()
        parts = line.split()
        if len(parts) != 2:
            raise HTTPException(status_code=500, detail="Invalid origin file format")
        origin_x = int(parts[0])
        origin_y = int(parts[1])
    except (OSError, ValueError) as e:
        if isinstance(e, HTTPException):
            raise
        logger.exception("Failed to read origin .txt")
        raise HTTPException(status_code=500, detail="Failed to read origin") from e
    return {"origin_x": origin_x, "origin_y": origin_y}


@router.get("/api/extract/screenshots/{filename}")
async def serve_screenshot(
    filename: str,
    subdir: str = "unlabeled/screenshots",
    crop: bool = False,
):
    """Serve a single screenshot image. If crop=true and subdir is labeled/screenshots/regular or blueprint, return cropped image (matches training preview coords)."""
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = _screenshot_path(filename, subdir)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Screenshot not found")
    if crop and subdir in ("labeled/screenshots/regular", "labeled/screenshots/blueprint"):
        body = _serve_cropped_image(path, subdir)
        return Response(content=body, media_type="image/png")
    return FileResponse(path, media_type="image/png")


def _stat_icons_unlabeled_dir() -> Path:
    """Return path to data/unlabeled/stat_icons."""
    return (_data_dir() / "unlabeled" / "stat_icons").resolve()


def _stat_icons_labeled_base() -> Path:
    """Return path to data/labeled/icons."""
    return (_data_dir() / "labeled" / "icons").resolve()


def _stat_icon_filename_safe(filename: str) -> None:
    """Raise if filename is invalid (path traversal)."""
    if "/" in filename or "\\" in filename or not filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if Path(filename).suffix.lower() not in (".png", ".jpg", ".jpeg"):
        raise HTTPException(status_code=400, detail="Invalid filename")


def _find_stat_icon_path(filename: str) -> tuple[Path, str | None]:
    """
    Find stat icon file by filename. Look in unlabeled first, then in each labeled/icons/<type>/.
    Returns (absolute_path, current_stat_type_or_None).
    Raises HTTPException if not found.
    """
    _stat_icon_filename_safe(filename)
    unlabeled_dir = _stat_icons_unlabeled_dir()
    unlabeled_path = (unlabeled_dir / filename).resolve()
    try:
        unlabeled_path.relative_to(unlabeled_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if unlabeled_path.exists() and unlabeled_path.is_file():
        return (unlabeled_path, None)
    labeled_base = _stat_icons_labeled_base()
    if labeled_base.exists():
        for subdir in labeled_base.iterdir():
            if subdir.is_dir() and subdir.name in VALID_STAT_TYPES:
                path = (subdir / filename).resolve()
                try:
                    path.relative_to(subdir)
                except ValueError:
                    continue
                if path.exists() and path.is_file():
                    return (path, subdir.name)
    raise HTTPException(status_code=404, detail="Stat icon not found")


@router.get("/api/extract/stat-types")
async def get_stat_types():
    """Return stat type keys for the UI (STAT_GROUPS + none)."""
    return {"stat_types": list(StatNormalizer.STAT_GROUPS.keys()) + ["none"]}


def _list_all_stat_icon_items() -> list[dict]:
    """Build list of all stat icon items: { filename, stat_type } (stat_type null if unlabeled)."""
    seen: set[str] = set()
    items: list[dict] = []
    unlabeled_dir = _stat_icons_unlabeled_dir()
    if unlabeled_dir.exists():
        for p in sorted(unlabeled_dir.iterdir()):
            if p.suffix.lower() == ".png" and p.is_file():
                name = p.name
                if name not in seen:
                    seen.add(name)
                    items.append({"filename": name, "stat_type": None})
    labeled_base = _stat_icons_labeled_base()
    if labeled_base.exists():
        for subdir in sorted(labeled_base.iterdir()):
            if subdir.is_dir() and subdir.name in VALID_STAT_TYPES:
                for p in sorted(subdir.iterdir()):
                    if p.suffix.lower() in (".png", ".jpg", ".jpeg") and p.is_file():
                        name = p.name
                        if name not in seen:
                            seen.add(name)
                            items.append({"filename": name, "stat_type": subdir.name})
    items.sort(key=lambda x: x["filename"])
    return items


@router.get("/api/extract/stat-icons/unlabeled")
async def list_unlabeled_stat_icons():
    """List PNG filenames in data/unlabeled/stat_icons (kept for backwards compatibility)."""
    items = _list_all_stat_icon_items()
    filenames = [x["filename"] for x in items if x["stat_type"] is None]
    return {"filenames": filenames}


@router.get("/api/extract/stat-icons/list")
async def list_all_stat_icons():
    """List all stat icons (unlabeled and labeled) with current label. For navigation and re-labeling."""
    return {"items": _list_all_stat_icon_items()}


@router.get("/api/extract/stat-icons/{filename}")
async def serve_stat_icon(filename: str):
    """Serve a stat icon image from unlabeled/stat_icons or labeled/icons/<type>/."""
    path, _ = _find_stat_icon_path(filename)
    return FileResponse(path, media_type="image/png")


class SaveStatIconLabelRequest(BaseModel):
    """Request body for POST /api/extract/stat-icons/save-label."""

    filename: str
    stat_type: str


@router.post("/api/extract/stat-icons/save-label")
async def save_stat_icon_label(body: SaveStatIconLabelRequest):
    """
    Set stat icon label: move from unlabeled to labeled, or move between labeled dirs (re-label).
    File is found in unlabeled/stat_icons or labeled/icons/<any_type>/.
    """
    if body.stat_type not in VALID_STAT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid stat_type; must be one of {sorted(VALID_STAT_TYPES)}")
    try:
        src, current_type = _find_stat_icon_path(body.filename)
    except HTTPException:
        raise
    dest_dir = (_data_dir() / "labeled" / "icons" / body.stat_type).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = (dest_dir / body.filename).resolve()
    try:
        dest.relative_to(dest_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if src == dest:
        return {"ok": True}
    try:
        src.rename(dest)
    except OSError as e:
        logger.exception("Failed to move stat icon")
        if getattr(e, "errno", None) == 30:
            raise HTTPException(
                status_code=503,
                detail="The data directory is read-only. Mount the data volume with write access.",
            ) from e
        raise HTTPException(status_code=500, detail="Failed to save label") from e
    return {"ok": True}


# Valid digit labels for digit labeling: 0-9 plus "none" (artifact)
VALID_DIGIT_LABELS = frozenset("0123456789") | {"none"}


def _numbers_unlabeled_dir() -> Path:
    """Return path to data/unlabeled/numbers."""
    return (_data_dir() / "unlabeled" / "numbers").resolve()


def _numbers_labeled_base() -> Path:
    """Return path to data/labeled/numbers."""
    return (_data_dir() / "labeled" / "numbers").resolve()


def _digit_filename_safe(filename: str) -> None:
    """Raise if filename is invalid (path traversal)."""
    if "/" in filename or "\\" in filename or not filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if Path(filename).suffix.lower() != ".png":
        raise HTTPException(status_code=400, detail="Invalid filename")


def _find_digit_path(filename: str) -> tuple[Path, str | None]:
    """
    Find digit file by filename. Look in unlabeled first, then in each labeled/numbers/<label>/.
    Returns (absolute_path, current_digit_label_or_None).
    Raises HTTPException if not found.
    """
    _digit_filename_safe(filename)
    unlabeled_dir = _numbers_unlabeled_dir()
    unlabeled_path = (unlabeled_dir / filename).resolve()
    try:
        unlabeled_path.relative_to(unlabeled_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if unlabeled_path.exists() and unlabeled_path.is_file():
        return (unlabeled_path, None)
    labeled_base = _numbers_labeled_base()
    if labeled_base.exists():
        for subdir in sorted(labeled_base.iterdir()):
            if subdir.is_dir() and subdir.name in VALID_DIGIT_LABELS:
                path = (subdir / filename).resolve()
                try:
                    path.relative_to(subdir)
                except ValueError:
                    continue
                if path.exists() and path.is_file():
                    return (path, subdir.name)
    raise HTTPException(status_code=404, detail="Digit image not found")


def _list_all_digit_items() -> list[dict]:
    """Build list of all digit items: { filename, digit_label } (digit_label null if unlabeled)."""
    seen: set[str] = set()
    items: list[dict] = []
    unlabeled_dir = _numbers_unlabeled_dir()
    if unlabeled_dir.exists():
        for p in sorted(unlabeled_dir.iterdir()):
            if p.suffix.lower() == ".png" and p.is_file():
                name = p.name
                if name not in seen:
                    seen.add(name)
                    items.append({"filename": name, "digit_label": None})
    labeled_base = _numbers_labeled_base()
    if labeled_base.exists():
        for subdir in sorted(labeled_base.iterdir()):
            if subdir.is_dir() and subdir.name in VALID_DIGIT_LABELS:
                for p in sorted(subdir.iterdir()):
                    if p.suffix.lower() == ".png" and p.is_file():
                        name = p.name
                        if name not in seen:
                            seen.add(name)
                            items.append({"filename": name, "digit_label": subdir.name})
    items.sort(key=lambda x: x["filename"])
    return items


@router.get("/api/extract/digits/list")
async def list_all_digits():
    """List all digit images (unlabeled and labeled) with current label. For navigation and re-labeling."""
    return {"items": _list_all_digit_items()}


@router.get("/api/extract/digits/{filename}")
async def serve_digit(filename: str):
    """Serve a digit image from unlabeled/numbers or labeled/numbers/<label>/."""
    path, _ = _find_digit_path(filename)
    return FileResponse(path, media_type="image/png")


class SaveDigitLabelRequest(BaseModel):
    """Request body for POST /api/extract/digits/save-label."""

    filename: str
    digit_label: str


@router.post("/api/extract/digits/save-label")
async def save_digit_label(body: SaveDigitLabelRequest):
    """
    Set digit label: move from unlabeled to labeled, or move between labeled dirs (re-label).
    File is found in unlabeled/numbers or labeled/numbers/<any_label>/.
    """
    if body.digit_label not in VALID_DIGIT_LABELS:
        raise HTTPException(
            status_code=400, detail=f"Invalid digit_label; must be one of {sorted(VALID_DIGIT_LABELS)}"
        )
    try:
        src, _ = _find_digit_path(body.filename)
    except HTTPException:
        raise
    dest_dir = (_data_dir() / "labeled" / "numbers" / body.digit_label).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = (dest_dir / body.filename).resolve()
    try:
        dest.relative_to(dest_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if src == dest:
        return {"ok": True}
    try:
        src.rename(dest)
    except OSError as e:
        logger.exception("Failed to move digit image")
        if getattr(e, "errno", None) == 30:
            raise HTTPException(
                status_code=503,
                detail="The data directory is read-only. Mount the data volume with write access.",
            ) from e
        raise HTTPException(status_code=500, detail="Failed to save label") from e
    return {"ok": True}


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
    result: dict = {"boxes": boxes}
    if (
        body.image_width is not None
        and body.image_height is not None
        and body.image_width > 0
        and body.image_height > 0
    ):
        bounds = (
            config.augment_shifts_blueprint
            if body.image_type == "blueprint"
            else config.augment_shifts_regular
        )
        scale = (
            config.EXTRACT_BLUEPRINT_SCALE
            if body.image_type == "blueprint"
            else config.EXTRACT_REGULAR_SCALE
        )
        result["translation_margin_lines"] = compute_translation_margin_lines(
            origin_x=body.origin_x,
            origin_y=body.origin_y,
            image_w=body.image_width,
            image_h=body.image_height,
            x_neg=bounds[0],
            x_pos=bounds[1],
            y_neg=bounds[2],
            y_pos=bounds[3],
            scale=scale,
            image_type=body.image_type,
        )
    return result


class TrainingStartRequest(BaseModel):
    """Request body for POST /api/extract/training/start."""

    model_type: str = "box_detector"
    resume_from_existing: bool = False
    training_epochs: int | None = None
    initial_learning_rate: float | None = None


def _training_params_path() -> Path:
    """Path to training_params.json (saved by task processor for resume defaults)."""
    return _data_dir() / "models" / "box_detector" / "training_params.json"


@router.get("/api/extract/training/params")
async def training_params():
    """
    Return training_epochs and initial_learning_rate for the UI (resume defaults).
    Reads from data/models/box_detector/training_params.json if present, else config defaults.
    """
    path = _training_params_path()
    if path.exists():
        try:
            with open(path) as f:
                data = json.load(f)
            return {
                "training_epochs": max(1, int(data.get("training_epochs", config.TRAINING_EPOCHS))),
                "initial_learning_rate": float(data.get("initial_learning_rate", config.INITIAL_LEARNING_RATE)),
            }
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            pass
    return {
        "training_epochs": config.TRAINING_EPOCHS,
        "initial_learning_rate": config.INITIAL_LEARNING_RATE,
    }


@router.get("/api/extract/training/current")
async def training_current():
    """
    Return the current training task id if one is pending or processing, else null.
    Used by the run_training_until_100_and_shutdown script to attach to an existing
    task instead of starting a new one (which would cancel the current task).
    """
    task_id = task_service.get_current_training_task_id()
    return {"task_id": task_id}


@router.post("/api/extract/training/start")
async def training_start(body: TrainingStartRequest | None = None):
    """
    Start a training task (box_detector or icon_type). Returns task_id to poll via GET /api/tasks/{task_id}.
    Body is optional; default model_type is box_detector.
    Optional training_epochs and initial_learning_rate override config / saved params.
    """
    model_type = (body.model_type if body is not None else "box_detector") or "box_detector"
    if model_type not in ("box_detector", "icon_type"):
        raise HTTPException(
            status_code=400,
            detail="model_type must be 'box_detector' or 'icon_type'",
        )
    resume_from_existing = body.resume_from_existing if body is not None else False
    training_epochs = body.training_epochs if body is not None else None
    initial_learning_rate = body.initial_learning_rate if body is not None else None
    try:
        task_id = task_service.create_training_task(
            model_type=model_type,
            resume_from_existing=resume_from_existing,
            training_epochs=training_epochs,
            initial_learning_rate=initial_learning_rate,
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
