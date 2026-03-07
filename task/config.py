"""Configuration for task worker service."""

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration settings for the task worker."""

    # Redis configuration
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD", None)

    # Data file path
    DATA_FILE_PATH: str = os.getenv("DATA_FILE_PATH", "data/collected.json")

    # Data directory for extract pipeline
    DATA_DIR: str = os.getenv("DATA_DIR", "data")

    # Extract pipeline: augmentation (for box detector training)
    EXTRACT_AUGMENT_SHIFT_REGULAR: float = float(
        os.getenv("EXTRACT_AUGMENT_SHIFT_REGULAR", "0.1")
    )
    EXTRACT_AUGMENT_SHIFT_BLUEPRINT: float = float(
        os.getenv("EXTRACT_AUGMENT_SHIFT_BLUEPRINT", "0.1")
    )
    _augment_fill_raw: str = (
        (os.getenv("EXTRACT_AUGMENT_FILL", "black") or "black").strip().lower()
    )

    @property
    def EXTRACT_AUGMENT_FILL(self) -> str:
        v = self._augment_fill_raw
        return v if v in ("black", "noise") else "black"

    EXTRACT_AUGMENT_COUNT: int = max(
        1, min(int(os.getenv("EXTRACT_AUGMENT_COUNT", "3")), 100)
    )

    # Box detector training
    BOX_DETECTOR_TEST_RATIO: float = float(
        os.getenv("BOX_DETECTOR_TEST_RATIO", "0.2")
    )
    BOX_DETECTOR_MODEL_PATH: str = os.getenv(
        "BOX_DETECTOR_MODEL_PATH", "data/box_detector_model"
    )
    TRAINING_EPOCHS: int = max(1, int(os.getenv("TRAINING_EPOCHS", "50")))

    @property
    def redis_url(self) -> str:
        """Get Redis connection URL."""
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
