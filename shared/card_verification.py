"""
Full-card verification: given an image and origin, extract stats, armor set, and level.

Script-callable; no HTTP or FastAPI dependencies. Used by the API and by future
scripts that run over a data folder.
"""

from __future__ import annotations

import base64
import io
import logging
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

from shared.armor_sets import SET_TYPES
from shared.extract_regions import compute_boxes
from shared.stat_normalizer import StatNormalizer

# Input size for icon and digit models (matches training)
STAT_INPUT_H = 56
STAT_INPUT_W = 56

# Icon type classes: stat types + "none", stable order
ICON_CLASS_NAMES: list[str] = sorted(StatNormalizer.STAT_GROUPS.keys()) + ["none"]

# Digit classes: 0-9 then "none"
DIGIT_CLASS_NAMES: list[str] = [str(d) for d in range(10)] + ["none"]

# Min fuzzywuzzy ratio to accept armor set match (legacy MIN_LEVENSHTEIN)
SET_MATCH_MIN_RATIO = 65


@dataclass
class VerificationResult:
    """Result of verifying a single card image."""

    armor_set: str | None
    current_level: int | None
    max_level: int | None
    stats: dict[str, int]
    error: str | None
    debug: dict[str, Any] | None = None


def verify_card(
    image: np.ndarray | Path | str,
    origin_x: int,
    origin_y: int,
    scale: float,
    image_type: str,
    *,
    data_dir: Path | None = None,
    icon_model_path: Path | str | None = None,
    digit_model_path: Path | str | None = None,
    return_debug: bool = False,
) -> VerificationResult:
    """
    Run the full card verification pipeline on one image.

    Args:
        image: Full screenshot as file path or RGB numpy array (H, W, 3).
        origin_x, origin_y: Top-left of armor tab (first card) in image coords.
        scale: Scale factor (e.g. from config).
        image_type: "regular" or "blueprint".
        data_dir: Data root for resolving model paths. Defaults to repo/data.
        icon_model_path: Override path to icon type model file.
        digit_model_path: Override path to digit detector model file.

    Returns:
        VerificationResult with armor_set, level, stats; error set on partial failure.
    """
    if data_dir is None:
        data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir = Path(data_dir).resolve()

    errors: list[str] = []
    armor_set: str | None = None
    current_level: int | None = None
    max_level: int | None = None
    stats: dict[str, int] = {}

    img = _load_image(image)
    if img is None:
        return VerificationResult(
            armor_set=None,
            current_level=None,
            max_level=None,
            stats={},
            error="Failed to load image",
            debug=None,
        )

    boxes = compute_boxes(origin_x, origin_y, scale, image_type)
    by_type: dict[str, list[dict]] = {}
    for b in boxes:
        by_type.setdefault(b["type"], []).append(b)

    stat_boxes = by_type.get("stat", [])
    set_boxes = by_type.get("set", [])
    level_boxes = by_type.get("level", [])

    # Crops for debug (computed when return_debug regardless of model success)
    set_crop: np.ndarray | None = None
    set_crop_processed: np.ndarray | None = None
    level_merged: np.ndarray | None = None
    stat_crops: list[np.ndarray] = []
    stat_crops_56: list[np.ndarray] = []

    # Stat types and values
    icon_path = _resolve_icon_model_path(data_dir) if icon_model_path is None else Path(icon_model_path)
    digit_path = _resolve_digit_model_path(data_dir) if digit_model_path is None else Path(digit_model_path)

    if icon_path is not None and icon_path.exists():
        icon_model = _load_keras_model(icon_path)
        if icon_model is not None:
            stat_crops = [_crop_box(img, b) for b in stat_boxes]
            stat_crops_56 = [_resize_stat_crop(c) for c in stat_crops]
            if stat_crops_56:
                X = np.stack(stat_crops_56).astype(np.float32) / 255.0
                preds = icon_model.predict(X, verbose=0)
                pred_indices = np.argmax(preds, axis=-1)
                num_classes = preds.shape[-1]
                for i, idx in enumerate(pred_indices):
                    idx = int(idx)
                    if idx < len(ICON_CLASS_NAMES) and idx < num_classes:
                        stat_type = ICON_CLASS_NAMES[idx]
                        if stat_type != "none" and i < len(stat_crops):
                            value = _read_stat_value(
                                stat_crops[i],
                                digit_model_path=digit_path,
                                data_dir=data_dir,
                            )
                            if value is not None:
                                stats[stat_type] = value
        else:
            errors.append("Failed to load icon type model")
    else:
        errors.append("Icon type model not found")

    # When return_debug but no icon model, still compute stat crops for region/preprocess display
    if return_debug and not stat_crops and stat_boxes:
        stat_crops = [_crop_box(img, b) for b in stat_boxes]
        stat_crops_56 = [_resize_stat_crop(c) for c in stat_crops]

    # Armor set (OCR + fuzzy match)
    ocr_set_text = ""
    ocr_set_error = ""
    if set_boxes:
        set_crop = _crop_box(img, set_boxes[0])
        if set_crop is not None and set_crop.size > 0:
            set_crop_processed = _preprocess_set_image(set_crop)
            armor_set, ocr_set_text, ocr_set_error = _read_armor_set(set_crop)
    if armor_set is None and set_boxes:
        errors.append("Could not read armor set")
        if return_debug and (set_crop is None or set_crop.size == 0):
            set_crop = _crop_box(img, set_boxes[0])
            if set_crop is not None and set_crop.size > 0:
                set_crop_processed = _preprocess_set_image(set_crop)

    # Level (merge, legacy cyan-based preprocessing, then OCR. Expected format "1 / 16".)
    ocr_level_text = ""
    ocr_level_error = ""
    level_processed: np.ndarray | None = None
    if level_boxes:
        level_merged = _merge_level_crops(img, level_boxes)
        if level_merged is not None:
            level_processed = _preprocess_level_image(level_merged)
            current_level, max_level, ocr_level_text, ocr_level_error = _read_level_from_merged(level_merged)
    if current_level is None and level_boxes:
        errors.append("Could not read level")

    debug: dict[str, Any] | None = None
    if return_debug:
        debug = {}
        if set_crop is not None and set_crop.size > 0:
            debug["region_set"] = _encode_image_b64(set_crop)
        if set_crop_processed is not None:
            debug["preprocess_set"] = _encode_image_b64(set_crop_processed)
        debug["ocr_set"] = ocr_set_text
        if ocr_set_error:
            debug["ocr_set_error"] = ocr_set_error
        if level_merged is not None:
            debug["region_level"] = _encode_image_b64(level_merged)
            if level_processed is not None:
                debug["preprocess_level"] = _encode_image_b64(level_processed)
        debug["ocr_level"] = ocr_level_text
        if ocr_level_error:
            debug["ocr_level_error"] = ocr_level_error
        if stat_crops:
            debug["region_stat_crops"] = [_encode_image_b64(c) for c in stat_crops]
        if stat_crops_56:
            debug["preprocess_stat_crops"] = [_encode_image_b64(c) for c in stat_crops_56]

    return VerificationResult(
        armor_set=armor_set,
        current_level=current_level,
        max_level=max_level,
        stats=stats,
        error="; ".join(errors) if errors else None,
        debug=debug,
    )


def _encode_image_b64(arr: np.ndarray) -> str:
    """Encode RGB numpy array (H, W, 3) as base64 PNG."""
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _merge_level_crops(img: np.ndarray, level_boxes: list[dict]) -> np.ndarray | None:
    """Merge level region crops into one horizontal strip (same as used for OCR). Returns RGB array or None."""
    crops = [_crop_box(img, b) for b in level_boxes]
    crops = [c for c in crops if c is not None and c.size > 0]
    if not crops:
        return None
    h = max(c.shape[0] for c in crops)
    total_w = sum(c.shape[1] for c in crops)
    merged = np.ones((h, total_w, 3), dtype=np.uint8) * 255
    x_off = 0
    for c in crops:
        merged[: c.shape[0], x_off : x_off + c.shape[1]] = c
        x_off += c.shape[1]
    return merged


def _load_image(image: np.ndarray | Path | str) -> np.ndarray | None:
    """Load image to RGB numpy array. Path/str loaded via PIL."""
    if isinstance(image, np.ndarray):
        if image.ndim == 3 and image.shape[2] == 3:
            return image
        return None
    path = Path(image)
    if not path.exists():
        return None
    try:
        from PIL import Image
        img = Image.open(path).convert("RGB")
        return np.array(img, dtype=np.uint8)
    except Exception:
        return None


def _crop_box(img: np.ndarray, box: dict) -> np.ndarray | None:
    """Extract region from image; clamp to bounds. Returns RGB crop or None if empty."""
    h, w = img.shape[:2]
    x = int(box["x"])
    y = int(box["y"])
    bw = int(box["width"])
    bh = int(box["height"])
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(w, x + bw)
    y2 = min(h, y + bh)
    if x1 >= x2 or y1 >= y2:
        return None
    return img[y1:y2, x1:x2].copy()


def _resize_stat_crop(crop: np.ndarray | None) -> np.ndarray:
    """Resize stat crop to STAT_INPUT_H x STAT_INPUT_W RGB. Returns zeros if crop is None or tiny."""
    if crop is None or crop.size == 0:
        return np.zeros((STAT_INPUT_H, STAT_INPUT_W, 3), dtype=np.uint8)
    from PIL import Image
    pil = Image.fromarray(crop).resize((STAT_INPUT_W, STAT_INPUT_H))
    return np.array(pil, dtype=np.uint8)


def _resolve_icon_model_path(data_dir: Path) -> Path | None:
    """Resolve icon type model: stem_current.keras, then latest timestamped, then stem.keras."""
    model_dir = data_dir / "models" / "icon_type_detection"
    stem = "icon_type_detector_model"
    current = model_dir / f"{stem}_current.keras"
    if current.exists():
        return current
    timestamped = sorted(
        model_dir.glob(f"{stem}_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9].keras"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if timestamped:
        return timestamped[0]
    legacy = model_dir / f"{stem}.keras"
    if legacy.exists():
        return legacy
    return None


def _resolve_digit_model_path(data_dir: Path) -> Path | None:
    """Resolve digit model: stem_current.keras, then latest timestamped, then stem.keras."""
    model_dir = data_dir / "models" / "digit_detection"
    stem = "digit_detector_model"
    current = model_dir / f"{stem}_current.keras"
    if current.exists():
        return current
    timestamped = sorted(
        model_dir.glob(f"{stem}_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9].keras"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if timestamped:
        return timestamped[0]
    legacy = model_dir / f"{stem}.keras"
    if legacy.exists():
        return legacy
    return None


def _load_keras_model(load_path: Path) -> Any | None:
    """Load Keras model from path (temp copy). Returns None on failure."""
    load_path = Path(load_path).resolve()
    if not load_path.exists():
        return None
    try:
        from tensorflow import keras
        is_keras_zip = zipfile.is_zipfile(load_path)
        suffix = ".keras" if is_keras_zip else ".h5"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            tmp_path = Path(f.name)
        try:
            shutil.copy2(load_path, tmp_path)
            compile_load = is_keras_zip
            return keras.models.load_model(str(tmp_path), compile=compile_load)
        finally:
            tmp_path.unlink(missing_ok=True)
    except Exception:
        return None


def _read_stat_value(
    stat_crop: np.ndarray,
    *,
    digit_model_path: Path | None = None,
    data_dir: Path | None = None,
) -> int | None:
    """Extract digits from stat crop, run digit model, combine into one number."""
    from shared.stat_digit_extract import extract_digits

    if stat_crop.shape[0] != STAT_INPUT_H or stat_crop.shape[1] != STAT_INPUT_W:
        from PIL import Image
        pil = Image.fromarray(stat_crop).resize((STAT_INPUT_W, STAT_INPUT_H))
        stat_crop = np.array(pil, dtype=np.uint8)
    bgr = stat_crop[:, :, ::-1].copy()
    digit_imgs = extract_digits(bgr)
    if not digit_imgs:
        return None
    if data_dir is None:
        data_dir = Path(__file__).resolve().parent.parent / "data"
    digit_path = digit_model_path if digit_model_path is not None else _resolve_digit_model_path(Path(data_dir))
    if digit_path is None or not Path(digit_path).exists():
        return None
    model = _load_keras_model(Path(digit_path))
    if model is None:
        return None
    # Prepare digit inputs: 56x56 RGB [0,1]
    X_list = []
    for d_img in digit_imgs:
        rgb = d_img[:, :, ::-1]
        from PIL import Image
        pil = Image.fromarray(rgb).resize((STAT_INPUT_W, STAT_INPUT_H))
        arr = np.array(pil, dtype=np.float32) / 255.0
        X_list.append(arr)
    X = np.stack(X_list)
    preds = model.predict(X, verbose=0)
    indices = np.argmax(preds, axis=-1)
    num = 0
    for idx in indices:
        idx = int(idx)
        if idx <= 9:
            num = num * 10 + idx
    return num if num > 0 or len(indices) > 0 else None


def _read_armor_set(set_crop: np.ndarray) -> tuple[str | None, str, str]:
    """Preprocess set crop, OCR with pytesseract, fuzzy match to SET_TYPES. Returns (matched_name or None, raw_ocr_text, ocr_error)."""
    processed = _preprocess_set_image(set_crop)
    try:
        import pytesseract
        from PIL import Image
        guess = pytesseract.image_to_string(Image.fromarray(processed)).strip()
    except Exception as e:
        logger.exception("OCR failed for armor set crop")
        return None, "", str(e)
    if not guess:
        return None, "", ""
    try:
        from fuzzywuzzy import fuzz
    except ImportError:
        return None, guess, ""
    best_ratio = 0
    best_name: str | None = None
    for name in SET_TYPES:
        r = fuzz.ratio(name.lower(), guess.lower())
        if r > best_ratio:
            best_ratio = r
            best_name = name
    if best_name is not None and best_ratio >= SET_MATCH_MIN_RATIO:
        return best_name, guess, ""
    return None, guess, ""


def _preprocess_set_image(img: np.ndarray) -> np.ndarray:
    """Binarize: white pixels -> black, rest -> white (legacy set preprocess). Expects RGB."""
    out = np.empty_like(img)
    white_thresh = 180
    for y in range(img.shape[0]):
        for x in range(img.shape[1]):
            r, g, b = img[y, x, 0], img[y, x, 1], img[y, x, 2]
            if r > white_thresh and g > white_thresh and b > white_thresh and r == g == b:
                out[y, x] = [0, 0, 0]
            else:
                out[y, x] = [255, 255, 255]
    return out


# Legacy PreProcessLevel constants (preprocess_level.py / preprocess.py)
_LEVEL_WHITE_VALUE_THRESHOLD = 180
_LEVEL_CYAN_RED_DIFF_THRESHOLD = 30


def _preprocess_level_image(img: np.ndarray) -> np.ndarray:
    """
    Binarize level image like legacy PreProcessLevel: cyan pixels -> black, rest -> white.
    Expects RGB. Matches legacy extract_gear/preprocess_level.py (is_cyan: blue > 180,
    blue == green, |blue - red| > 30).
    """
    out = np.empty_like(img)
    for y in range(img.shape[0]):
        for x in range(img.shape[1]):
            r, g, b = img[y, x, 0], img[y, x, 1], img[y, x, 2]
            if (
                b > _LEVEL_WHITE_VALUE_THRESHOLD
                and b == g
                and (b - r if b > r else r - b) > _LEVEL_CYAN_RED_DIFF_THRESHOLD
            ):
                out[y, x] = [0, 0, 0]
            else:
                out[y, x] = [255, 255, 255]
    return out


def _read_level_from_merged(merged: np.ndarray) -> tuple[int | None, int | None, str, str]:
    """
    Extract level from merged level image. Uses legacy cyan-based binarization
    (PreProcessLevel: cyan -> black, rest -> white). Expected format: "1 / 16" (current / max).
    Returns (current_level, max_level, raw_ocr_text, ocr_error).
    """
    processed = _preprocess_level_image(merged)
    try:
        import pytesseract
        from PIL import Image
        pil = Image.fromarray(processed)
        text = pytesseract.image_to_string(pil).strip()
    except ImportError:
        return None, None, "", "pytesseract or PIL not installed"
    except Exception as e:
        logger.exception("OCR failed for level crop")
        return None, None, "", str(e)
    # Parse "X/Y" or "X / Y" or two numbers
    match = re.search(r"(\d+)\s*/\s*(\d+)", text)
    if match:
        return int(match.group(1)), int(match.group(2)), text, ""
    nums = re.findall(r"\d+", text)
    if len(nums) >= 2:
        return int(nums[0]), int(nums[1]), text, ""
    if len(nums) == 1:
        return int(nums[0]), None, text, ""
    return None, None, text, ""
