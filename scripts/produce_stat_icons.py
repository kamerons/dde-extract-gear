"""Produce 14 stat-icon crops per labeled screenshot. Run from repo root: python3 scripts/produce_stat_icons.py

Reads data/labeled/screenshots/regular and blueprint (PNG + companion .txt with origin_x origin_y),
computes stat regions via shared.extract_regions, crops each region, and writes to data/unlabeled/stat_icons.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

# Ensure repo root is on path so shared is importable when run as script
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from shared.box_detector_augment import read_txt_origin
from shared.extract_regions import compute_boxes

STAT_ICONS_PER_SOURCE = 14


def _repo_data_dir() -> Path:
    return _repo_root / "data"


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
    """Scan dirs for (typename, filename, png_path, origin_x, origin_y)."""
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


def _load_image_as_array(png_path: Path) -> np.ndarray:
    """Load PNG as RGB numpy array (height, width, 3)."""
    img = Image.open(png_path).convert("RGB")
    return np.array(img)


def _box_in_bounds(x: int, y: int, w: int, h: int, img_height: int, img_width: int) -> bool:
    return x >= 0 and y >= 0 and x + w <= img_width and y + h <= img_height


def produce_stat_icons(
    data_dir: Path | None = None,
    out_dir: Path | None = None,
    scale: float = 1.0,
) -> int:
    """
    Produce 14 stat-icon PNGs per labeled screenshot into data/unlabeled/stat_icons.

    Returns the number of stat icon images written.
    """
    data_dir = data_dir or _repo_data_dir()
    out_dir = out_dir or (data_dir / "unlabeled" / "stat_icons")
    out_dir.mkdir(parents=True, exist_ok=True)

    labeled = _labeled_dirs(data_dir)
    if not labeled:
        print("No labeled screenshot dirs found under data/labeled/screenshots/ (regular or blueprint).")
        return 0

    sources = _scan_sources(labeled)
    if not sources:
        print("No labeled sources (PNG + .txt) found.")
        return 0

    total_written = 0
    skipped = []

    for typename, filename, png_path, origin_x, origin_y in sources:
        stem = png_path.stem
        img_arr = _load_image_as_array(png_path)
        img_height, img_width = img_arr.shape[:2]

        boxes = compute_boxes(origin_x, origin_y, scale, typename)
        stat_boxes = [b for b in boxes if b.get("type") == "stat"]

        if len(stat_boxes) != STAT_ICONS_PER_SOURCE:
            skipped.append((filename, f"expected {STAT_ICONS_PER_SOURCE} stat boxes, got {len(stat_boxes)}"))
            continue

        all_in_bounds = True
        for b in stat_boxes:
            x, y = b["x"], b["y"]
            w, h = b["width"], b["height"]
            if not _box_in_bounds(x, y, w, h, img_height, img_width):
                all_in_bounds = False
                break

        if not all_in_bounds:
            skipped.append((filename, "one or more stat boxes out of image bounds"))
            continue

        for slot, b in enumerate(stat_boxes):
            x, y = b["x"], b["y"]
            w, h = b["width"], b["height"]
            crop = img_arr[y : y + h, x : x + w]
            out_name = f"{typename}_{stem}_{slot:02d}.png"
            out_path = out_dir / out_name
            Image.fromarray(crop).save(out_path)
            total_written += 1

    if skipped:
        for name, reason in skipped:
            print(f"Skipped {name}: {reason}")

    print(f"Wrote {total_written} stat icons to {out_dir}.")
    return total_written


def main() -> None:
    produce_stat_icons()


if __name__ == "__main__":
    main()
