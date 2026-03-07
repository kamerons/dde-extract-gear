"""Evaluation processor: load box detector model and run evaluate or preview.

Used by the task worker for evaluation_tasks. Resolves load path, loads model
with .keras vs HDF5 format detection and logging, then runs evaluate (metrics)
or preview (test set items with predictions).
"""

import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

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


def run_evaluate(
    data_dir: Path,
    test_ratio: float,
    shift_regular: float,
    shift_blueprint: float,
    fill_mode: str,
    augment_count: int,
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
    _, test_sources = _split_train_test(sources, test_ratio)
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


def run_preview(
    data_dir: Path,
    test_ratio: float,
    shift_regular: float,
    shift_blueprint: float,
    fill_mode: str,
    augment_count: int,
    scale_regular: float,
    scale_blueprint: float,
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
    _, test_sources = _split_train_test(sources, test_ratio)
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

    X_test, _ = _build_arrays(
        test_sources,
        augment=False,
        shift_regular=shift_regular,
        shift_blueprint=shift_blueprint,
        fill_mode=fill_mode,
        augment_count=augment_count,
    )
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
        "scale_regular": scale_regular,
        "scale_blueprint": scale_blueprint,
        "model_format": format_str,
    }
