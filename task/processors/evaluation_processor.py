"""Evaluation processor: load box detector model and run evaluate or preview.

Used by the task worker for evaluation_tasks. Resolves load path, loads model
with .keras vs HDF5 format detection and logging, then runs evaluate (metrics)
or preview (test set items with predictions). Preview includes augmented test
samples with embedded images so the frontend can show model performance on each.
"""

import base64
import io
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from shared.box_detector_augment import augment_sample_label_aware, crop_to_inner_rect
from shared.extract_regions import compute_boxes
from task.processors.box_detector_processor import (
    INPUT_HEIGHT,
    INPUT_WIDTH,
    _build_arrays,
    _compute_test_metrics,
    _labeled_dirs,
    _load_image,
    _scan_sources,
    _split_train_test,
)

logger = logging.getLogger(__name__)


def _box_detector_load_path(data_dir: Path, model_path: str) -> tuple[Path | None, Path, str]:
    """
    Path to load for box detector: _current, latest timestamped, or legacy stem.keras.
    Returns (load_path or None, model_dir, stem).
    """
    model_dir = (data_dir / "models" / "box_detector").resolve()
    stem = Path(model_path).name
    if stem.endswith(".keras") or stem.endswith(".h5"):
        stem = Path(stem).stem
    current_path = model_dir / (stem + "_current.keras")
    legacy_path = model_dir / (stem + ".keras")

    if current_path.exists():
        return (current_path, model_dir, stem)
    timestamped = sorted(
        model_dir.glob(f"{stem}_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9].keras"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if timestamped:
        return (timestamped[0], model_dir, stem)
    if legacy_path.exists():
        return (legacy_path, model_dir, stem)
    return (None, model_dir, stem)


def _load_box_detector_model(load_path: Path) -> tuple[Any, str]:
    """
    Load Keras model from path. Uses temp copy for reliability.
    Detects .keras zip vs HDF5, logs format, returns (model, format_str).
    format_str is "keras" or "hdf5".
    """
    from tensorflow import keras

    is_keras_zip = zipfile.is_zipfile(load_path)
    format_str = "keras" if is_keras_zip else "hdf5"
    logger.info(
        "Loading box detector model from %s (format: %s)",
        load_path,
        ".keras zip" if is_keras_zip else "HDF5",
    )

    suffix = ".keras" if is_keras_zip else ".h5"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        tmp_path = Path(f.name)
    try:
        shutil.copy2(load_path, tmp_path)
        compile_load = is_keras_zip
        model = keras.models.load_model(str(tmp_path), compile=compile_load)
        return (model, format_str)
    finally:
        tmp_path.unlink(missing_ok=True)


def _image_to_data_url(pil_img: Image.Image) -> str:
    """Encode PIL image as PNG data URL."""
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def build_preview_items(
    model: Any,
    test_sources: list,
    scale_regular: float,
    scale_blueprint: float,
    shift_regular: tuple[float, float, float, float],
    shift_blueprint: tuple[float, float, float, float],
    fill_mode: str,
    augment_count: int,
) -> tuple[list[dict], float, float]:
    """
    Build preview items from an already-loaded model and test sources.
    Generates augment_count augmented samples per test source (same as training),
    runs the model on each, and returns one item per augmented sample with
    image_data_url so the frontend can show each augment and its GT/pred.
    Origin and prediction are in the augmented (cropped) image space.
    Returns (items, scale_regular, scale_blueprint).
    """
    samples = []  # (aug_img, origin_x, origin_y, filename, subdir, augment_index)
    X_list = []
    for typename, filename, png_path, ox, oy in test_sources:
        img = _load_image(png_path)
        x_neg, x_pos, y_neg, y_pos = shift_regular if typename == "regular" else shift_blueprint
        cropped, crop_left, crop_top = crop_to_inner_rect(img, x_neg, x_pos, y_neg, y_pos)
        cw, ch = cropped.size
        origin_crop_x = ox - crop_left
        origin_crop_y = oy - crop_top
        scale_x = INPUT_WIDTH / cw
        scale_y = INPUT_HEIGHT / ch
        subdir = f"labeled/screenshots/{typename}"
        image_type_here = typename
        scale_here = scale_blueprint if typename == "blueprint" else scale_regular
        for aug_idx, (aug_img, new_ox, new_oy) in enumerate(
            augment_sample_label_aware(
                cropped,
                origin_crop_x,
                origin_crop_y,
                x_neg,
                x_pos,
                y_neg,
                y_pos,
                fill_mode,
                augment_count,
                scale=scale_here,
                image_type=image_type_here,
            )
        ):
            samples.append((aug_img, new_ox, new_oy, filename, subdir, aug_idx + 1))
            arr = np.array(aug_img.resize((INPUT_WIDTH, INPUT_HEIGHT)), dtype=np.float32) / 255.0
            X_list.append(arr)
    if not X_list:
        return ([], scale_regular, scale_blueprint)
    X_test = np.stack(X_list)
    pred = model.predict(X_test, verbose=0)

    items = []
    for i, (aug_img, orig_x, orig_y, filename, subdir, aug_idx) in enumerate(samples):
        cw, ch = aug_img.size
        scale_x = INPUT_WIDTH / cw
        scale_y = INPUT_HEIGHT / ch
        pred_x = int(round(float(pred[i, 0]) / scale_x))
        pred_y = int(round(float(pred[i, 1]) / scale_y))
        image_type = "blueprint" if "blueprint" in subdir else "regular"
        scale = scale_blueprint if image_type == "blueprint" else scale_regular
        boxes_gt = compute_boxes(
            origin_x=int(orig_x),
            origin_y=int(orig_y),
            scale=scale,
            image_type=image_type,
        )
        boxes_pred = compute_boxes(
            origin_x=pred_x,
            origin_y=pred_y,
            scale=scale,
            image_type=image_type,
        )
        items.append({
            "filename": filename,
            "subdir": subdir,
            "origin_x": orig_x,
            "origin_y": orig_y,
            "pred_x": pred_x,
            "pred_y": pred_y,
            "boxes_gt": boxes_gt,
            "boxes_pred": boxes_pred,
            "image_data_url": _image_to_data_url(aug_img),
            "augment_index": aug_idx,
        })
    return (items, scale_regular, scale_blueprint)


def run_evaluate(
    data_dir: Path,
    test_ratio: float,
    shift_regular: tuple[float, float, float, float],
    shift_blueprint: tuple[float, float, float, float],
    fill_mode: str,
    augment_count: int,
    test_blueprint_fraction: float = 0.5,
) -> dict[str, Any]:
    """
    Run evaluate: load model, build test set, return metrics dict.
    On error returns {"error": str, "message": str}.
    On success returns metrics with optional "model_format": "keras" | "hdf5".
    """
    from task.config import Config
    config = Config()
    load_path, model_dir, _stem = _box_detector_load_path(data_dir, config.BOX_DETECTOR_MODEL_PATH)
    if load_path is None:
        return {
            "error": "model_not_found",
            "message": f"No box detector model found in {model_dir}. Run training first.",
        }

    labeled = _labeled_dirs(data_dir)
    if not labeled:
        return {"error": "no_labeled_data", "message": "No labeled screenshots found."}
    sources = _scan_sources(labeled)
    if not sources:
        return {"error": "no_sources", "message": "No valid (image, .txt) pairs found."}
    _, test_sources = _split_train_test(sources, test_ratio, test_blueprint_fraction)
    if not test_sources:
        return {"error": "no_test_set", "message": "No test set after split."}

    try:
        model, format_str = _load_box_detector_model(load_path)
    except Exception as e:
        logger.exception("Failed to load box detector model from %s", load_path)
        return {
            "error": "load_failed",
            "message": f"Keras failed to load model: {e!s}",
        }

    X_test, y_test = _build_arrays(
        test_sources,
        augment=True,
        shift_regular=shift_regular,
        shift_blueprint=shift_blueprint,
        fill_mode=fill_mode,
        augment_count=augment_count,
    )
    metrics = _compute_test_metrics(model, X_test, y_test)
    metrics["model_format"] = format_str
    return metrics


def run_evaluate_all_labeled(
    data_dir: Path,
    shift_regular: tuple[float, float, float, float],
    shift_blueprint: tuple[float, float, float, float],
    fill_mode: str,
    augment_count: int,
    scale_regular: float = 1.0,
    scale_blueprint: float = 1.0,
) -> dict[str, Any]:
    """
    Compute metrics for the loaded box detector model on all labeled sources (no train/test split).
    Used by GET /api/extract/model-metrics for "loaded model" accuracy estimate.
    On error returns {"error": str, "message": str}. On success returns metrics dict.
    """
    from task.config import Config
    cfg = Config()
    load_path, model_dir, _stem = _box_detector_load_path(data_dir, cfg.BOX_DETECTOR_MODEL_PATH)
    if load_path is None:
        return {
            "error": "model_not_found",
            "message": f"No box detector model found in {model_dir}. Run training first.",
        }
    labeled = _labeled_dirs(data_dir)
    if not labeled:
        return {"error": "no_labeled_data", "message": "No labeled screenshots found."}
    sources = _scan_sources(labeled)
    if not sources:
        return {"error": "no_sources", "message": "No valid (image, .txt) pairs found."}
    try:
        model, format_str = _load_box_detector_model(load_path)
    except Exception as e:
        logger.exception("Failed to load box detector model from %s", load_path)
        return {
            "error": "load_failed",
            "message": f"Keras failed to load model: {e!s}",
        }
    X_all, y_all = _build_arrays(
        sources,
        augment=True,
        shift_regular=shift_regular,
        shift_blueprint=shift_blueprint,
        fill_mode=fill_mode,
        augment_count=augment_count,
        scale_regular=scale_regular,
        scale_blueprint=scale_blueprint,
    )
    metrics = _compute_test_metrics(model, X_all, y_all)
    metrics["model_format"] = format_str
    return metrics


def run_preview(
    data_dir: Path,
    test_ratio: float,
    shift_regular: tuple[float, float, float, float],
    shift_blueprint: tuple[float, float, float, float],
    fill_mode: str,
    augment_count: int,
    scale_regular: float,
    scale_blueprint: float,
    test_blueprint_fraction: float = 0.5,
) -> dict[str, Any]:
    """
    Run preview: load model, build test set, predict, return items + scales.
    On error returns {"error": str, "message": str}.
    On success returns {"items": [...], "scale_regular": float, "scale_blueprint": float, "model_format": str}.
    """
    from task.config import Config
    config = Config()
    load_path, model_dir, _stem = _box_detector_load_path(data_dir, config.BOX_DETECTOR_MODEL_PATH)
    if load_path is None:
        return {
            "error": "model_not_found",
            "message": f"No box detector model found in {model_dir}. Run training first.",
        }

    labeled = _labeled_dirs(data_dir)
    if not labeled:
        return {"error": "no_labeled_data", "message": "No labeled screenshots found."}
    sources = _scan_sources(labeled)
    if not sources:
        return {"error": "no_sources", "message": "No valid (image, .txt) pairs found."}
    _, test_sources = _split_train_test(sources, test_ratio, test_blueprint_fraction)
    if not test_sources:
        return {"error": "no_test_set", "message": "No test set after split."}

    try:
        model, format_str = _load_box_detector_model(load_path)
    except Exception as e:
        logger.exception("Failed to load box detector model from %s", load_path)
        return {
            "error": "load_failed",
            "message": f"Keras failed to load model: {e!s}",
        }

    items, sr, sb = build_preview_items(
        model,
        test_sources,
        scale_regular,
        scale_blueprint,
        shift_regular,
        shift_blueprint,
        fill_mode,
        augment_count,
    )
    return {
        "items": items,
        "scale_regular": sr,
        "scale_blueprint": sb,
        "model_format": format_str,
    }
