class PreProcessLevel:
  NUM_PIXEL_THRESHOLD = 60
  PIXEL_VALUE_THRESHOLD = 3
  PIXEL_COLOR_THRESHOLD = 40

  AREA_THRESHOLD = 30

  LOW_X = 11
  LOW_Y = 31
  HIGH_X = 51
  HIGH_Y = 55

  img = None
  x_size = 0
  y_size = 0

  def __init__(self, img):
    self.img = img
    self.x_size = img.shape[1]
    self.y_size = img.shape[0]

  def run(self, img):
    pass

  def process_level(self):
    for x in range(self.x_size):
      for y in range(self.y_size):
        pixel = self.img[y,x]
        if self.is_cyan(pixel):
          self.img[y,x] = [0, 0, 0]
        else:
          self.img[y,x] = [255, 255, 255]
    return self.img

  def is_cyan(self, pixel):
    blue, green, red = pixel
    return blue > 200 and blue == green and self.safe_difference(red, blue) > 30

  def safe_difference(self, c1, c2):
    if c1 > c2:
      return c1 - c2
    else:
      return c2 - c1
