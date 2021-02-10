class PreProcessSet:
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

  def process_set(self):
    for x in range(self.x_size):
      for y in range(self.y_size):
        pixel = self.img[y,x]
        if self.is_white(pixel):
          self.img[y,x] = [0, 0, 0]
        else:
          self.img[y,x] = [255, 255, 255]
    return self.img

  def is_white(self, pixel):
    blue, green, red = pixel
    return blue > 180 and blue == green and blue == red

  def safe_difference(self, c1, c2):
    if c1 > c2:
      return c1 - c2
    else:
      return c2 - c1
