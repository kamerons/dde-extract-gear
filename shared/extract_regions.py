"""
Extract region constants and box computation for the config UI and splitter.

Ported from legacy/extract_gear/image_splitter.py. Computes region boxes for the
first card (gear_coord 1,1) given user origin and scale. All pixel values are
scaled by the scale factor; origin is the top-left of the armor tab (later
provided by the box-detector neural network at inference time).
"""

from dataclasses import dataclass
from typing import Callable

# --- Group data: base offsets for first card and spacing (scaled at runtime) ---
# Standard (regular) layout
STANDARD_START_Y = 375
STANDARD_START_X = 390
STANDARD_Y_GEAR_OFFSET = 177
STANDARD_X_GEAR_OFFSET = 174

# Blueprint layout
BLUEPRINT_START_Y = 293
BLUEPRINT_START_X = 423
BLUEPRINT_Y_GEAR_OFFSET = 129
BLUEPRINT_X_GEAR_OFFSET = 126

# --- Region type definitions (size (h, w), rel_start_offset (y, x), grid, pass_fn, next_offset) ---
# CARD: single rect
CARD_SIZE = (430, 350)
CARD_REL_START = (-112, -10)
CARD_GRID = (1, 1)
CARD_PASS = lambda col, row: False
CARD_NEXT_OFFSET = (0, 0)

# SET: single rect
SET_SIZE = (20, 140)
SET_REL_START = (-100, 100)
SET_GRID = (1, 1)
SET_PASS = lambda col, row: False
SET_NEXT_OFFSET = (0, 0)

# STAT: 3 rows x 6 cols, skip col>=4 and row!=1
STAT_SIZE = (56, 56)
STAT_REL_START = (0, 0)
STAT_GRID = (3, 6)
STAT_PASS = lambda col, row: col >= 4 and row != 1
STAT_NEXT_OFFSET = (87, 60)

# LEVEL: 2 rows x 3 cols, skip row==0 and col==2
LEVEL_SIZE = (30, 70)
LEVEL_REL_START = (268, 180)
LEVEL_GRID = (2, 3)
LEVEL_PASS = lambda col, row: row == 0 and col == 2
LEVEL_NEXT_OFFSET = (-88, 60)


@dataclass
class Box:
    """A single region box in image coordinates (x, y, width, height)."""

    x: int
    y: int
    width: int
    height: int
    type: str  # "card", "set", "stat", "level"


def _get_group_base(is_blueprint: bool) -> tuple[int, int, int, int]:
    """Return (start_y, start_x, y_gear_offset, x_gear_offset) base values."""
    if is_blueprint:
        return (
            BLUEPRINT_START_Y,
            BLUEPRINT_START_X,
            BLUEPRINT_Y_GEAR_OFFSET,
            BLUEPRINT_X_GEAR_OFFSET,
        )
    return (
        STANDARD_START_Y,
        STANDARD_START_X,
        STANDARD_Y_GEAR_OFFSET,
        STANDARD_X_GEAR_OFFSET,
    )


def _start_coord(
    origin_y: int,
    origin_x: int,
    rel_y: int,
    rel_x: int,
    scale: float,
    y_gear_offset: int,
    x_gear_offset: int,
    gear_row: int = 1,
    gear_col: int = 1,
) -> tuple[int, int]:
    """Compute (y, x) of region start. gear_row/col are 1-based; we use (1,1) for first card."""
    y = origin_y + (gear_row - 1) * int(y_gear_offset * scale) + int(rel_y * scale)
    x = origin_x + (gear_col - 1) * int(x_gear_offset * scale) + int(rel_x * scale)
    return (y, x)


def _boxes_for_grid(
    origin_y: int,
    origin_x: int,
    scale: float,
    is_blueprint: bool,
    size: tuple[int, int],
    rel_start: tuple[int, int],
    rows: int,
    cols: int,
    pass_fn: Callable[[int, int], bool],
    next_offset: tuple[int, int],
    box_type: str,
) -> list[Box]:
    """Emit boxes for a grid region (or single cell if rows==cols==1)."""
    _, _, y_go, x_go = _get_group_base(is_blueprint)
    h, w = size
    sh, sw = int(h * scale), int(w * scale)
    rel_y, rel_x = rel_start
    no_y, no_x = next_offset
    no_y_s, no_x_s = int(no_y * scale), int(no_x * scale)
    base_y, base_x = _start_coord(
        origin_y, origin_x, rel_y, rel_x, scale, y_go, x_go, 1, 1
    )
    out: list[Box] = []
    for row in range(rows):
        for col in range(cols):
            if pass_fn(col, row):
                continue
            y = base_y + no_y_s * row
            x = base_x + no_x_s * col
            out.append(Box(x=x, y=y, width=sw, height=sh, type=box_type))
    return out


def compute_boxes(
    origin_x: int,
    origin_y: int,
    scale: float,
    image_type: str,
) -> list[dict]:
    """
    Compute all region boxes for the first card.

    Args:
        origin_x: Top-left x of the armor tab (first card) in image coordinates.
        origin_y: Top-left y of the armor tab (first card) in image coordinates.
        scale: Scale factor applied to offsets and sizes.
        image_type: "regular" or "blueprint".

    Returns:
        List of dicts with keys: x, y, width, height, type (card, set, stat, level).
    """
    is_blueprint = image_type.lower() == "blueprint"
    origin_y_int = int(origin_y)
    origin_x_int = int(origin_x)

    boxes: list[Box] = []

    # CARD
    boxes.extend(
        _boxes_for_grid(
            origin_y_int,
            origin_x_int,
            scale,
            is_blueprint,
            CARD_SIZE,
            CARD_REL_START,
            1,
            1,
            CARD_PASS,
            CARD_NEXT_OFFSET,
            "card",
        )
    )
    # SET
    boxes.extend(
        _boxes_for_grid(
            origin_y_int,
            origin_x_int,
            scale,
            is_blueprint,
            SET_SIZE,
            SET_REL_START,
            1,
            1,
            SET_PASS,
            SET_NEXT_OFFSET,
            "set",
        )
    )
    # STAT
    boxes.extend(
        _boxes_for_grid(
            origin_y_int,
            origin_x_int,
            scale,
            is_blueprint,
            STAT_SIZE,
            STAT_REL_START,
            STAT_GRID[0],
            STAT_GRID[1],
            STAT_PASS,
            STAT_NEXT_OFFSET,
            "stat",
        )
    )
    # LEVEL
    boxes.extend(
        _boxes_for_grid(
            origin_y_int,
            origin_x_int,
            scale,
            is_blueprint,
            LEVEL_SIZE,
            LEVEL_REL_START,
            LEVEL_GRID[0],
            LEVEL_GRID[1],
            LEVEL_PASS,
            LEVEL_NEXT_OFFSET,
            "level",
        )
    )

    return [
        {"x": b.x, "y": b.y, "width": b.width, "height": b.height, "type": b.type}
        for b in boxes
    ]
