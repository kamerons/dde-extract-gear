import numpy as np
import unittest
from unittest.mock import patch

from extract_gear.extract_image import ExtractImage

from test.util.test_util import TestUtil

class TestExtractImage(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    TestExtractImage.ORIGINAL_EXTRACTIMAGE_ATTRIBUTES = TestUtil.get_class_attributes(ExtractImage)


  @classmethod
  def tearDownClass(cls):
    TestUtil.restore_class_attributes(ExtractImage, TestExtractImage.ORIGINAL_EXTRACTIMAGE_ATTRIBUTES)


  def test_extractSetImage(self):
    self.zero_offset()
    self.zero_gear_offset()
    ExtractImage.Y_SET_OFFSET = 1
    ExtractImage.X_SET_OFFSET = 2
    ExtractImage.SET_HEIGHT = 3
    ExtractImage.SET_WIDTH = 4

    img = np.full((6,6,1), (0), np.uint8)
    img[1,2] = 255

    extract_image = ExtractImage()
    with patch.object(extract_image, 'get_start_coord', wraps=extract_image.get_start_coord) as spy:
      img = extract_image.extract_set_image(img, 11, 12)

      self.assertEqual((3,4,1), img.shape)
      self.assertEqual(255, img[0,0])
      spy.assert_called_once_with(11, 12, 1, 2)


  def test_getStartCoord_base(self):
    ExtractImage.Y_START = 2
    ExtractImage.X_START = 3
    extract_image = ExtractImage()

    start_coord_1 = extract_image.get_start_coord(1, 1, 0, 0)
    start_coord_2 = extract_image.get_start_coord(1, 1, 10, 20)

    self.assertEqual((2,3), start_coord_1)
    self.assertEqual((12,23), start_coord_2)


  def test_getStartCoord_otherGearPosition(self):
    self.zero_offset()
    ExtractImage.Y_GEAR_OFFSET = 30
    ExtractImage.X_GEAR_OFFSET = 20
    extract_image = ExtractImage()

    start_coord_1 = extract_image.get_start_coord(2, 3, 0, 0)
    start_coord_2 = extract_image.get_start_coord(3, 5, 0, 0)

    self.assertEqual((30,40), start_coord_1)
    self.assertEqual( (60,80), start_coord_2)


  def zero_offset(self):
    ExtractImage.Y_START = 0
    ExtractImage.X_START = 0


  def zero_gear_offset(self):
    ExtractImage.Y_GEAR_OFFSET = 0
    ExtractImage.X_GEAR_OFFSET = 0
