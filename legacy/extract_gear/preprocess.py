import numpy as np

class PreProcessor:

  PIXEL_VALUE_THRESHOLD = 3
  PIXEL_COLOR_THRESHOLD = 40

  CYAN_RED_DIFF_THRESHOLD = 30
  WHITE_VALUE_THRESHOLD = 180


  def is_red(self, pixel):
    blue, green, red = pixel
    return (red > PreProcessor.PIXEL_COLOR_THRESHOLD
      and blue < PreProcessor.PIXEL_VALUE_THRESHOLD
      and green < PreProcessor.PIXEL_VALUE_THRESHOLD)


  def is_green(self, pixel):
    blue, green, red = pixel
    return (green > PreProcessor.PIXEL_COLOR_THRESHOLD
      and blue < PreProcessor.PIXEL_VALUE_THRESHOLD
      and red < PreProcessor.PIXEL_VALUE_THRESHOLD)


  def is_black(self, pixel):
    blue, green, red = pixel
    return blue == 0 and green == 0 and red == 0


  def is_white(self, pixel):
    blue, green, red = pixel
    return blue > PreProcessor.WHITE_VALUE_THRESHOLD and blue == green and blue == red


  def is_gray(self, pixel):
    blue, green, red = pixel
    return (self.safe_difference(blue, green) < PreProcessor.PIXEL_VALUE_THRESHOLD
      and self.safe_difference(blue, red) < PreProcessor.PIXEL_VALUE_THRESHOLD
      and blue > PreProcessor.PIXEL_COLOR_THRESHOLD)


  def is_cyan(self, pixel):
    blue, green, red = pixel
    # a value of 50 actually produces better results from OOTB OCR, despite the fact that the image
    # is less clear
    return (blue > PreProcessor.WHITE_VALUE_THRESHOLD and blue == green
      and self.safe_difference(blue, red) > PreProcessor.CYAN_RED_DIFF_THRESHOLD)


  def safe_difference(self, c1, c2):
    if c1 > c2:
      return c1 - c2
    else:
      return c2 - c1
