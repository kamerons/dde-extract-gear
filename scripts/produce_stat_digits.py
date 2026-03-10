"""Produce unlabeled digit crops from labeled stat icons. Run from repo root: python3 scripts/produce_stat_digits.py

Reads data/labeled/icons/<stat_type>/*.png, runs legacy-style digit extraction (shared.stat_digit_extract),
and writes each digit image to data/unlabeled/numbers/ with names {stat_type}_{icon_stem}_{digit_index:02d}.png.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from shared.stat_digit_extract import extract_digits
from shared.stat_normalizer import StatNormalizer

# Stat-type dirs to use for digit extraction; exclude "none" (no real stat value)
VALID_STAT_TYPES = frozenset(StatNormalizer.STAT_GROUPS.keys())

# Expected stat icon size (shared/extract_regions STAT_SIZE)
STAT_ICON_HEIGHT = 56
STAT_ICON_WIDTH = 56


def _repo_data_dir() -> Path:
    return _repo_root / "data"


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


def _load_stat_icon_bgr(png_path: Path) -> np.ndarray | None:
    """Load PNG as BGR numpy array (56, 56, 3). Returns None if unreadable or wrong size."""
    try:
        img = Image.open(png_path).convert("RGB")
        arr = np.array(img)
    except Exception:
        return None
    if arr.ndim != 3 or arr.shape[2] != 3:
        return None
    h, w = arr.shape[:2]
    if h != STAT_ICON_HEIGHT or w != STAT_ICON_WIDTH:
        return None
    # extract_digits expects BGR (legacy OpenCV order)
    bgr = arr[:, :, ::-1].copy()
    return bgr


def produce_stat_digits(
    data_dir: Path | None = None,
    out_dir: Path | None = None,
) -> int:
    """
    Produce unlabeled digit PNGs from every labeled stat icon into data/unlabeled/numbers.

    Returns the number of digit images written.
    """
    data_dir = data_dir or _repo_data_dir()
    out_dir = out_dir or (data_dir / "unlabeled" / "numbers")
    out_dir.mkdir(parents=True, exist_ok=True)

    labeled_dirs = _labeled_icon_dirs(data_dir)
    if not labeled_dirs:
        print("No labeled icon dirs found under data/labeled/icons/ (valid stat-type subdirs).")
        return 0

    sources = _scan_icon_sources(labeled_dirs)
    if not sources:
        print("No PNGs found under data/labeled/icons/<stat_type>/.")
        return 0

    total_written = 0
    skipped = []

    for stat_type, png_path in sources:
        stem = png_path.stem
        img_bgr = _load_stat_icon_bgr(png_path)
        if img_bgr is None:
            skipped.append((png_path.name, "unreadable or not 56x56"))
            continue
        digits = extract_digits(img_bgr)
        for idx, digit_bgr in enumerate(digits):
            out_name = f"{stat_type}_{stem}_{idx:02d}.png"
            out_path = out_dir / out_name
            # Save as RGB for consistency with other scripts (PIL)
            digit_rgb = digit_bgr[:, :, ::-1]
            Image.fromarray(digit_rgb).save(out_path)
            total_written += 1

    if skipped:
        for name, reason in skipped:
            print(f"Skipped {name}: {reason}")

    print(f"Wrote {total_written} digit images to {out_dir}.")
    return total_written


def main() -> None:
    produce_stat_digits()


if __name__ == "__main__":
    main()
