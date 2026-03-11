"""
Extract cluster images from a binarized level strip (black foreground, white background).

Used for digit-detector-based level parsing: clusters are digits and the slash,
ordered left-to-right. Caller resizes each crop to 56x56 and runs the digit model.
"""

import numpy as np

# Minimum black pixel count to keep a component (drop dust/noise)
LEVEL_CLUSTER_MIN_AREA = 15

# Padding added around each cluster bounding box (pixels)
LEVEL_CLUSTER_PADDING = 2


def _is_black_level(pixel: np.ndarray) -> bool:
    """True if pixel is foreground (black). Accepts (3,) RGB or scalar."""
    if pixel.size >= 3:
        return int(pixel[0]) < 128 and int(pixel[1]) < 128 and int(pixel[2]) < 128
    return int(pixel.flat[0]) < 128


def _get_black_mask(img: np.ndarray) -> np.ndarray:
    """Return (H, W) bool mask: True where image is black (foreground)."""
    if img.ndim == 3:
        return (img[:, :, 0] < 128) & (img[:, :, 1] < 128) & (img[:, :, 2] < 128)
    return img < 128


def _add_neighbors_level(
    mask: np.ndarray,
    coord: tuple[int, int],
    visited: set[tuple[int, int]],
) -> list[tuple[int, int]]:
    """4-connected neighbors of coord that are foreground and not visited."""
    h, w = mask.shape
    y, x = coord
    out: list[tuple[int, int]] = []
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        ny, nx = y + dy, x + dx
        if 0 <= ny < h and 0 <= nx < w and (ny, nx) not in visited and mask[ny, nx]:
            out.append((ny, nx))
    return out


def _component_at(mask: np.ndarray, start: tuple[int, int]) -> set[tuple[int, int]]:
    """Flood-fill from start; return set of (y, x) in the same connected component."""
    visited: set[tuple[int, int]] = {start}
    to_visit = list(_add_neighbors_level(mask, start, visited))
    while to_visit:
        cur = to_visit.pop()
        if cur in visited:
            continue
        visited.add(cur)
        for n in _add_neighbors_level(mask, cur, visited):
            if n not in visited:
                to_visit.append(n)
    return visited


def _component_centroid_x(coords: set[tuple[int, int]]) -> float:
    """Horizontal centroid for sorting left-to-right."""
    if not coords:
        return 0.0
    return sum(x for (_, x) in coords) / len(coords)


def _crop_cluster_to_image(
    img: np.ndarray,
    coords: set[tuple[int, int]],
    padding: int,
) -> np.ndarray:
    """
    Extract cluster as RGB patch: bounding box of coords + padding, white background,
    black foreground. img is (H, W) or (H, W, 3).
    """
    if not coords:
        return np.ones((1, 1, 3), dtype=np.uint8) * 255
    ys = [y for y, _ in coords]
    xs = [x for _, x in coords]
    min_y = max(0, min(ys) - padding)
    max_y = min(img.shape[0], max(ys) + 1 + padding)
    min_x = max(0, min(xs) - padding)
    max_x = min(img.shape[1], max(xs) + 1 + padding)
    h, w = max_y - min_y, max_x - min_x
    if h <= 0 or w <= 0:
        return np.ones((1, 1, 3), dtype=np.uint8) * 255
    if img.ndim == 2:
        patch = np.ones((h, w, 3), dtype=np.uint8) * 255
        for (py, px) in coords:
            ly, lx = py - min_y, px - min_x
            if 0 <= ly < h and 0 <= lx < w:
                patch[ly, lx, :] = 0
    else:
        patch = np.ones((h, w, 3), dtype=np.uint8) * 255
        for (py, px) in coords:
            ly, lx = py - min_y, px - min_x
            if 0 <= ly < h and 0 <= lx < w:
                patch[ly, lx, :] = img[py, px, :]
    return patch


def extract_level_clusters(binarized: np.ndarray) -> list[np.ndarray]:
    """
    Extract cluster crops from a binarized level image in left-to-right order.

    binarized: (H, W) or (H, W, 3) with black = foreground (0), white = background (255).
    Returns: List of RGB numpy arrays (variable size), one per connected black component
    with area >= LEVEL_CLUSTER_MIN_AREA, sorted by horizontal centroid.
    """
    mask = _get_black_mask(binarized)
    h, w = mask.shape
    seen: set[tuple[int, int]] = set()
    components: list[set[tuple[int, int]]] = []
    for y in range(h):
        for x in range(w):
            if (y, x) in seen or not mask[y, x]:
                continue
            comp = _component_at(mask, (y, x))
            seen.update(comp)
            if len(comp) >= LEVEL_CLUSTER_MIN_AREA:
                components.append(comp)
    components.sort(key=_component_centroid_x)
    return [
        _crop_cluster_to_image(binarized, comp, LEVEL_CLUSTER_PADDING)
        for comp in components
    ]
