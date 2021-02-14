from extract_gear.image_type_data import ImageTypeData

class ImageSplitter:

  X_START = 390
  Y_START = 375

  X_GEAR_OFFSET = 174
  Y_GEAR_OFFSET = 177

  CARD_DATA = ImageTypeData((430,350), (-112,-10))
  SET_DATA = ImageTypeData((20,140), (-100,100))
  STAT_DATA = ImageTypeData((56,56), (0,0), 3, 6, lambda col, row: col >= 4 and row != 1, (87,60))
  LEVEL_DATA = ImageTypeData((30,70), (268,180), 2, 3, lambda col, row: row == 0 and col == 2, (-88,60))

  def extract_stat_card(self, img, gear_coord):
    return self.get_single_image_split(img, gear_coord, ImageSplitter.CARD_DATA)


  def extract_set_image(self, img, gear_coord):
    return self.get_single_image_split(img, gear_coord, ImageSplitter.SET_DATA)


  def extract_stat_images(self, img, gear_coord):
    return self.get_group_image_split(img, gear_coord, ImageSplitter.STAT_DATA)


  def extract_level_images(self, img, gear_coord):
    return self.get_group_image_split(img, gear_coord, ImageSplitter.LEVEL_DATA)


  def get_single_image_split(self, img, gear_coord, image_type_data):
    start_coord = self.get_start_coord(gear_coord, image_type_data.rel_start_offset)
    return self.get_image_from_start(img, start_coord, image_type_data.size)


  def get_group_image_split(self, img, gear_coord, image_type_data):
    images = []
    abs_start_coord = self.get_start_coord(gear_coord, image_type_data.rel_start_offset)
    for row in range(image_type_data.rows):
      for col in range(image_type_data.columns):
        if image_type_data.pass_fn(col, row):
          continue
        start_y = abs_start_coord[0] + (image_type_data.next_offset[0] * row)
        start_x = abs_start_coord[1] + (image_type_data.next_offset[1] * col)
        single_img = self.get_image_from_start(img, (start_y, start_x), image_type_data.size)
        images.append(single_img)
    return images


  def get_start_coord(self, gear_coord, rel_start_offset):
    y_gear_offset, x_gear_offset = gear_coord
    y_offset, x_offset = rel_start_offset
    y_point = ImageSplitter.Y_START + (y_gear_offset-1) * ImageSplitter.Y_GEAR_OFFSET + y_offset
    x_point = ImageSplitter.X_START + (x_gear_offset-1) * ImageSplitter.X_GEAR_OFFSET + x_offset
    return (y_point, x_point)


  def get_image_from_start(self, img, abs_start_coord, size):
    low_y, low_x = abs_start_coord
    height, width = size
    high_y = low_y + height
    high_x = low_x + width
    return img[low_y:high_y, low_x:high_x]
