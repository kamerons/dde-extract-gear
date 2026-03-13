"""Produce unlabeled digit crops from armor run1 outlier screenshots (hero_hp and tower_hp only).

Run from repo root: python scripts/produce_outlier_stat_digits.py

Reads outlier filenames from data/collected/armor_run1_outliers.md, loads those screenshots from
data/labeled/screenshots/regular/ (with companion .txt origin), extracts only hero_hp and tower_hp
stat regions, runs digit extraction (shared.stat_digit_extract), and writes digit images to
data/unlabeled/numbers/ with an outlier_ prefix. No interim card or stat-icon crops are saved.
"""

import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image

_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from shared.box_detector_augment import read_txt_origin
from shared.extract_regions import compute_boxes
from shared.stat_digit_extract import extract_digits

# Stat grid slots for hero_hp and tower_hp (shared/extract_regions order: row0 4, row1 6, row2 4)
HERO_HP_STAT_SLOT = 4
TOWER_HP_STAT_SLOT = 10

SCALE = 1.0
IMAGE_TYPE = "regular"


def produce_outlier_stat_digits(
    data_dir: Path | None = None,
    outliers_md_path: Path | None = None,
    out_dir: Path | None = None,
) -> int:
    """
    Produce unlabeled digit PNGs from outlier screenshots (hero_hp and tower_hp only).

    Returns the number of digit images written.
    """
    data_dir = data_dir or _repo_root / "data"
    out_dir = out_dir or (data_dir / "unlabeled" / "numbers")
    outliers_md_path = outliers_md_path or (data_dir / "collected" / "armor_run1_outliers.md")

    out_dir.mkdir(parents=True, exist_ok=True)

    filenames = _parse_outlier_filenames(outliers_md_path)
    if not filenames:
        print("No outlier filenames found in " + str(outliers_md_path) + ".")
        return 0

    screenshots_dir = data_dir / "labeled" / "screenshots" / IMAGE_TYPE
    if not screenshots_dir.exists():
        print("Screenshots dir not found: " + str(screenshots_dir))
        return 0

    total_written = 0
    skipped = []

    for filename in filenames:
        png_path = screenshots_dir / filename
        txt_path = png_path.with_suffix(".txt")
        if not png_path.exists():
            skipped.append((filename, "PNG missing"))
            continue
        if not txt_path.exists():
            skipped.append((filename, "origin .txt missing"))
            continue
        origin = read_txt_origin(txt_path)
        if origin is None:
            skipped.append((filename, "invalid origin in .txt"))
            continue

        origin_x, origin_y = origin
        try:
            img_rgb = np.array(Image.open(png_path).convert("RGB"))
        except Exception as e:
            skipped.append((filename, "unreadable image: " + str(e)))
            continue

        img_height, img_width = img_rgb.shape[:2]
        boxes = compute_boxes(origin_x, origin_y, SCALE, IMAGE_TYPE)
        stat_boxes = [b for b in boxes if b.get("type") == "stat"]
        if len(stat_boxes) < max(HERO_HP_STAT_SLOT, TOWER_HP_STAT_SLOT) + 1:
            skipped.append((filename, "expected 14 stat boxes, got " + str(len(stat_boxes))))
            continue

        hero_box = stat_boxes[HERO_HP_STAT_SLOT]
        tower_box = stat_boxes[TOWER_HP_STAT_SLOT]

        def in_bounds(b: dict) -> bool:
            x, y = b["x"], b["y"]
            w, h = b["width"], b["height"]
            return x >= 0 and y >= 0 and x + w <= img_width and y + h <= img_height

        if not in_bounds(hero_box) or not in_bounds(tower_box):
            skipped.append((filename, "stat box out of image bounds"))
            continue

        stem = png_path.stem

        for stat_slot, stat_name in ((HERO_HP_STAT_SLOT, "hero_hp"), (TOWER_HP_STAT_SLOT, "tower_hp")):
            b = stat_boxes[stat_slot]
            x, y, w, h = b["x"], b["y"], b["width"], b["height"]
            crop_rgb = img_rgb[y : y + h, x : x + w]
            crop_bgr = crop_rgb[:, :, ::-1].copy()
            digits = extract_digits(crop_bgr)
            for idx, digit_bgr in enumerate(digits):
                out_name = f"outlier_{stem}_{stat_name}_{idx:02d}.png"
                out_path = out_dir / out_name
                digit_rgb = digit_bgr[:, :, ::-1]
                Image.fromarray(digit_rgb).save(out_path)
                total_written += 1

    if skipped:
        for name, reason in skipped:
            print("Skipped " + name + ": " + reason)

    print("Wrote " + str(total_written) + " digit images to " + str(out_dir) + ".")
    return total_written


def _parse_outlier_filenames(md_path: Path) -> list[str]:
    """Extract .png filenames from armor_run1_outliers.md (lines like `run1_....png`)."""
    if not md_path.exists():
        return []
    text = md_path.read_text()
    # Match backtick-wrapped filenames ending in .png
    pattern = re.compile(r"`([^`]+\.png)`")
    return list(dict.fromkeys(pattern.findall(text)))  # preserve order, dedupe


def main() -> None:
    produce_outlier_stat_digits()


if __name__ == "__main__":
    main()
