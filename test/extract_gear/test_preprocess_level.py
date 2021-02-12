import numpy as np
import unittest

from extract_gear.preprocess_level import PreProcessLevel

class TestPreProcessLevel(unittest.TestCase):

  def test_process_level(self):
    shape = (2, 2, 3)
    img = np.full(shape, (0, 0, 0), dtype=np.uint8)

    img[0, 0] = [240, 240, 40]
    img[1, 1] = [255, 0, 240]

    preprocessor = PreProcessLevel(img)
    preprocessor.process_level()

    self.assertEqual(all([0, 0, 0]), all(img[0, 0]), msg="pixels inside border that are cyan are set to black")
    self.assertEqual(all([255, 255, 255]), all(img[1, 1]), msg="pixels inside border that aren't white are cleared")
