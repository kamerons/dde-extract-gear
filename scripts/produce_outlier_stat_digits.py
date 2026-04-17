"""Produce unlabeled digit crops from outlier screenshots (hero_hp and tower_hp only).

Run from repo root: python scripts/produce_outlier_stat_digits.py

Reads outlier filenames from a markdown file (backtick-wrapped .png names). Resolves each file under
data/labeled/screenshots/regular/ or .../blueprint/ (with companion .txt origin), extracts digit crops
for requested stats (default hero_hp,tower_hp; use --stats e.g. hero_rate), runs
shared.stat_digit_extract, and writes PNGs to data/unlabeled/numbers/ with an outlier_ prefix.
Standard stats use fixed grid slots; unknown stat names fall back to the icon type model if present.
"""

import argparse
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

# Fixed stat grid slot indices: same row-major order as legacy STAT_OPTIONS /
# collect UI (base, resists, hero row, tower row). See shared/extract_regions stat grid.
FIXED_STAT_SLOTS = {
    "hero_hp": 4,
    "hero_dmg": 5,
    "hero_rate": 6,
    "hero_speed": 7,
    "offense": 8,
    "defense": 9,
    "tower_hp": 10,
    "tower_dmg": 11,
    "tower_rate": 12,
    "tower_range": 13,
    "base": 0,
    "fire": 1,
    "electric": 2,
    "poison": 3,
}

SCALE = 1.0

# Avoid reloading the icon Keras model on every screenshot in one run.
_ICON_MODEL_SCRIPT_CACHE: dict = {}


def _stat_slot_via_icon_model(
    img_rgb: np.ndarray,
    origin_x: int,
    origin_y: int,
    image_type: str,
    data_dir: Path,
    target_stat: str,
    icon_model,
) -> int | None:
    """
    Find which stat-box index the icon model classifies as target_stat (e.g. hero_rate).
    Matches verify_card icon routing. Returns None if not found.
    """
    from shared.card_verification import ICON_CLASS_NAMES, _crop_box, _resize_stat_crop

    boxes = compute_boxes(origin_x, origin_y, SCALE, image_type)
    stat_boxes = [b for b in boxes if b.get("type") == "stat"]
    if not stat_boxes or icon_model is None:
        return None
    stat_crops = [_crop_box(img_rgb, b) for b in stat_boxes]
    stat_crops_56 = [_resize_stat_crop(c) for c in stat_crops]
    X = np.stack(stat_crops_56).astype(np.float32) / 255.0
    preds = icon_model.predict(X, verbose=0)
    pred_indices = np.argmax(preds, axis=-1)
    for i, idx in enumerate(pred_indices):
        idx = int(idx)
        if idx >= len(ICON_CLASS_NAMES):
            continue
        if ICON_CLASS_NAMES[idx] == target_stat:
            return i
    return None


def _resolve_screenshot(
    data_dir: Path, filename: str
) -> tuple[Path, Path, str] | None:
    """Return (png_path, txt_path, image_type) for regular or blueprint, or None if missing."""
    for image_type in ("regular", "blueprint"):
        base = data_dir / "labeled" / "screenshots" / image_type
        png_path = base / filename
        if png_path.is_file():
            return png_path, png_path.with_suffix(".txt"), image_type
    return None


def _parse_stats_csv(stats_csv: str) -> list[str]:
    return [s.strip() for s in stats_csv.split(",") if s.strip()]


def produce_outlier_stat_digits(
    data_dir: Path | None = None,
    outliers_md_path: Path | None = None,
    out_dir: Path | None = None,
    stats: list[str] | None = None,
) -> int:
    """
    Produce unlabeled digit PNGs from outlier screenshots for named stats.

    hero_hp and tower_hp use fixed grid slots; other stats (e.g. hero_rate) need the
    icon type model to find which stat box is which.

    Returns the number of digit images written.
    """
    from shared.card_verification import _get_cached_model, _resolve_icon_model_path

    data_dir = data_dir or _repo_root / "data"
    data_dir = Path(data_dir).resolve()
    out_dir = out_dir or (data_dir / "unlabeled" / "numbers")
    outliers_md_path = outliers_md_path or (data_dir / "collected" / "armor_run1_outliers.md")
    stat_names = stats if stats is not None else ["hero_hp", "tower_hp"]

    out_dir.mkdir(parents=True, exist_ok=True)

    filenames = _parse_outlier_filenames(outliers_md_path)
    if not filenames:
        print("No outlier filenames found in " + str(outliers_md_path) + ".")
        return 0

    needs_icon = any(name not in FIXED_STAT_SLOTS for name in stat_names)
    icon_model = None
    icon_path = _resolve_icon_model_path(data_dir)
    if needs_icon:
        if icon_path is None or not icon_path.exists():
            print("Icon type model required for non-fixed stats but not found under data/models/icon_type_detection.")
            return 0
        icon_model, _ = _get_cached_model(icon_path, _ICON_MODEL_SCRIPT_CACHE)

    total_written = 0
    skipped = []

    def in_bounds(b: dict, img_w: int, img_h: int) -> bool:
        x, y = b["x"], b["y"]
        w, h = b["width"], b["height"]
        return x >= 0 and y >= 0 and x + w <= img_w and y + h <= img_h

    for filename in filenames:
        resolved = _resolve_screenshot(data_dir, filename)
        if resolved is None:
            skipped.append((filename, "PNG missing under regular/ and blueprint/"))
            continue
        png_path, txt_path, image_type = resolved
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
        boxes = compute_boxes(origin_x, origin_y, SCALE, image_type)
        stat_boxes = [b for b in boxes if b.get("type") == "stat"]
        if len(stat_boxes) < 14:
            skipped.append((filename, "expected 14 stat boxes, got " + str(len(stat_boxes))))
            continue

        stem = png_path.stem

        for stat_name in stat_names:
            if stat_name in FIXED_STAT_SLOTS:
                stat_slot = FIXED_STAT_SLOTS[stat_name]
            else:
                if icon_model is None:
                    skipped.append((filename, "no icon model for " + stat_name))
                    break
                stat_slot = _stat_slot_via_icon_model(
                    img_rgb,
                    origin_x,
                    origin_y,
                    image_type,
                    data_dir,
                    stat_name,
                    icon_model,
                )
                if stat_slot is None:
                    skipped.append((filename, "icon model did not find slot for " + stat_name))
                    break

            if stat_slot >= len(stat_boxes):
                skipped.append((filename, "stat slot out of range for " + stat_name))
                break
            b = stat_boxes[stat_slot]
            if not in_bounds(b, img_width, img_height):
                skipped.append((filename, "stat box out of image bounds for " + stat_name))
                break

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
    parser = argparse.ArgumentParser(
        description="Extract digit crops for listed stats from outlier screenshots (fixed slots or icon model)."
    )
    parser.add_argument(
        "--outliers-md",
        type=Path,
        default=None,
        help="Markdown file with backtick-wrapped .png filenames (default: armor_run1_outliers.md)",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Data directory (default: repo data/)",
    )
    parser.add_argument(
        "--stats",
        type=str,
        default="hero_hp,tower_hp",
        help="Comma-separated stats to extract (default: hero_hp,tower_hp). "
        "Other names (e.g. hero_rate) use the icon type model to locate the box.",
    )
    args = parser.parse_args()
    stats_list = _parse_stats_csv(args.stats)
    produce_outlier_stat_digits(
        data_dir=args.data_dir,
        outliers_md_path=args.outliers_md,
        stats=stats_list,
    )


if __name__ == "__main__":
    main()
