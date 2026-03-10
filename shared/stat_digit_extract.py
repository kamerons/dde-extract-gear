"""
Extract digit images from a 56x56 stat icon crop.

Ported from legacy/extract_gear/preprocess.py and preprocess_stat.py.
Expects BGR images (e.g. from cv2.imread). Returns list of 56x56 BGR digit images.
"""

import numpy as np

# --- Pixel thresholds (legacy PreProcessor) ---
PIXEL_VALUE_THRESHOLD = 3
PIXEL_COLOR_THRESHOLD = 40
WHITE_VALUE_THRESHOLD = 180

# --- Stat digit ROI and behavior ---
AREA_THRESHOLD = 30
LOW_Y = 31
LOW_X = 11
HIGH_Y = 55
HIGH_X = 51
DIGIT_SIZE = 56
CENTER_OFFSET = 25


def _is_red(pixel: np.ndarray) -> bool:
    blue, green, red = pixel[0], pixel[1], pixel[2]
    return (
        red > PIXEL_COLOR_THRESHOLD
        and blue < PIXEL_VALUE_THRESHOLD
        and green < PIXEL_VALUE_THRESHOLD
    )


def _is_green(pixel: np.ndarray) -> bool:
    blue, green, red = pixel[0], pixel[1], pixel[2]
    return (
        green > PIXEL_COLOR_THRESHOLD
        and blue < PIXEL_VALUE_THRESHOLD
        and red < PIXEL_VALUE_THRESHOLD
    )


def _is_black(pixel: np.ndarray) -> bool:
    blue, green, red = pixel[0], pixel[1], pixel[2]
    return blue == 0 and green == 0 and red == 0


def _is_gray(pixel: np.ndarray) -> bool:
    blue, green, red = pixel[0], pixel[1], pixel[2]
    return (
        _safe_difference(blue, green) < PIXEL_VALUE_THRESHOLD
        and _safe_difference(blue, red) < PIXEL_VALUE_THRESHOLD
        and blue > PIXEL_COLOR_THRESHOLD
    )


def _safe_difference(c1: int, c2: int) -> int:
    return c1 - c2 if c1 > c2 else c2 - c1


def _increase_contrast(img: np.ndarray) -> None:
    y_size, x_size = img.shape[:2]
    for x in range(x_size):
        for y in range(y_size):
            if y not in range(LOW_Y, HIGH_Y) or x not in range(LOW_X, HIGH_X):
                img[y, x] = [255, 255, 255]
                continue
            coord = (y, x)
            pixel = img[coord]
            if _is_red(pixel) or _is_green(pixel) or _is_gray(pixel):
                img[coord] = [0, 0, 0]
            else:
                img[coord] = [255, 255, 255]


def _add_neighbors(
    img: np.ndarray,
    coord: tuple[int, int],
    visited: set[tuple[int, int]] | None = None,
) -> list[tuple[int, int]]:
    visited = visited or set()
    y, x = coord
    out = []
    if (y - 1, x) not in visited and y - 1 >= LOW_Y and _is_black(img[y - 1, x]):
        out.append((y - 1, x))
    if (y + 1, x) not in visited and y + 1 < HIGH_Y and _is_black(img[y + 1, x]):
        out.append((y + 1, x))
    if (y, x - 1) not in visited and x - 1 >= LOW_X and _is_black(img[y, x - 1]):
        out.append((y, x - 1))
    if (y, x + 1) not in visited and x + 1 < HIGH_X and _is_black(img[y, x + 1]):
        out.append((y, x + 1))
    return out


def _size_area(img: np.ndarray, coord: tuple[int, int]) -> tuple[int, set[tuple[int, int]]]:
    visited: set[tuple[int, int]] = {coord}
    to_visit: list[tuple[int, int]] = list(_add_neighbors(img, coord, visited))
    a_size = 1
    while to_visit:
        cur = to_visit.pop()
        if cur in visited:
            continue
        visited.add(cur)
        a_size += 1
        for n in _add_neighbors(img, cur, visited):
            if n not in visited:
                to_visit.append(n)
    return a_size, visited


def _remove_area(img: np.ndarray, start_coord: tuple[int, int]) -> None:
    to_visit: list[tuple[int, int]] = []
    img[start_coord] = [255, 255, 255]
    for c in _add_neighbors(img, start_coord):
        to_visit.append(c)
    while to_visit:
        cur_coord = to_visit.pop()
        img[cur_coord] = [255, 255, 255]
        for c in _add_neighbors(img, cur_coord):
            to_visit.append(c)


def _copy_digit(coordinates: set[tuple[int, int]]) -> np.ndarray:
    min_y = HIGH_Y
    min_x = HIGH_X
    for (py, px) in coordinates:
        min_y = min(min_y, py)
        min_x = min(min_x, px)
    digit = np.full((DIGIT_SIZE, DIGIT_SIZE, 3), (255, 255, 255), dtype=np.uint8)
    y_adj = CENTER_OFFSET - min_y
    x_adj = CENTER_OFFSET - min_x
    for (py, px) in coordinates:
        y = py + y_adj
        x = px + x_adj
        if 0 <= y < DIGIT_SIZE and 0 <= x < DIGIT_SIZE:
            digit[y, x] = [0, 0, 0]
    return digit


def _trim_splotches(img: np.ndarray) -> list[np.ndarray]:
    digits: list[np.ndarray] = []
    visited: set[tuple[int, int]] = set()
    for x in range(LOW_X, HIGH_X):
        for y in range(LOW_Y, HIGH_Y):
            coord = (y, x)
            if coord in visited:
                continue
            if not _is_black(img[coord]):
                continue
            a_size, a_visited = _size_area(img, coord)
            visited.update(a_visited)
            if a_size < AREA_THRESHOLD:
                _remove_area(img, coord)
            else:
                digits.append(_copy_digit(a_visited))
    return digits


def extract_digits(stat_image: np.ndarray) -> list[np.ndarray]:
    """
    Extract digit (and blob) crops from a 56x56 stat icon image.

    stat_image: BGR numpy array (e.g. from cv2.imread), shape (56, 56, 3).
    Returns: List of 56x56 BGR images, one per connected black region in the
    digit ROI (left-to-right order). Small regions below AREA_THRESHOLD are
    dropped; the rest are centered in a 56x56 white canvas.
    """
    img = stat_image.copy()
    _increase_contrast(img)
    return _trim_splotches(img)
