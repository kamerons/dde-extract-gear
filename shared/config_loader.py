"""Load config from config.yaml. Fails fast if file is missing. Optional env overlay for secrets."""

import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


def _config_path() -> Path:
    raw = os.environ.get("CONFIG_PATH", "").strip()
    if raw:
        return Path(raw)
    return Path("config.yaml")


def load_config() -> dict[str, Any]:
    """
    Load config from config.yaml (or CONFIG_PATH). Raises FileNotFoundError if missing.
    REDIS_PASSWORD can be overridden via os.environ (so secrets need not live in the file).
    """
    if yaml is None:
        raise RuntimeError("PyYAML is required for config loading. Install with: pip install PyYAML")
    path = _config_path().resolve()
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}. Copy config.yaml.example to config.yaml (or set CONFIG_PATH)."
        )
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("config.yaml must be a YAML object (key-value).")
    # Optional: overlay REDIS_PASSWORD from env so secrets need not be in the file
    if "REDIS_PASSWORD" in os.environ and os.environ["REDIS_PASSWORD"].strip():
        if "redis" not in data:
            data["redis"] = {}
        data["redis"]["password"] = os.environ["REDIS_PASSWORD"].strip()
    return data


def get_nested(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Get a nested key, e.g. get_nested(data, 'redis', 'host') -> data['redis']['host']."""
    for key in keys:
        if not isinstance(data, dict) or key not in data:
            return default
        data = data[key]
    return data


def get_augment_shifts(data: dict[str, Any], typename: str) -> tuple[float, float, float, float]:
    """Get (x_neg, x_pos, y_neg, y_pos) crop margins for 'regular' or 'blueprint'.

    These are crop margins (max fraction of full image discarded per side). They are not
    used to cap augmentation translation; translation uses geometric limits (label + box).
    Clamps to [0, 1], default 0.1.
    """
    extract = data.get("extract") or {}
    augment = extract.get("augment") or {}
    t = augment.get(typename) or {}
    def f(k: str) -> float:
        return max(0.0, min(1.0, float(t.get(k, 0.1))))
    return (f("x_neg"), f("x_pos"), f("y_neg"), f("y_pos"))
