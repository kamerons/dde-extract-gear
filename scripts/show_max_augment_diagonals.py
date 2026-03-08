#!/usr/bin/env python3
"""
Show the 4 diagonal max-augment images in a simple 2x2 GUI.

Pushes the cropped image to the maximum allowed translation in each diagonal direction
(using the same label-aware limits as training) and displays all 4 at once.
Run from repo root: python scripts/show_max_augment_diagonals.py [image.png] [regular|blueprint]

If no image is given, uses the first labeled screenshot in data/labeled/screenshots/regular.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Run from repo root so config and data paths resolve
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
os.chdir(REPO_ROOT)

from PIL import Image

from shared.box_detector_augment import apply_shift_with_fill, crop_to_inner_rect, read_txt_origin
from shared.config_loader import get_nested, load_config
from shared.extract_regions import compute_detection_extents


def get_max_shift_limits(
    cw: int,
    ch: int,
    origin_crop_x: int,
    origin_crop_y: int,
    scale: float,
    image_type: str,
) -> tuple[int, int, int, int]:
    """Return (max_dx_neg, max_dx_pos, max_dy_neg, max_dy_pos) so the detection box stays in frame.

    Limits are geometric only (label + box extents in cropped space). Config crop margins
    are not used to cap shift; the box can be pushed to the crop edges in all four directions.
    """
    left_ext, top_ext, right_ext, bottom_ext = compute_detection_extents(scale, image_type)
    max_dx_neg = max(0, origin_crop_x - left_ext)
    max_dx_pos = max(0, cw - origin_crop_x - right_ext)
    max_dy_neg = max(0, origin_crop_y - top_ext)
    max_dy_pos = max(0, ch - origin_crop_y - bottom_ext)
    return (max_dx_neg, max_dx_pos, max_dy_neg, max_dy_pos)


def main() -> None:
    parser = argparse.ArgumentParser(description="Show 4 max-diagonal augment images in a 2x2 grid.")
    parser.add_argument(
        "image",
        nargs="?",
        help="Path to labeled screenshot (default: first in data/labeled/screenshots/regular)",
    )
    parser.add_argument(
        "image_type",
        nargs="?",
        choices=("regular", "blueprint"),
        default="regular",
        help="Image type for crop/augment config (default: regular)",
    )
    args = parser.parse_args()

    data_dir = REPO_ROOT / "data"
    if args.image:
        png_path = Path(args.image).resolve()
        if not png_path.is_file():
            print(f"Error: not a file: {png_path}", file=sys.stderr)
            sys.exit(1)
        txt_path = png_path.with_suffix(".txt")
        if not txt_path.exists():
            print(f"Error: no origin file {txt_path}", file=sys.stderr)
            sys.exit(1)
    else:
        subdir = data_dir / "labeled" / "screenshots" / args.image_type
        if not subdir.is_dir():
            print(f"Error: no directory {subdir}", file=sys.stderr)
            sys.exit(1)
        pngs = sorted(subdir.glob("*.png")) or sorted(subdir.glob("*.jpg"))
        if not pngs:
            print(f"Error: no images in {subdir}", file=sys.stderr)
            sys.exit(1)
        png_path = pngs[0]
        txt_path = png_path.with_suffix(".txt")
        if not txt_path.exists():
            print(f"Error: no origin file {txt_path}", file=sys.stderr)
            sys.exit(1)
        print(f"Using {png_path.name} (first labeled in {args.image_type})")

    origin = read_txt_origin(txt_path)
    if origin is None:
        print(f"Error: invalid origin in {txt_path}", file=sys.stderr)
        sys.exit(1)
    ox, oy = origin

    config = load_config()
    augment = get_nested(config, "extract", "augment") or {}
    typen = augment.get(args.image_type) or {}
    def f(k: str, default: float = 0.1) -> float:
        return max(0.0, min(1.0, float(typen.get(k, default))))
    x_neg, x_pos, y_neg, y_pos = f("x_neg"), f("x_pos"), f("y_neg"), f("y_pos")
    scale = float(get_nested(config, "extract", "regular_scale", default=1.0))
    if args.image_type == "blueprint":
        scale = float(get_nested(config, "extract", "blueprint_scale", default=1.0))
    fill = (get_nested(config, "extract", "augment", "fill") or "black").strip().lower()
    if fill not in ("black", "noise"):
        fill = "black"

    img = Image.open(png_path).convert("RGB")
    cropped, crop_left, crop_top = crop_to_inner_rect(img, x_neg, x_pos, y_neg, y_pos)
    cw, ch = cropped.size
    origin_crop_x = ox - crop_left
    origin_crop_y = oy - crop_top

    max_dx_neg, max_dx_pos, max_dy_neg, max_dy_pos = get_max_shift_limits(
        cw, ch, origin_crop_x, origin_crop_y, scale, args.image_type
    )
    print(f"Crop size {cw}x{ch}  origin_crop=({origin_crop_x},{origin_crop_y})")
    print(f"Max shifts: dx_neg={max_dx_neg} dx_pos={max_dx_pos} dy_neg={max_dy_neg} dy_pos={max_dy_pos}")

    # 4 diagonal corners: (-dx,-dy), (+dx,-dy), (+dx,+dy), (-dx,+dy)
    shifts = [
        (-max_dx_neg, -max_dy_neg, "(-dx,-dy) top-left"),
        (max_dx_pos, -max_dy_neg, "(+dx,-dy) top-right"),
        (max_dx_pos, max_dy_pos, "(+dx,+dy) bottom-right"),
        (-max_dx_neg, max_dy_pos, "(-dx,+dy) bottom-left"),
    ]
    images = []
    for dx, dy, label in shifts:
        out = apply_shift_with_fill(cropped, dx, dy, fill)
        images.append((out, label))

    # Scale down for display so 2x2 fits on screen (max ~800px total width)
    max_side = 420
    scaled = []
    for im, label in images:
        w, h = im.size
        if w > max_side or h > max_side:
            r = min(max_side / w, max_side / h)
            im = im.resize((int(w * r), int(h * r)), Image.Resampling.NEAREST)
        scaled.append((im, label))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(10, 10))
    fig.suptitle(f"Max augment diagonals — {png_path.name} ({args.image_type})", fontsize=12)
    for ax, (im, label) in zip(axes.flat, scaled):
        ax.imshow(im)
        ax.set_title(label, fontsize=10)
        ax.axis("off")
    plt.tight_layout()
    out_path = REPO_ROOT / "scripts" / "max_augment_diagonals.png"
    plt.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"Saved {out_path}")
    # Open with system default viewer
    if sys.platform == "darwin":
        subprocess.run(["open", str(out_path)], check=False)
    elif sys.platform == "linux":
        subprocess.run(["xdg-open", str(out_path)], check=False)
    elif sys.platform == "win32":
        os.startfile(str(out_path))
    else:
        print("Open the file manually to view.")


if __name__ == "__main__":
    main()
