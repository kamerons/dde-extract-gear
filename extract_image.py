class ExtractImage:

  X_STAT_OFFSET = 60
  Y_STAT_OFFSET = 87

  X_GEAR_OFFSET = 174
  Y_GEAR_OFFSET = 177

  X_LEVEL_OFFSET = 180
  Y_LEVEL_OFFSET = 268

  X_SET_OFFSET = 100
  Y_SET_OFFSET = -100

  LEVEL_WIDTH = 70
  LEVEL_HEIGHT = 30

  SET_WIDTH = 140
  SET_HEIGHT = 20

  LEVEL_ONE_STAT_ROW_OFFSET = 88

  X_START = 390
  Y_START = 375

  STAT_SIZE = 56


  def __init__(self):
    pass


  def extract_stat_images(self, img, y, x):
    images = []
    x_coord = ExtractImage.X_START + (x-1) * ExtractImage.X_GEAR_OFFSET
    y_coord = ExtractImage.Y_START + (y-1) * ExtractImage.Y_GEAR_OFFSET

    for y_offset in range(3):
      for x_offset in range(6):
        if x_offset >= 4 and y_offset != 1:
          continue
        low_y = y_coord + y_offset * ExtractImage.Y_STAT_OFFSET
        low_x = x_coord + x_offset * ExtractImage.X_STAT_OFFSET
        high_y = low_y + ExtractImage.STAT_SIZE
        high_x = low_x + ExtractImage.STAT_SIZE
        images.append(img[low_y:high_y, low_x:high_x])

    return images


  def extract_level_images(self, img, y, x):
    images = []
    y_coord, x_coord = self.get_start_coord(y, x, ExtractImage.Y_LEVEL_OFFSET, ExtractImage.X_LEVEL_OFFSET)

    for y_offset in range(2):
      for x_offset in range(3):
        if y_offset == 0 and x_offset == 2:
          continue
        low_y = y_coord - y_offset * ExtractImage.LEVEL_ONE_STAT_ROW_OFFSET
        low_x = x_coord + x_offset * ExtractImage.STAT_SIZE
        high_y = low_y + ExtractImage.LEVEL_HEIGHT
        high_x = low_x + ExtractImage.LEVEL_WIDTH
        images.append(img[low_y:high_y, low_x:high_x])
    return images


  def extract_set_image(self, img, y, x):
    low_y, low_x = self.get_start_coord(y, x, ExtractImage.Y_SET_OFFSET, ExtractImage.X_SET_OFFSET)
    high_y = low_y + ExtractImage.SET_HEIGHT
    high_x = low_x + ExtractImage.SET_WIDTH

    return img[low_y:high_y, low_x:high_x]


  def get_start_coord(self, y, x, y_offset, x_offset):
    y_coord = ExtractImage.Y_START + (y-1) * ExtractImage.Y_GEAR_OFFSET + y_offset
    x_coord = ExtractImage.X_START + (x-1) * ExtractImage.X_GEAR_OFFSET + x_offset
    return (y_coord, x_coord)
