"""Augmentation helpers for box-detector training: crop, shift + fill, origin reading.

Used by the training processor to generate augmented samples in-process.
Labels are on uncropped images; crop step produces cropped image and origin in cropped coords.
Config x_neg/x_pos/y_neg/y_pos define crop margins only (max fraction discarded per side).
Augmentation translation limits are geometric only (label + box extents in cropped space);
the full detection box (card + regions) can be pushed to the crop edges. No config cap on shift.
No file I/O for writing; origin can be read from paths or from (x, y) tuples.
"""

import random
from pathlib import Path
from typing import Any, Iterator

from PIL import Image

from shared.extract_regions import compute_detection_extents


def compute_translation_margin_lines(
    origin_x: int,
    origin_y: int,
    image_w: int,
    image_h: int,
    x_neg: float,
    x_pos: float,
    y_neg: float,
    y_pos: float,
    scale: float = 1.0,
    image_type: str = "regular",
) -> dict[str, Any]:
    """
    Compute four line segments (left, top, right, bottom) in cropped pixel coordinates
    from the detection box edges to the crop edges. These represent the maximum
    translation in each direction without the box going off-frame.

    Returns dict with keys "left", "top", "right", "bottom"; each value is
    {"x1", "y1", "x2", "y2"} where (x1,y1) is at the box edge and (x2,y2) is at
    the crop edge (arrow drawn at crop edge). Coordinates are in cropped space.
    """
    x_neg = max(0.0, min(1.0, x_neg))
    x_pos = max(0.0, min(1.0, x_pos))
    y_neg = max(0.0, min(1.0, y_neg))
    y_pos = max(0.0, min(1.0, y_pos))
    if x_neg + x_pos >= 1.0:
        x_pos = 1.0 - x_neg - 0.001
    if y_neg + y_pos >= 1.0:
        y_pos = 1.0 - y_neg - 0.001
    crop_left = int(image_w * x_neg)
    crop_top = int(image_h * y_neg)
    crop_right = int(image_w * (1.0 - x_pos))
    crop_bottom = int(image_h * (1.0 - y_pos))
    crop_right = max(crop_right, crop_left + 1)
    crop_bottom = max(crop_bottom, crop_top + 1)
    crop_w = crop_right - crop_left
    crop_h = crop_bottom - crop_top

    origin_crop_x = origin_x - crop_left
    origin_crop_y = origin_y - crop_top
    left_ext, top_ext, right_ext, bottom_ext = compute_detection_extents(
        scale, image_type
    )
    box_left = origin_crop_x - left_ext
    box_top = origin_crop_y - top_ext
    box_right = origin_crop_x + right_ext
    box_bottom = origin_crop_y + bottom_ext
    box_center_x = (box_left + box_right) // 2
    box_center_y = (box_top + box_bottom) // 2

    # Clamp box to crop so segments stay inside
    box_left_c = max(0, min(crop_w, box_left))
    box_top_c = max(0, min(crop_h, box_top))
    box_right_c = max(0, min(crop_w, box_right))
    box_bottom_c = max(0, min(crop_h, box_bottom))
    bcx = max(0, min(crop_w, box_center_x))
    bcy = max(0, min(crop_h, box_center_y))

    def seg(x1: int, y1: int, x2: int, y2: int) -> dict[str, int]:
        return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}

    return {
        "left": seg(box_left_c, bcy, 0, bcy),
        "top": seg(bcx, box_top_c, bcx, 0),
        "right": seg(box_right_c, bcy, crop_w, bcy),
        "bottom": seg(bcx, box_bottom_c, bcx, crop_h),
    }


def crop_to_inner_rect(
    img: Image.Image,
    x_neg: float,
    x_pos: float,
    y_neg: float,
    y_pos: float,
) -> tuple[Image.Image, int, int]:
    """
    Crop image to the inner rectangle defined by margin fractions.
    Bounds are fractions in [0, 1]; margins (x_neg from left, x_pos from right, etc.) are removed.
    Returns (cropped_img, crop_left, crop_top) so callers can transform origin:
        origin_crop_x = origin_x - crop_left, origin_crop_y = origin_y - crop_top.
    Cropped size is at least 1 pixel per axis (bounds are clamped if needed).
    """
    w, h = img.size
    x_neg = max(0.0, min(1.0, x_neg))
    x_pos = max(0.0, min(1.0, x_pos))
    y_neg = max(0.0, min(1.0, y_neg))
    y_pos = max(0.0, min(1.0, y_pos))
    # Ensure at least 1 pixel crop size
    if x_neg + x_pos >= 1.0:
        x_pos = 1.0 - x_neg - 0.001
    if y_neg + y_pos >= 1.0:
        y_pos = 1.0 - y_neg - 0.001
    crop_left = int(w * x_neg)
    crop_top = int(h * y_neg)
    crop_right = int(w * (1.0 - x_pos))
    crop_bottom = int(h * (1.0 - y_pos))
    crop_right = max(crop_right, crop_left + 1)
    crop_bottom = max(crop_bottom, crop_top + 1)
    cropped = img.crop((crop_left, crop_top, crop_right, crop_bottom))
    return cropped, crop_left, crop_top


def augment_sample_label_aware(
    img: Image.Image,
    origin_crop_x: int,
    origin_crop_y: int,
    shift_x_neg: float,
    shift_x_pos: float,
    shift_y_neg: float,
    shift_y_pos: float,
    fill_mode: str,
    count: int,
    scale: float = 1.0,
    image_type: str = "regular",
) -> Iterator[tuple[Image.Image, int, int]]:
    """
    Yield (augmented_image, new_origin_x, new_origin_y) count times.
    img is the cropped image; origin_crop_* is the origin in cropped image coords.
    shift_x_neg, shift_x_pos, shift_y_neg, shift_y_pos are legacy/crop-margin args and are
    not used to cap translation. Translation is limited only so the full detection box
    (card + set + stat + level) stays in [0, cw) x [0, ch)—geometric limits from
    origin_crop and box extents; the box can be pushed to the crop edges.
    scale and image_type are used to compute the box extents (left/top/right/bottom
    from origin). The returned (new_origin_x, new_origin_y) is the actual content
    position in the augmented image (origin_crop + shift), so GT boxes align with the image.
    """
    cw, ch = img.size
    left_ext, top_ext, right_ext, bottom_ext = compute_detection_extents(scale, image_type)
    # Geometric limits only (no config cap): box can be pushed to crop edges in all 4 directions.
    max_dx_neg = max(0, origin_crop_x - left_ext)
    max_dx_pos = max(0, cw - origin_crop_x - right_ext)
    max_dy_neg = max(0, origin_crop_y - top_ext)
    max_dy_pos = max(0, ch - origin_crop_y - bottom_ext)
    for _ in range(count):
        dx = random.randint(-max_dx_neg, max_dx_pos) if (max_dx_neg or max_dx_pos) else 0
        dy = random.randint(-max_dy_neg, max_dy_pos) if (max_dy_neg or max_dy_pos) else 0
        out_img = apply_shift_with_fill(img, dx, dy, fill_mode)
        # Return actual content position in augmented image so GT boxes align with the card
        yield out_img, origin_crop_x + dx, origin_crop_y + dy


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
    shift_x_neg: float,
    shift_x_pos: float,
    shift_y_neg: float,
    shift_y_pos: float,
    fill_mode: str,
    count: int,
) -> Iterator[tuple[Image.Image, int, int]]:
    """
    Yield (augmented_image, new_origin_x, new_origin_y) count times for in-process training.
    Shift bounds are fractions of width (x) or height (y), in [0, 1]. Pixel bounds are computed
    per axis; dx in [-w*shift_x_neg, w*shift_x_pos], dy in [-h*shift_y_neg, h*shift_y_pos].
    """
    w, h = img.size
    shift_x_neg = max(0.0, min(1.0, shift_x_neg))
    shift_x_pos = max(0.0, min(1.0, shift_x_pos))
    shift_y_neg = max(0.0, min(1.0, shift_y_neg))
    shift_y_pos = max(0.0, min(1.0, shift_y_pos))
    max_dx_neg = max(0, int(w * shift_x_neg))
    max_dx_pos = max(0, int(w * shift_x_pos))
    max_dy_neg = max(0, int(h * shift_y_neg))
    max_dy_pos = max(0, int(h * shift_y_pos))
    # At least 1 pixel range on each axis so we can generate a valid shift
    if max_dx_neg == 0 and max_dx_pos == 0:
        max_dx_pos = 1
    if max_dy_neg == 0 and max_dy_pos == 0:
        max_dy_pos = 1
    for _ in range(count):
        dx = random.randint(-max_dx_neg, max_dx_pos)
        dy = random.randint(-max_dy_neg, max_dy_pos)
        out_img = apply_shift_with_fill(img, dx, dy, fill_mode)
        yield out_img, origin_x + dx, origin_y + dy
