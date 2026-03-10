"""Icon (stat) type classification training: reads labeled icons, stratified 75/25 split,
trains until 100% test accuracy then saves and stops. Saves under data/models/icon_type_detection.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
from PIL import Image

from shared.recommendation_engine import TaskCancelledError
from shared.stat_normalizer import StatNormalizer

from task.processors.box_detector_processor import (
    _relax_path_for_host,
    _save_model_native,
    _write_training_params,
)

logger = logging.getLogger(__name__)

# Input size for the model (matches shared/extract_regions STAT_SIZE)
INPUT_HEIGHT = 56
INPUT_WIDTH = 56

# Valid stat types: STAT_GROUPS keys + "none", stable order for label indices
CLASS_NAMES: list[str] = sorted(StatNormalizer.STAT_GROUPS.keys()) + ["none"]
VALID_STAT_TYPES = frozenset(CLASS_NAMES)

# Do not early-stop on 100% test accuracy before this many epochs (avoids saving on a lucky first epoch)
MIN_EPOCHS_BEFORE_EARLY_STOP = 5


def _labeled_icon_dirs(data_dir: Path) -> list[tuple[str, Path]]:
    """Return [(stat_type, subdir_path), ...] for labeled/icons subdirs that are valid stat types."""
    base = data_dir / "labeled" / "icons"
    if not base.exists():
        return []
    out = []
    for subdir in sorted(base.iterdir()):
        if subdir.is_dir() and subdir.name in VALID_STAT_TYPES:
            out.append((subdir.name, subdir))
    return out


def _scan_icon_sources(labeled_dirs: list[tuple[str, Path]]) -> list[tuple[str, Path]]:
    """Scan dirs for (stat_type, png_path). Only PNGs."""
    sources = []
    for stat_type, dirpath in labeled_dirs:
        for png_path in sorted(dirpath.glob("*.png")):
            sources.append((stat_type, png_path))
    return sources


def _split_train_test_stratified(
    sources: list[tuple[str, Path]],
    test_ratio: float = 0.25,
) -> tuple[list[tuple[str, Path]], list[tuple[str, Path]]]:
    """
    Stratified split: per stat type, sort by path, reserve test_ratio (25%) as test.
    n_test = max(0, (n * 25) // 100) per type; test = last n_test, train = rest.
    """
    if not sources:
        return [], []
    by_type: dict[str, list[tuple[str, Path]]] = {}
    for stat_type, png_path in sources:
        by_type.setdefault(stat_type, []).append((stat_type, png_path))
    train_list = []
    test_list = []
    for stat_type in sorted(by_type.keys()):
        items = sorted(by_type[stat_type], key=lambda x: str(x[1]))
        n = len(items)
        n_test = max(0, (n * int(test_ratio * 100)) // 100)
        n_train = n - n_test
        train_list.extend(items[:n_train])
        test_list.extend(items[-n_test:] if n_test else [])
    return train_list, test_list


def _load_icon_image(png_path: Path) -> np.ndarray:
    """Load PNG as RGB, resize to INPUT_HEIGHT x INPUT_WIDTH, normalize to [0,1]."""
    img = Image.open(png_path).convert("RGB")
    arr = np.array(img.resize((INPUT_WIDTH, INPUT_HEIGHT)), dtype=np.float32) / 255.0
    return arr


def _build_icon_arrays(
    sources: list[tuple[str, Path]],
    class_to_index: dict[str, int],
) -> tuple[np.ndarray, np.ndarray]:
    """Build X (N, H, W, 3) and y (N,) int labels from (stat_type, path) list."""
    if not sources:
        return (
            np.zeros((0, INPUT_HEIGHT, INPUT_WIDTH, 3), dtype=np.float32),
            np.zeros((0,), dtype=np.int32),
        )
    X_list = []
    y_list = []
    for stat_type, png_path in sources:
        arr = _load_icon_image(png_path)
        X_list.append(arr)
        y_list.append(class_to_index[stat_type])
    return np.stack(X_list), np.array(y_list, dtype=np.int32)


def _build_icon_type_model(num_classes: int, initial_learning_rate: float = 0.0001):
    """Keras classification model: Conv2D stack + Dense(num_classes). SparseCategoricalCrossentropy, accuracy."""
    from tensorflow import keras

    model = keras.Sequential([
        keras.layers.Conv2D(
            16, 3, padding="same", activation="relu",
            input_shape=(INPUT_HEIGHT, INPUT_WIDTH, 3),
        ),
        keras.layers.MaxPool2D(),
        keras.layers.Conv2D(16, 3, padding="same", activation="relu"),
        keras.layers.MaxPool2D(),
        keras.layers.Conv2D(32, 3, padding="same", activation="relu"),
        keras.layers.MaxPool2D(),
        keras.layers.Dropout(0.4),
        keras.layers.Flatten(),
        keras.layers.Dense(64, activation="relu"),
        keras.layers.Dense(num_classes),
    ])
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=initial_learning_rate),
        loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=["accuracy"],
    )
    return model


class IconTypeDetectorProcessor:
    """Processes icon type (stat type) classification training: stratified 75/25 split,
    train until 100% test accuracy then save and stop.
    """

    def __init__(
        self,
        data_dir: str,
        model_path: str,
        test_ratio: float,
        epochs: int,
        initial_learning_rate: float = 0.0001,
    ):
        self._data_dir_abs = Path(data_dir).resolve() if not Path(data_dir).is_absolute() else Path(data_dir)
        self.model_path = model_path
        self.test_ratio = test_ratio
        self.epochs = epochs
        self.initial_learning_rate = initial_learning_rate

    def process(
        self,
        task_id: str = "",
        progress_callback: Optional[Callable[[int, int, dict], None]] = None,
        check_cancelled: Optional[Callable[[], bool]] = None,
    ) -> dict:
        """
        Run icon type training. Stratified 75/25 split; each epoch fit with validation_data=test.
        When test accuracy >= 1.0, save model to data/models/icon_type_detection and return.
        Raises TaskCancelledError if check_cancelled returns True.
        """
        labeled_dirs = _labeled_icon_dirs(self._data_dir_abs)
        if not labeled_dirs:
            return {
                "error": "no_labeled_data",
                "message": "No labeled icon dirs found in data/labeled/icons/ (valid stat type subdirs).",
            }

        sources = _scan_icon_sources(labeled_dirs)
        if not sources:
            return {
                "error": "no_labeled_data",
                "message": "No PNG files found in data/labeled/icons/<stat_type>/.",
            }

        train_sources, test_sources = _split_train_test_stratified(sources, self.test_ratio)
        if not train_sources:
            return {
                "error": "no_train_sources",
                "message": "No training samples after stratified split (test_ratio may be too high).",
            }
        if not test_sources:
            return {
                "error": "no_test_sources",
                "message": "No test samples after stratified split (need enough samples per type for 25% test).",
            }

        train_paths = frozenset(p.resolve() for _, p in train_sources)
        test_paths = frozenset(p.resolve() for _, p in test_sources)
        overlap = train_paths & test_paths
        if overlap:
            return {
                "error": "train_test_overlap",
                "message": f"Train and test sets must be disjoint; found {len(overlap)} paths in both.",
            }

        def _count_by_type(sources_list: list[tuple[str, Path]]) -> dict[str, int]:
            counts: dict[str, int] = {}
            for stat_type, _ in sources_list:
                counts[stat_type] = counts.get(stat_type, 0) + 1
            return counts

        train_by_type = _count_by_type(train_sources)
        test_by_type = _count_by_type(test_sources)
        logger.info(
            "Icon type training: %d train, %d test (stratified %.0f%% test)",
            len(train_sources),
            len(test_sources),
            self.test_ratio * 100,
        )
        for stat_type in sorted(train_by_type.keys()):
            tr = train_by_type[stat_type]
            te = test_by_type.get(stat_type, 0)
            logger.info("  %s: %d train, %d test", stat_type, tr, te)

        # Class list: only types that appear in our sources, in stable order (same as CLASS_NAMES)
        types_present = frozenset(s[0] for s in sources)
        class_names_used = [c for c in CLASS_NAMES if c in types_present]
        class_to_index = {c: i for i, c in enumerate(class_names_used)}
        num_classes = len(class_names_used)

        save_dir = self._data_dir_abs / "models" / "icon_type_detection"
        stem = Path(self.model_path).name
        if stem.endswith(".keras") or stem.endswith(".h5"):
            stem = Path(stem).stem
        save_dir.mkdir(parents=True, exist_ok=True)
        _relax_path_for_host(save_dir, is_dir=True)
        _write_training_params(save_dir, self.epochs, self.initial_learning_rate)

        model = _build_icon_type_model(num_classes, self.initial_learning_rate)

        X_train, y_train = _build_icon_arrays(train_sources, class_to_index)
        X_test, y_test = _build_icon_arrays(test_sources, class_to_index)

        for epoch in range(1, self.epochs + 1):
            if check_cancelled and check_cancelled():
                raise TaskCancelledError()

            hist = model.fit(
                X_train,
                y_train,
                epochs=1,
                batch_size=32,
                validation_data=(X_test, y_test),
                verbose=0,
            )
            loss = float(hist.history["loss"][0])
            val_loss = float(hist.history.get("val_loss", [loss])[0])
            acc = float(hist.history["accuracy"][0])
            val_acc = float(hist.history.get("val_accuracy", [0.0])[0])

            metrics = {
                "loss": round(loss, 6),
                "val_loss": round(val_loss, 6),
                "accuracy": round(acc, 4),
                "val_accuracy": round(val_acc, 4),
                "train_samples": int(X_train.shape[0]),
                "test_samples": int(X_test.shape[0]),
            }

            if progress_callback:
                progress_callback(epoch, self.epochs, metrics)

            if val_acc >= 1.0 and epoch >= MIN_EPOCHS_BEFORE_EARLY_STOP:
                timestamped_name = stem + "_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".keras"
                timestamped_path = save_dir / timestamped_name
                legacy_path = save_dir / (stem + ".keras")
                logger.info(
                    "100%% test accuracy reached at epoch %d; saving model to %s and %s",
                    epoch,
                    timestamped_path,
                    legacy_path,
                )
                _save_model_native(model, timestamped_path)
                _save_model_native(model, legacy_path)
                out_metrics = dict(metrics)
                out_metrics["epochs"] = epoch
                out_metrics["status"] = "completed"
                out_metrics["stopped_early_100"] = True
                return out_metrics

        # Max epochs reached without 100%%: save final model
        timestamped_name = stem + "_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".keras"
        timestamped_path = save_dir / timestamped_name
        legacy_path = save_dir / (stem + ".keras")
        logger.info("Saving final model to %s and %s", timestamped_path, legacy_path)
        _save_model_native(model, timestamped_path)
        _save_model_native(model, legacy_path)

        final_metrics = {
            "loss": round(float(hist.history["loss"][0]), 6),
            "val_loss": round(float(hist.history.get("val_loss", [0])[0]), 6),
            "accuracy": round(float(hist.history["accuracy"][0]), 4),
            "val_accuracy": round(float(hist.history.get("val_accuracy", [0])[0]), 4),
            "train_samples": int(X_train.shape[0]),
            "test_samples": int(X_test.shape[0]),
            "epochs": self.epochs,
            "status": "completed",
        }
        return final_metrics
