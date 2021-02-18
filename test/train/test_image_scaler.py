import numpy as np
import unittest

from extract_gear.image_splitter import ImageSplitter
from extract_gear.image_type_data import ImageTypeData
from test.util.test_util import TestUtil
from train.image_scaler import ImageScaler

class TestImageScaler(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    TestImageScaler.IMAGESPLITTER_ATTRIBUTES = TestUtil.get_class_attributes(ImageSplitter)


  @classmethod
  def tearDownClass(cls):
    TestUtil.restore_class_attributes(ImageSplitter, TestImageScaler.IMAGESPLITTER_ATTRIBUTES)


  def test_prepareForClassification_list(self):
    ImageSplitter.STAT_DATA = ImageTypeData((2, 2), (0,0))
    img1 = np.full((4,4,1), 0, dtype=np.uint8)
    img2 = np.full((4,4,1), 255, dtype=np.uint8)
    data = [[img1, 1], [img2, 2]]

    image_scaler = ImageScaler()

    scaled_x, y = image_scaler.prepare_for_classification(data)

    self.assert_np_matrix_equal([0.0], scaled_x[0], (2,2))
    self.assert_np_matrix_equal([1.0], scaled_x[1], (2,2))
    self.assertEqual(1, y[0])
    self.assertEqual(2, y[1])


  def test_prepareForClassification_nonList(self):
    ImageSplitter.STAT_DATA = ImageTypeData((2, 2), (0,0))
    img1 = np.full((4,4,1), 0, dtype=np.uint8)
    img2 = np.full((4,4,1), 255, dtype=np.uint8)
    data = [img1, img2]

    image_scaler = ImageScaler()

    scaled_x, _ = image_scaler.prepare_for_classification(data)

    self.assert_np_matrix_equal([0.0], scaled_x[0], (2,2))
    self.assert_np_matrix_equal([1.0], scaled_x[1], (2,2))


  def assert_np_matrix_equal(self, expected_value, np_arr, size):
    for y in range(size[0]):
      for x in range(size[1]):
        self.assertEqual(expected_value, np_arr[y,x])
