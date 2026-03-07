"""Box detector training processor: regression model for (origin_x, origin_y).

Loads labeled screenshots, fixes train/test split at run start, re-scans each epoch
to add new labels to the training set, augments in-process, and trains for a fixed
number of epochs. Supports progress callback and cancellation.
"""

import logging
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import numpy as np
from PIL import Image

from shared.box_detector_augment import (
    augment_sample,
    read_txt_origin,
)
from shared.recommendation_engine import TaskCancelledError

logger = logging.getLogger(__name__)

# Input size for the model (all images resized to this)
INPUT_HEIGHT = 256
INPUT_WIDTH = 256


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _model_save_path(path: Path) -> Path:
    """Return path with .keras extension so Keras save() accepts it."""
    p = Path(path)
    s = str(p)
    if s.endswith(".keras") or s.endswith(".h5"):
        return p
    return Path(s + ".keras")


def _relax_path_for_host(path: Path, *, is_dir: bool = False) -> None:
    """Set permissions so the host user can read/write/delete (e.g. when running in Docker as root)."""
    try:
        os.chmod(path, 0o777 if is_dir else 0o666)
    except OSError as e:
        logger.warning("Could not chmod %s: %s", path, e)


def _save_model_native(model, path: Path) -> None:
    """Save model in native Keras format (.keras zip) so load_model can read it."""
    from tensorflow import keras
    save_path = _model_save_path(Path(path)) if not str(path).endswith(".keras") else Path(path)
    path_str = str(save_path.resolve())
    # Use extension to drive format: .keras -> zip archive (Keras 3). Avoid save_format="keras"
    # because in some TF 2.x versions it writes legacy HDF5 instead of the zip.
    if hasattr(keras, "saving") and hasattr(keras.saving, "save_model"):
        keras.saving.save_model(model, path_str)
    else:
        # Path must end with .keras so TF 2.15+ writes the zip format, not HDF5.
        model.save(path_str)
    _relax_path_for_host(save_path, is_dir=False)


def _labeled_dirs(data_dir: Path) -> list[tuple[str, Path]]:
    """Return [(typename, path), ...] for labeled/screenshots/regular and blueprint."""
    base = data_dir / "labeled" / "screenshots"
    out = []
    for name in ("regular", "blueprint"):
        p = base / name
        if p.exists():
            out.append((name, p))
    return out


def _scan_sources(labeled_dirs: list[tuple[str, Path]]) -> list[tuple[str, str, Path, int, int]]:
    """Scan dirs for (type, filename, png_path, origin_x, origin_y)."""
    sources = []
    for typename, dirpath in labeled_dirs:
        for png_path in sorted(dirpath.glob("*.png")):
            txt_path = png_path.with_suffix(".txt")
            origin = read_txt_origin(txt_path)
            if origin is None:
                continue
            ox, oy = origin
            sources.append((typename, png_path.name, png_path, ox, oy))
    return sources


def _split_train_test(
    sources: list[tuple[str, str, Path, int, int]],
    test_ratio: float,
) -> tuple[list[tuple[str, str, Path, int, int]], list[tuple[str, str, Path, int, int]]]:
    """Deterministic split: sort by (type, name), take last test_ratio as test."""
    if not sources:
        return [], []
    ordered = sorted(sources, key=lambda s: (s[0], s[1]))
    n = len(ordered)
    n_test = max(0, int(n * test_ratio))
    n_train = n - n_test
    train = ordered[:n_train] if n_train else []
    test = ordered[n_train:] if n_test else []
    return train, test


def _load_image(png_path: Path) -> Image.Image:
    img = Image.open(png_path).convert("RGB")
    return img


def _build_arrays(
    sources: list[tuple[str, str, Path, int, int]],
    augment: bool,
    shift_regular: float,
    shift_blueprint: float,
    fill_mode: str,
    augment_count: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Build X (N, H, W, 3) and y (N, 2) in resized space. Optionally augment train set."""
    X_list = []
    y_list = []
    for typename, _name, png_path, ox, oy in sources:
        img = _load_image(png_path)
        w, h = img.size
        scale_x = INPUT_WIDTH / w
        scale_y = INPUT_HEIGHT / h
        shift_fraction = shift_regular if typename == "regular" else shift_blueprint

        if augment:
            for aug_img, new_ox, new_oy in augment_sample(
                img, ox, oy, shift_fraction, fill_mode, augment_count
            ):
                arr = np.array(aug_img.resize((INPUT_WIDTH, INPUT_HEIGHT)), dtype=np.float32) / 255.0
                X_list.append(arr)
                y_list.append([new_ox * scale_x, new_oy * scale_y])
        else:
            arr = np.array(img.resize((INPUT_WIDTH, INPUT_HEIGHT)), dtype=np.float32) / 255.0
            X_list.append(arr)
            y_list.append([ox * scale_x, oy * scale_y])

    if not X_list:
        return np.zeros((0, INPUT_HEIGHT, INPUT_WIDTH, 3), dtype=np.float32), np.zeros((0, 2), dtype=np.float32)
    return np.stack(X_list), np.array(y_list, dtype=np.float32)


def _build_model():
    """Keras regression model: CNN -> 2 outputs (origin x, y in input space)."""
    from tensorflow import keras
    model = keras.Sequential([
        keras.layers.Conv2D(32, 3, padding="same", activation="relu", input_shape=(INPUT_HEIGHT, INPUT_WIDTH, 3)),
        keras.layers.MaxPool2D(),
        keras.layers.Conv2D(64, 3, padding="same", activation="relu"),
        keras.layers.MaxPool2D(),
        keras.layers.Conv2D(64, 3, padding="same", activation="relu"),
        keras.layers.MaxPool2D(),
        keras.layers.Flatten(),
        keras.layers.Dense(128, activation="relu"),
        keras.layers.Dropout(0.3),
        keras.layers.Dense(2),
    ])
    model.compile(optimizer="adam", loss="mse", metrics=["mae"])
    return model


def _resolve_box_detector_load_path(data_dir: Path, model_path: str) -> Path | None:
    """
    Path to load for box detector: _current, latest timestamped, or legacy stem.keras.
    Returns load_path or None if no file exists.
    """
    model_dir = (data_dir / "models" / "box_detector").resolve()
    stem = Path(model_path).name
    if stem.endswith(".keras") or stem.endswith(".h5"):
        stem = Path(stem).stem
    current_path = model_dir / (stem + "_current.keras")
    legacy_path = model_dir / (stem + ".keras")

    if current_path.exists():
        return current_path
    timestamped = sorted(
        model_dir.glob(f"{stem}_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]_[0-9][0-9][0-9][0-9][0-9][0-9].keras"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if timestamped:
        return timestamped[0]
    if legacy_path.exists():
        return legacy_path
    return None


def _load_existing_model(load_path: Path):
    """Load Keras model from path (temp copy + load_model). Raises on failure."""
    from tensorflow import keras

    is_keras_zip = zipfile.is_zipfile(load_path)
    logger.info(
        "Loading existing box detector model from %s (format: %s)",
        load_path,
        ".keras zip" if is_keras_zip else "HDF5",
    )
    suffix = ".keras" if is_keras_zip else ".h5"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        tmp_path = Path(f.name)
    try:
        shutil.copy2(load_path, tmp_path)
        compile_load = is_keras_zip
        return keras.models.load_model(str(tmp_path), compile=compile_load)
    finally:
        tmp_path.unlink(missing_ok=True)


def _compute_test_metrics(model, X_test: np.ndarray, y_test: np.ndarray) -> dict:
    """Predict on test set; scale back to pixel space and compute MAE (in input 256 space for simplicity)."""
    if len(X_test) == 0:
        return {"test_mae_x": 0.0, "test_mae_y": 0.0, "accuracy_within_5px": 0.0}
    pred = model.predict(X_test, verbose=0)
    mae_x = float(np.mean(np.abs(pred[:, 0] - y_test[:, 0])))
    mae_y = float(np.mean(np.abs(pred[:, 1] - y_test[:, 1])))
    within_5 = np.sum((np.abs(pred - y_test) <= 5).all(axis=1)) / len(y_test)
    return {
        "test_mae_x": round(mae_x, 4),
        "test_mae_y": round(mae_y, 4),
        "accuracy_within_5px": round(float(within_5), 4),
    }


class BoxDetectorProcessor:
    """Processes box detector training: re-scans each epoch so train/test grow with new labels; test set augmented for metrics."""

    def __init__(
        self,
        data_dir: str,
        model_path: str,
        test_ratio: float,
        epochs: int,
        augment_shift_regular: float,
        augment_shift_blueprint: float,
        augment_fill: str,
        augment_count: int,
    ):
        self.data_dir = Path(data_dir) if not isinstance(data_dir, Path) else data_dir
        self.model_path = model_path
        self.test_ratio = test_ratio
        self.epochs = epochs
        self.augment_shift_regular = augment_shift_regular
        self.augment_shift_blueprint = augment_shift_blueprint
        self.augment_fill = augment_fill
        self.augment_count = augment_count
        self._repo = _repo_root()
        self._data_dir_abs = (self._repo / self.data_dir).resolve()

    def process(
        self,
        task_id: str,
        progress_callback: Optional[Callable[[int, int, dict], None]] = None,
        check_cancelled: Optional[Callable[[], bool]] = None,
        resume_from_existing: bool = False,
    ) -> dict:
        """
        Run box detector training. Re-scans labeled dirs each epoch; train and test sets
        grow as new images are labeled. Test set is augmented for larger evaluation.
        Raises TaskCancelledError if check_cancelled returns True.
        If resume_from_existing is True, load the existing saved model when present; otherwise build a new one.
        """
        labeled = _labeled_dirs(self._data_dir_abs)
        if not labeled:
            return {
                "error": "no_labeled_data",
                "message": "No labeled screenshots found in data/labeled/screenshots/regular or blueprint.",
            }

        sources_initial = _scan_sources(labeled)
        if not sources_initial:
            return {
                "error": "no_valid_sources",
                "message": "No (image, .txt) pairs found.",
            }

        train_initial, test_initial = _split_train_test(sources_initial, self.test_ratio)
        if len(train_initial) == 0:
            return {
                "error": "no_train_sources",
                "message": "No training samples after split (test_ratio may be too high).",
            }

        # Save under data/models/box_detector so we always write to the mounted volume
        save_dir = self._data_dir_abs / "models" / "box_detector"
        stem = Path(self.model_path).name
        if stem.endswith(".keras") or stem.endswith(".h5"):
            stem = Path(stem).stem
        save_dir.mkdir(parents=True, exist_ok=True)
        _relax_path_for_host(save_dir, is_dir=True)

        if resume_from_existing:
            load_path = _resolve_box_detector_load_path(self._data_dir_abs, self.model_path)
            if load_path is not None:
                try:
                    model = _load_existing_model(load_path)
                except Exception as e:
                    logger.warning("Failed to load existing model from %s: %s; building fresh model", load_path, e)
                    model = _build_model()
            else:
                logger.info("No existing model found; building fresh model")
                model = _build_model()
        else:
            model = _build_model()

        for epoch in range(1, self.epochs + 1):
            if check_cancelled and check_cancelled():
                raise TaskCancelledError()

            labeled_now = _labeled_dirs(self._data_dir_abs)
            sources_now = _scan_sources(labeled_now)
            if not sources_now:
                continue
            train_sources, test_sources = _split_train_test(sources_now, self.test_ratio)
            if not train_sources:
                train_sources = train_initial

            X_train, y_train = _build_arrays(
                train_sources,
                augment=True,
                shift_regular=self.augment_shift_regular,
                shift_blueprint=self.augment_shift_blueprint,
                fill_mode=self.augment_fill,
                augment_count=self.augment_count,
            )
            X_test_aug, y_test_aug = _build_arrays(
                test_sources,
                augment=True,
                shift_regular=self.augment_shift_regular,
                shift_blueprint=self.augment_shift_blueprint,
                fill_mode=self.augment_fill,
                augment_count=self.augment_count,
            )

            if X_train.shape[0] == 0:
                continue

            validation_data = (X_test_aug, y_test_aug) if len(X_test_aug) > 0 else None
            hist = model.fit(
                X_train, y_train,
                epochs=1,
                validation_data=validation_data,
                verbose=0,
            )
            loss = float(hist.history["loss"][0])
            val_loss = float(hist.history["val_loss"][0]) if "val_loss" in hist.history else loss
            mae = float(hist.history.get("mae", [0])[0])
            val_mae = float(hist.history["val_mae"][0]) if "val_mae" in hist.history else 0.0

            metrics = {
                "loss": round(loss, 6),
                "val_loss": round(val_loss, 6),
                "mae": round(mae, 4),
                "val_mae": round(val_mae, 4),
                "train_samples": int(X_train.shape[0]),
                "test_samples": int(X_test_aug.shape[0]),
            }
            test_metrics = _compute_test_metrics(model, X_test_aug, y_test_aug)
            metrics.update(test_metrics)

            if progress_callback:
                progress_callback(epoch, self.epochs, metrics)

            # Save checkpoint every 10 epochs (and on last epoch) so eval thread can load it
            save_checkpoint = (epoch % 10 == 0) or (epoch == self.epochs)
            if save_checkpoint:
                current_path = save_dir / (stem + "_current.keras")
                logger.info("Saving checkpoint to %s", current_path)
                _save_model_native(model, current_path)
                if not current_path.exists():
                    logger.warning("Checkpoint file missing after save: %s", current_path)

            if check_cancelled and check_cancelled():
                raise TaskCancelledError()

        # Final split from current sources for last metrics
        labeled_final = _labeled_dirs(self._data_dir_abs)
        sources_final = _scan_sources(labeled_final)
        _, test_sources_final = _split_train_test(sources_final, self.test_ratio)
        X_test_final, y_test_final = _build_arrays(
            test_sources_final,
            augment=True,
            shift_regular=self.augment_shift_regular,
            shift_blueprint=self.augment_shift_blueprint,
            fill_mode=self.augment_fill,
            augment_count=self.augment_count,
        )

        # Save final model: timestamped + legacy (always under data dir)
        timestamped_name = stem + "_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".keras"
        timestamped_path = save_dir / timestamped_name
        legacy_path = save_dir / (stem + ".keras")
        logger.info("Saving final model to %s and %s", timestamped_path, legacy_path)
        _save_model_native(model, timestamped_path)
        _save_model_native(model, legacy_path)
        if not timestamped_path.exists():
            logger.error("Timestamped model file missing after save: %s", timestamped_path)
        if not legacy_path.exists():
            logger.error("Legacy model file missing after save: %s", legacy_path)

        final_metrics = _compute_test_metrics(model, X_test_final, y_test_final)
        final_metrics["epochs"] = self.epochs
        final_metrics["status"] = "completed"
        return final_metrics
