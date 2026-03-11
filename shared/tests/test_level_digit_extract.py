"""Unit tests for level cluster extraction (shared.level_digit_extract)."""

import unittest

import numpy as np

from shared.level_digit_extract import extract_level_clusters


def _binarized_with_blobs(shape: tuple[int, int], blobs: list[list[tuple[int, int]]]) -> np.ndarray:
    """Build a binarized image (255=white, 0=black) with one connected black blob per list of (y,x) coords."""
    out = np.ones((*shape, 3), dtype=np.uint8) * 255
    for blob in blobs:
        for y, x in blob:
            if 0 <= y < shape[0] and 0 <= x < shape[1]:
                out[y, x, :] = 0
    return out


class TestExtractLevelClusters(unittest.TestCase):
    def test_three_blobs_left_to_right_returns_three_crops(self):
        # Three separate blobs (e.g. "1", "/", "6") in a row; each >= MIN_AREA
        def box(y0, x0, h, w):
            return [(y, x) for y in range(y0, y0 + h) for x in range(x0, x0 + w)]
        blobs = [box(5, 5, 4, 4), box(5, 20, 4, 4), box(5, 35, 4, 4)]
        img = _binarized_with_blobs((15, 45), blobs)
        clusters = extract_level_clusters(img)
        self.assertEqual(len(clusters), 3, "should detect 3 clusters")

    def test_five_blobs_returns_five_crops(self):
        blobs = [
            [(5, 5)], [(5, 15)], [(5, 25)], [(5, 35)], [(5, 45)],
        ]
        # Make each blob above min area by adding a few pixels
        for i, blob in enumerate(blobs):
            for dy in range(4):
                for dx in range(4):
                    blobs[i].append((5 + dy, blob[0][1] + dx))
        img = _binarized_with_blobs((20, 55), blobs)
        clusters = extract_level_clusters(img)
        self.assertEqual(len(clusters), 5)

    def test_order_left_to_right(self):
        def box(y0, x0, h, w):
            return [(y, x) for y in range(y0, y0 + h) for x in range(x0, x0 + w)]
        blobs = [box(5, 2, 4, 4), box(5, 10, 4, 4), box(5, 18, 4, 4)]
        img = _binarized_with_blobs((15, 25), blobs)
        clusters = extract_level_clusters(img)
        self.assertEqual(len(clusters), 3)
        self.assertGreaterEqual(clusters[0].shape[1], 1)
        self.assertGreaterEqual(clusters[1].shape[1], 1)

    def test_tiny_blobs_filtered_out(self):
        def box(y0, x0, h, w):
            return [(y, x) for y in range(y0, y0 + h) for x in range(x0, x0 + w)]
        # One big blob and two single-pixel blobs (below LEVEL_CLUSTER_MIN_AREA)
        blobs = [
            box(5, 5, 4, 5),   # 20 pixels
            [(5, 25)],         # 1 pixel
            [(5, 35)],         # 1 pixel
        ]
        img = _binarized_with_blobs((15, 45), blobs)
        clusters = extract_level_clusters(img)
        self.assertEqual(len(clusters), 1, "only the large blob should remain")

    def test_empty_or_all_white_returns_empty_list(self):
        img = np.ones((10, 50, 3), dtype=np.uint8) * 255
        clusters = extract_level_clusters(img)
        self.assertEqual(clusters, [])

    def test_grayscale_2d_accepted(self):
        # (H, W) with 0 and 255; each region >= 15 pixels
        img = np.ones((15, 40), dtype=np.uint8) * 255
        img[4:8, 5:9] = 0   # 16 px
        img[4:8, 18:22] = 0  # 16 px
        img[4:8, 31:35] = 0  # 16 px
        clusters = extract_level_clusters(img)
        self.assertEqual(len(clusters), 3)
