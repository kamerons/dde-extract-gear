import numpy as np
import unittest

from extract_gear.preprocess_set import PreProcessSet

class TestPreProcessSet(unittest.TestCase):

  def test_process_set(self):
    shape = (2, 2, 3)
    img = np.full(shape, (0, 0, 0), dtype=np.uint8)

    img[0, 0] = [240, 240, 240]
    img[1, 1] = [255, 0, 240]

    preprocessor = PreProcessSet(img)
    preprocessor.process_set()

    self.assertEqual(all([0, 0, 0]), all(img[0, 0]), msg="pixels inside border that are white are set to black")
    self.assertEqual(all([255, 255, 255]), all(img[1, 1]), msg="pixels inside border that aren't white are cleared")
