"""Augmentation helpers for box-detector training: shift + fill, origin reading.

Used by the training processor to generate augmented samples in-process.
No file I/O for writing; origin can be read from paths or from (x, y) tuples.
"""

import random
from pathlib import Path
from typing import Iterator

from PIL import Image


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


def augment_sample(
    img: Image.Image,
    origin_x: int,
    origin_y: int,
    shift_fraction: float,
    fill_mode: str,
    count: int,
) -> Iterator[tuple[Image.Image, int, int]]:
    """Yield (augmented_image, new_origin_x, new_origin_y) count times for in-process training."""
    w, h = img.size
    shift_fraction = max(0.0, min(1.0, shift_fraction))
    max_shift = max(1, int(min(w, h) * shift_fraction))
    for _ in range(count):
        dx = random.randint(-max_shift, max_shift)
        dy = random.randint(-max_shift, max_shift)
        out_img = apply_shift_with_fill(img, dx, dy, fill_mode)
        yield out_img, origin_x + dx, origin_y + dy
