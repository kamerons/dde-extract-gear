"""Augment labeled screenshots by random shift + black/noise fill for box-detector training.

Run from repo root: python3 scripts/augment_screenshots.py

Reads from data/labeled/screenshots/<type>/ (requires both .png and .txt per image).
Writes to data/labeled/augmented/<type>/ with naming <id>_<n>.png and <id>_<n>.txt.
Env: EXTRACT_AUGMENT_SHIFT_REGULAR, EXTRACT_AUGMENT_SHIFT_BLUEPRINT (fraction 0-1),
     EXTRACT_AUGMENT_FILL=black|noise, EXTRACT_AUGMENT_COUNT (augmented copies per source).
See scripts/AUGMENT.md for details.
"""

import os
import random
import sys
from pathlib import Path

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
LABELED_SCREENSHOTS = REPO_ROOT / "data" / "labeled" / "screenshots"
AUGMENTED_DIR = REPO_ROOT / "data" / "labeled" / "augmented"


def _read_config():
    shift_regular = float(os.getenv("EXTRACT_AUGMENT_SHIFT_REGULAR", "0.1"))
    shift_blueprint = float(os.getenv("EXTRACT_AUGMENT_SHIFT_BLUEPRINT", "0.1"))
    fill = (os.getenv("EXTRACT_AUGMENT_FILL", "black") or "black").strip().lower()
    if fill not in ("black", "noise"):
        fill = "black"
    count = int(os.getenv("EXTRACT_AUGMENT_COUNT", "3"))
    count = max(1, min(count, 100))
    return {
        "shift_regular": shift_regular,
        "shift_blueprint": shift_blueprint,
        "fill": fill,
        "count": count,
    }


def read_txt_origin(txt_path: Path) -> tuple[int, int] | None:
    """Read origin_x origin_y from a single-line .txt file. Returns None if missing or invalid."""
    if not txt_path.exists():
        return None
    try:
        line = txt_path.read_text().strip()
        parts = line.split()
        if len(parts) != 2:
            return None
        return int(parts[0]), int(parts[1])
    except (ValueError, OSError):
        return None


def apply_shift_with_fill(
    img: Image.Image,
    dx: int,
    dy: int,
    fill_mode: str,
) -> Image.Image:
    """Create a new image of the same size: fill background, then paste img at (dx, dy)."""
    w, h = img.size
    if fill_mode == "noise":
        try:
            import numpy as np
            arr = np.random.randint(0, 256, (h, w, 3), dtype=np.uint8)
            canvas = Image.fromarray(arr)
        except ImportError:
            canvas = Image.new("RGB", (w, h), (0, 0, 0))
    else:
        canvas = Image.new("RGB", (w, h), (0, 0, 0))
    canvas.paste(img, (dx, dy))
    return canvas


def write_origin_txt(txt_path: Path, origin_x: int, origin_y: int) -> None:
    """Write a single line: origin_x origin_y."""
    txt_path.write_text(f"{origin_x} {origin_y}\n")


def augment_one_image(
    png_path: Path,
    txt_path: Path,
    out_dir: Path,
    shift_fraction: float,
    fill_mode: str,
    count: int,
) -> int:
    """Augment one source image count times. Returns number of augmented pairs written. Skips if no .txt."""
    origin = read_txt_origin(txt_path)
    if origin is None:
        return 0
    origin_x, origin_y = origin
    img = Image.open(png_path).convert("RGB")
    w, h = img.size
    max_shift = max(1, int(min(w, h) * shift_fraction))
    stem = png_path.stem
    written = 0
    for n in range(1, count + 1):
        dx = random.randint(-max_shift, max_shift)
        dy = random.randint(-max_shift, max_shift)
        out_img = apply_shift_with_fill(img, dx, dy, fill_mode)
        new_ox = origin_x + dx
        new_oy = origin_y + dy
        out_name = f"{stem}_{n}"
        out_png = out_dir / f"{out_name}.png"
        out_txt = out_dir / f"{out_name}.txt"
        out_img.save(out_png)
        write_origin_txt(out_txt, new_ox, new_oy)
        written += 1
    return written


def run_for_type(typename: str, config: dict) -> tuple[int, int]:
    """Process all images in labeled/screenshots/<typename>. Returns (sources_processed, augmented_written)."""
    src_dir = LABELED_SCREENSHOTS / typename
    out_dir = AUGMENTED_DIR / typename
    if not src_dir.exists():
        return 0, 0
    shift_fraction = config["shift_regular"] if typename == "regular" else config["shift_blueprint"]
    shift_fraction = max(0.0, min(1.0, shift_fraction))
    out_dir.mkdir(parents=True, exist_ok=True)
    pngs = sorted(src_dir.glob("*.png"))
    sources_ok = 0
    total_written = 0
    for png_path in pngs:
        txt_path = png_path.with_suffix(".txt")
        if not txt_path.exists():
            print(f"  Skip (no .txt): {png_path.name}", file=sys.stderr)
            continue
        n = augment_one_image(
            png_path,
            txt_path,
            out_dir,
            shift_fraction,
            config["fill"],
            config["count"],
        )
        if n:
            sources_ok += 1
            total_written += n
    return sources_ok, total_written


def main() -> None:
    config = _read_config()
    print("Augment config:", config)
    for typename in ("regular", "blueprint"):
        sources, written = run_for_type(typename, config)
        print(f"{typename}: {sources} sources -> {written} augmented images")
    print("Done.")


if __name__ == "__main__":
    main()
