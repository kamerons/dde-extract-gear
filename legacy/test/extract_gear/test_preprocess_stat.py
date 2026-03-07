import numpy as np
import timeout_decorator
import unittest

from extract_gear.preprocess_stat import PreProcessStat

from test.util.test_util import TestUtil

class TestPreProcessSet(unittest.TestCase):

  RED = [0, 0, 255]
  GREEN = [0, 255, 0]
  GRAY = [60, 60, 60]

  BLACK = [0, 0, 0]
  WHITE = [255, 255, 255]

  @classmethod
  def setUpClass(cls):
    TestPreProcessSet.ORIGINAL_PREPROCESSSTAT_ATTRIBUTES = TestUtil.get_class_attributes(PreProcessStat)


  @classmethod
  def tearDownClass(cls):
    TestUtil.restore_class_attributes(PreProcessStat, TestPreProcessSet.ORIGINAL_PREPROCESSSTAT_ATTRIBUTES)


  def test_increaseContrast_colorsInBoundsPreserved(self):
    img = self.setup_squareImg(2)

    red_coord = (0, 0)
    green_coord = (0, 1)
    gray_coord = (1, 0)
    img[red_coord] = TestPreProcessSet.RED
    img[green_coord] = TestPreProcessSet.GREEN
    img[gray_coord] = TestPreProcessSet.GRAY
    processor = PreProcessStat(img)

    processor.increase_contrast()

    self.assertEqual(all(img[red_coord]), all(TestPreProcessSet.BLACK))
    self.assertEqual(all(img[green_coord]), all(TestPreProcessSet.BLACK))
    self.assertEqual(all(img[gray_coord]), all(TestPreProcessSet.BLACK))


  def test_increaseContrast_noiseInBoundsErased(self):
    img = self.setup_squareImg(2)
    other_coord = (1, 1)
    img[other_coord] = [255, 70, 30]
    processor = PreProcessStat(img)

    processor.increase_contrast()

    self.assertEqual(all(img[other_coord]), all(TestPreProcessSet.WHITE))


  def test_increaseContrast_outOfBoundsErased(self):
    self.setup_squareBounds(1)
    img = np.full((2, 2, 3), (0, 0, 0), dtype=np.uint8)
    other_coord = (1, 1)
    img[other_coord] = TestPreProcessSet.BLACK
    processor = PreProcessStat(img)

    processor.increase_contrast()

    self.assertEqual(all(img[other_coord]), all(TestPreProcessSet.WHITE))


  @timeout_decorator.timeout(1)
  def test_trimSplotches_smallAreasRemoved(self):
    PreProcessStat.AREA_THRESHOLD = 5
    img = self.setup_squareImg(4)
    origin = (0,0)
    self.addSquareAtoLocation(img, origin, 2)
    processor = PreProcessStat(img)

    processor.trim_splotches()

    self.assertSquareIsColor(img, origin, 2, TestPreProcessSet.WHITE)


  @timeout_decorator.timeout(1)
  def test_trimSplotches_largeAreasPreserved(self):
    PreProcessStat.AREA_THRESHOLD = 3
    img = self.setup_squareImg(3)
    origin = (0,0)
    self.addSquareAtoLocation(img, origin, 2)
    processor = PreProcessStat(img)

    processor.trim_splotches()

    self.assertSquareIsColor(img, origin, 2, TestPreProcessSet.BLACK)


  @timeout_decorator.timeout(1)
  def test_sizeArea(self):
    img = self.setup_squareImg(4)
    origin = (0,0)
    self.addSquareAtoLocation(img, origin, 2)
    processor = PreProcessStat(img)

    x = processor.size_area((0, 0))[0]
    self.assertEqual(4, x)


  def setup_squareImg(self, size):
    self.setup_squareBounds(size)
    img = np.full((size, size, 3), (255, 255, 255), dtype=np.uint8)
    return img


  def setup_squareBounds(self, size):
    PreProcessStat.LOW_Y = 0
    PreProcessStat.LOW_X = 0
    PreProcessStat.HIGH_Y = size
    PreProcessStat.HIGH_X = size


  def addSquareAtoLocation(self, img, coord, size):
    for y in range(coord[0], coord[0] + size):
      for x in range(coord[1], coord[1] + size):
        img[y,x] = TestPreProcessSet.BLACK


  def assertSquareIsColor(self, img, coord, size, expected_color):
    for y in range(coord[0], coord[0] + size):
      for x in range(coord[1], coord[1] + size):
        self.assertEqual(all(img[y,x]), all(expected_color))
