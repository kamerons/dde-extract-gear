import numpy as np
import unittest

from extract_gear.preprocess import PreProcessor

class TestPreProcess(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    TestPreProcess.ORIGINAL_PIXEL_VALUE_THRESHOLD = PreProcessor.PIXEL_VALUE_THRESHOLD
    TestPreProcess.ORIGINAL_PIXEL_COLOR_THRESHOLD = PreProcessor.PIXEL_COLOR_THRESHOLD
    TestPreProcess.ORIGINAL_CYAN_RED_THRESHOLD = PreProcessor.CYAN_RED_DIFF_THRESHOLD
    TestPreProcess.ORIGINAL_WHITE_VALUE_THRESHOLD = PreProcessor.WHITE_VALUE_THRESHOLD


  @classmethod
  def tearDownClass(cls):
    PreProcessor.PIXEL_VALUE_THRESHOLD = TestPreProcess.ORIGINAL_PIXEL_VALUE_THRESHOLD
    PreProcessor.PIXEL_COLOR_THRESHOLD = TestPreProcess.ORIGINAL_PIXEL_COLOR_THRESHOLD
    PreProcessor.CYAN_RED_DIFF_THRESHOLD = TestPreProcess.ORIGINAL_CYAN_RED_THRESHOLD
    PreProcessor.WHITE_VALUE_THRESHOLD = TestPreProcess.ORIGINAL_WHITE_VALUE_THRESHOLD


  def test_isRed(self):
    PreProcessor.PIXEL_VALUE_THRESHOLD = 1
    PreProcessor.PIXEL_COLOR_THRESHOLD = 5
    red_pixels = [[0, 0, 6], [0, 0, 255]]
    not_red_pixels = [[255, 0, 255], [0, 0, 5]]
    preprocess = PreProcessor()

    for p in red_pixels:
      self.assertTrue(preprocess.is_red(p))

    for p in not_red_pixels:
      self.assertFalse(preprocess.is_red(p))


  def test_isGreen(self):
    PreProcessor.PIXEL_VALUE_THRESHOLD = 1
    PreProcessor.PIXEL_COLOR_THRESHOLD = 5
    green_pixels = [[0, 6, 0], [0, 255, 0]]
    not_green_pixels = [[255, 0, 255], [0, 0, 5]]
    preprocess = PreProcessor()

    for p in green_pixels:
      self.assertTrue(preprocess.is_green(p))

    for p in not_green_pixels:
      self.assertFalse(preprocess.is_green(p))


  def test_isBlack(self):
    black_pixel = [0, 0, 0]
    not_black_pixel = [0, 0, 1]
    preprocess = PreProcessor()

    self.assertTrue(preprocess.is_black(black_pixel))
    self.assertFalse(preprocess.is_black(not_black_pixel))


  def test_isWhite(self):
    PreProcessor.WHITE_VALUE_THRESHOLD = 5
    white_pixels = [[6, 6, 6], [255, 255, 255]]
    not_white_pixels = [[5, 6, 7], [100, 100, 250]]
    preprocess = PreProcessor()

    for p in white_pixels:
      self.assertTrue(preprocess.is_white(p))

    for p in not_white_pixels:
      self.assertFalse(preprocess.is_white(p))


  def test_isGray(self):
    PreProcessor.PIXEL_VALUE_THRESHOLD = 2
    PreProcessor.PIXEL_COLOR_THRESHOLD = 5
    gray_pixels = [[6, 7, 6], [100, 101, 100]]
    not_gray_pixels = [[6, 12, 6], [0, 23, 23]]
    preprocess = PreProcessor()

    for p in gray_pixels:
      self.assertTrue(preprocess.is_gray(p))

    for p in not_gray_pixels:
      self.assertFalse(preprocess.is_gray(p))


  def test_isCyan(self):
    PreProcessor.WHITE_VALUE_THRESHOLD = 20
    PreProcessor.CYAN_RED_DIFF_THRESHOLD = 10
    cyan_pixels = [[30, 30, 19], [255, 255, 100]]
    not_cyan_pixels = [[19, 19, 0], [19, 18, 0], [255, 255, 255]]
    preprocess = PreProcessor()

    for p in cyan_pixels:
      self.assertTrue(preprocess.is_cyan(p))

    for p in not_cyan_pixels:
      self.assertFalse(preprocess.is_cyan(p))


  def test_safeDifference(self):
    a = np.uint8(1)
    b = np.uint8(255)
    preprocess = PreProcessor()

    self.assertEqual(np.uint8(254), preprocess.safe_difference(a, b))
    self.assertEqual(np.uint8(254), preprocess.safe_difference(b, a))
