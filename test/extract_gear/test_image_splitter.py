from copy import deepcopy
import numpy as np
import unittest
from unittest.mock import patch
from unittest.mock import Mock

from extract_gear.image_splitter import ImageSplitter, ImageTypeData, ImageGroupData

from test.util.test_util import TestUtil

class TestImageSplitter(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    TestImageSplitter.ORIGINAL_IMAGESPLITTER_ATTRIBUTES = deepcopy(TestUtil.get_class_attributes(ImageSplitter))


  @classmethod
  def tearDownClass(cls):
    TestUtil.restore_class_attributes(ImageSplitter, TestImageSplitter.ORIGINAL_IMAGESPLITTER_ATTRIBUTES)


  def setUp(self):
    self.setZeroStart()


  def test_extractStatImages_returnsCorrectSet(self):
    #test the real row, column, and pass_fn
    for attribute_name, attribute_value in TestImageSplitter.ORIGINAL_IMAGESPLITTER_ATTRIBUTES:
      if attribute_name == "STAT_DATA":
        orig_stat_data = attribute_value
        break

    ImageSplitter.STAT_DATA = ImageTypeData((2,2), (0,0), orig_stat_data.rows,
      orig_stat_data.columns, orig_stat_data.pass_fn, (2,2))

    img = np.full((6,12,1), 0, np.uint8)
    expected_row1 = [(0,0), (0,2), (0,4), (0,6)]
    expected_row2 = [(2,0), (2,2), (2,4), (2,6), (2,8), (2,10)]
    expected_row3 = [(4,0), (4,2), (4,4), (4,6)]
    full_coords = expected_row1 + expected_row2 + expected_row3
    for coord in full_coords:
      img[coord] = 255
    image_splitter = ImageSplitter()

    images = image_splitter.extract_stat_images(img, (1,1))

    #return 12 images of size 2x2
    for i in range(12):
      self.assertEqual(255, images[i][0,0])
      self.assertAllCoordsBut(images[i], [(0,0)], np.array([0], dtype=np.uint8))


  def test_extractLevelImages_returnsCorrectSet(self):
    #test the real row, column, and pass_fn
    for attribute_name, attribute_value in TestImageSplitter.ORIGINAL_IMAGESPLITTER_ATTRIBUTES:
      if attribute_name == "LEVEL_DATA":
        orig_level_data = attribute_value
        break

    ImageSplitter.LEVEL_DATA = ImageTypeData((2,2), (0,0), orig_level_data.rows,
      orig_level_data.columns, orig_level_data.pass_fn, (2,2))

    img = np.full((4,6,1), 0, np.uint8)
    expected_row1 = [(0,0), (0,2)]
    expected_row2 = [(2,0), (2,2), (2,4)]
    full_coords = expected_row1 + expected_row2
    for coord in full_coords:
      img[coord] = 255
    image_splitter = ImageSplitter()

    images = image_splitter.extract_level_images(img, (1,1))

    #return 6 images of size 2x2
    for i in range(5):
      self.assertEqual(255, images[i][0,0])
      self.assertAllCoordsBut(images[i], [(0,0)], np.array([0], dtype=np.uint8))


  def test_extractSetImage_usesCorrectData(self):
    ImageSplitter.SET_DATA = ImageTypeData((2,2), (0,0))

    img = np.full((3,3,1), 0, np.uint8)
    img[1,1] = 255
    image_splitter = ImageSplitter()

    img = image_splitter.extract_set_image(img, (1,1))

    self.assertEqual((2,2,1), img.shape)
    self.assertEqual(255, img[1,1])
    self.assertAllCoordsBut(img, [(1,1)], np.array([0], dtype=np.uint8))


  def test_extractStatCard_usesCorrectData(self):
    ImageSplitter.CARD_DATA = ImageTypeData((2,3), (0,0))

    img = np.full((3,3,1), 0, np.uint8)
    img[1,1] = 255
    image_splitter = ImageSplitter()

    img = image_splitter.extract_stat_card(img, (1,1))

    self.assertEqual((2,3,1), img.shape)
    self.assertEqual(255, img[1,1])
    self.assertAllCoordsBut(img, [(1,1)], np.array([0], dtype=np.uint8))


  def test_getSingleImageSplit_usesRelStart(self):
    end_coord = (1,3)
    image_type_data = ImageTypeData((1,1), end_coord)

    img = np.full((end_coord[0] + 1, end_coord[1] + 1, 1), 0, np.uint8)
    img[end_coord] = 255
    image_splitter = ImageSplitter()

    split_img = image_splitter.get_single_image_split(img, (1,1), image_type_data)

    self.assertEqual(255, split_img[0,0][0])


  def test_getSingleImageSplit_usesGearCoord(self):
    image_type_data = ImageTypeData((1,1), (0,0))
    ImageSplitter.STANDARD_GROUP_DATA = ImageGroupData(0, 0, 2, 1)
    gear_coord = (3,4)
    gear_offset= (2,1)

    y_end_coord = (gear_coord[0] - 1) * gear_offset[0]
    x_end_coord = (gear_coord[1] - 1) * gear_offset[1]

    y_size = y_end_coord + 1
    x_size = x_end_coord + 1

    img = np.full((y_size, x_size, 1), 0, np.uint8)
    img[(y_end_coord, x_end_coord)] = 255
    image_splitter = ImageSplitter()

    split_img = image_splitter.get_single_image_split(img, gear_coord, image_type_data)

    self.assertEqual(255, split_img[0,0][0])


  def test_getSingleImageSplit_usesStandardStart(self):
    image_type_data = ImageTypeData((1,1), (0,0))
    end_coord = (2,1)
    ImageSplitter.STANDARD_GROUP_DATA = ImageGroupData(end_coord[0], end_coord[1], 0, 0)

    img = np.full((end_coord[0]+1, end_coord[1]+1, 1), 0, np.uint8)
    img[end_coord] = 255
    image_splitter = ImageSplitter()

    split_img = image_splitter.get_single_image_split(img, (1,1), image_type_data)

    self.assertEqual(255, split_img[0,0][0])


  def test_getSingleImageSplit_usesBlueprint(self):
    image_type_data = ImageTypeData((1,1), (0,0))
    end_coord = (2,1)
    ImageSplitter.BLUEPRINT_GROUP_DATA = ImageGroupData(end_coord[0], end_coord[1], 0, 0)

    img = np.full((end_coord[0]+1, end_coord[1]+1, 1), 0, np.uint8)
    img[end_coord] = 255
    image_splitter = ImageSplitter()

    split_img = image_splitter.get_single_image_split(img, (1,1), image_type_data, blueprint=True)

    self.assertEqual(255, split_img[0,0][0])


  def assertAllCoordsBut(self, img, coords, expected_color):
    for row in range(img.shape[0]):
      for col in range(img.shape[1]):
        if not (row,col) in coords:
          self.assertEqual(expected_color, img[row,col])

  def setZeroStart(self):
    ImageSplitter.STANDARD_GROUP_DATA = ImageGroupData(0, 0, 0, 0)
    ImageSplitter.BLUEPRINT_GROUP_DATA = ImageGroupData(0, 0, 0, 0)
