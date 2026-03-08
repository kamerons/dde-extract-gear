"""Configuration for task worker service. Loaded from config.yaml (required)."""

from typing import Optional

from shared.config_loader import get_augment_shifts, get_nested, load_config

_config_data = load_config()


class Config:
    """Configuration settings for the task worker. Sourced from config.yaml."""

    # Redis configuration
    REDIS_HOST: str = str(get_nested(_config_data, "redis", "host", default="redis"))
    REDIS_PORT: int = int(get_nested(_config_data, "redis", "port", default=6379))
    REDIS_DB: int = int(get_nested(_config_data, "redis", "db", default=0))
    _redis_password = get_nested(_config_data, "redis", "password")
    REDIS_PASSWORD: Optional[str] = (str(_redis_password).strip() or None) if _redis_password else None

    # Data
    DATA_FILE_PATH: str = str(get_nested(_config_data, "data", "file_path", default="data/collected.json"))
    DATA_DIR: str = str(get_nested(_config_data, "data", "dir", default="data"))

    # Extract pipeline: scale factors
    EXTRACT_REGULAR_SCALE: float = float(get_nested(_config_data, "extract", "regular_scale", default=1.0))
    EXTRACT_BLUEPRINT_SCALE: float = float(get_nested(_config_data, "extract", "blueprint_scale", default=1.0))

    # Extract pipeline: augmentation (per-axis shift bounds)
    _augment_regular = get_augment_shifts(_config_data, "regular")
    _augment_blueprint = get_augment_shifts(_config_data, "blueprint")
    EXTRACT_AUGMENT_SHIFT_REGULAR_X_NEG: float = _augment_regular[0]
    EXTRACT_AUGMENT_SHIFT_REGULAR_X_POS: float = _augment_regular[1]
    EXTRACT_AUGMENT_SHIFT_REGULAR_Y_NEG: float = _augment_regular[2]
    EXTRACT_AUGMENT_SHIFT_REGULAR_Y_POS: float = _augment_regular[3]
    EXTRACT_AUGMENT_SHIFT_BLUEPRINT_X_NEG: float = _augment_blueprint[0]
    EXTRACT_AUGMENT_SHIFT_BLUEPRINT_X_POS: float = _augment_blueprint[1]
    EXTRACT_AUGMENT_SHIFT_BLUEPRINT_Y_NEG: float = _augment_blueprint[2]
    EXTRACT_AUGMENT_SHIFT_BLUEPRINT_Y_POS: float = _augment_blueprint[3]

    _augment_fill_raw: str = (
        (str(get_nested(_config_data, "extract", "augment", "fill", default="black")) or "black").strip().lower()
    )

    @property
    def EXTRACT_AUGMENT_FILL(self) -> str:
        v = self._augment_fill_raw
        return v if v in ("black", "noise") else "black"

    EXTRACT_AUGMENT_COUNT: int = max(
        1,
        min(int(get_nested(_config_data, "extract", "augment", "count", default=7)), 100),
    )

    # Box detector training
    BOX_DETECTOR_TEST_RATIO: float = float(get_nested(_config_data, "box_detector", "test_ratio", default=0.25))
    BOX_DETECTOR_TEST_BLUEPRINT_FRACTION: float = float(
        get_nested(_config_data, "box_detector", "test_blueprint_fraction", default=0.5)
    )
    BOX_DETECTOR_MODEL_PATH: str = str(
        get_nested(_config_data, "box_detector", "model_path", default="data/box_detector_model")
    )
    TRAINING_EPOCHS: int = max(1, int(get_nested(_config_data, "box_detector", "training_epochs", default=50)))
    PREVIEW_EVERY_N_EPOCHS: int = max(
        1,
        min(int(get_nested(_config_data, "box_detector", "preview_every_n_epochs", default=20)), 1000),
    )
    PREVIEW_EXPECTED_DURATION_MS: int = max(
        0,
        int(get_nested(_config_data, "box_detector", "preview_expected_duration_ms", default=10000)),
    )
    PREVIEW_MS_PER_IMAGE: int = max(
        1,
        int(get_nested(_config_data, "box_detector", "preview_ms_per_image", default=244)),
    )

    EVALUATION_WORKER_COUNT: int = max(
        1,
        min(int(get_nested(_config_data, "task", "evaluation_worker_count", default=4)), 32),
    )

    @property
    def augment_shifts_regular(self) -> tuple[float, float, float, float]:
        """(x_neg, x_pos, y_neg, y_pos) crop margins for regular screenshots; not used to cap translation."""
        return (
            self.EXTRACT_AUGMENT_SHIFT_REGULAR_X_NEG,
            self.EXTRACT_AUGMENT_SHIFT_REGULAR_X_POS,
            self.EXTRACT_AUGMENT_SHIFT_REGULAR_Y_NEG,
            self.EXTRACT_AUGMENT_SHIFT_REGULAR_Y_POS,
        )

    @property
    def augment_shifts_blueprint(self) -> tuple[float, float, float, float]:
        """(x_neg, x_pos, y_neg, y_pos) crop margins for blueprint screenshots; not used to cap translation."""
        return (
            self.EXTRACT_AUGMENT_SHIFT_BLUEPRINT_X_NEG,
            self.EXTRACT_AUGMENT_SHIFT_BLUEPRINT_X_POS,
            self.EXTRACT_AUGMENT_SHIFT_BLUEPRINT_Y_NEG,
            self.EXTRACT_AUGMENT_SHIFT_BLUEPRINT_Y_POS,
        )

    @property
    def redis_url(self) -> str:
        """Get Redis connection URL."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
