class ImageGroupData:

  def __init__(self, start_y, start_x, y_gear_offset, x_gear_offset):
    self.start_y = start_y
    self.start_x = start_x
    self.y_gear_offset = y_gear_offset
    self.x_gear_offset = x_gear_offset


class ImageTypeData:

  def __init__(self, size, rel_start_offset, rows=None, columns=None, pass_fn=None, next_offset=None):
    self.size = size
    self.rel_start_offset = rel_start_offset
    self.rows = rows
    self.columns = columns
    self.pass_fn = pass_fn
    self.next_offset = next_offset


class ImageSplitter:

  STANDARD_GROUP_DATA = ImageGroupData(375, 390, 177, 174)
  BLUEPRINT_GROUP_DATA = ImageGroupData(293, 423, 129, 126)

  CARD_DATA = ImageTypeData((430,350), (-112,-10))
  SET_DATA = ImageTypeData((20,140), (-100,100))
  STAT_DATA = ImageTypeData((56,56), (0,0), 3, 6, lambda col, row: col >= 4 and row != 1, (87,60))
  LEVEL_DATA = ImageTypeData((30,70), (268,180), 2, 3, lambda col, row: row == 0 and col == 2, (-88,60))

  STADARD_PAGE_DATA = ImageTypeData((160,160), (41,-157), 3, 5, lambda _, __: False, (177, 174))
  BLUEPRINT_PAGE_DATA = ImageTypeData((90, 90), (74, -100), 6, 4, lambda _, __: False, (129, 126))


  def extract_stat_card(self, img, gear_coord, is_blueprint=False):
    group_data = self.get_group_data(is_blueprint)
    return self.get_single_image_split(img, gear_coord, ImageSplitter.CARD_DATA, group_data)


  def extract_set_image(self, img, gear_coord, is_blueprint=False):
    group_data = self.get_group_data(is_blueprint)
    return self.get_single_image_split(img, gear_coord, ImageSplitter.SET_DATA, group_data)


  def extract_stat_images(self, img, gear_coord, is_blueprint=False):
    group_data = self.get_group_data(is_blueprint)
    return self.get_group_image_split(img, gear_coord, ImageSplitter.STAT_DATA, group_data)


  def extract_level_images(self, img, gear_coord, is_blueprint=False):
    group_data = self.get_group_data(is_blueprint)
    return self.get_group_image_split(img, gear_coord, ImageSplitter.LEVEL_DATA, group_data)


  def extract_page_images(self, img, is_blueprint=False):
    group_data = self.get_group_data(is_blueprint)
    page_data = ImageSplitter.BLUEPRINT_PAGE_DATA if is_blueprint else ImageSplitter.STADARD_PAGE_DATA
    return self.get_group_image_split(img, (1,1), page_data, group_data)


  def get_single_image_split(self, img, gear_coord, image_type_data, group_data):
    start_coord = self.get_start_coord(gear_coord, image_type_data.rel_start_offset, group_data)
    return self.get_image_from_start(img, start_coord, image_type_data.size)


  def get_group_image_split(self, img, gear_coord, image_type_data, group_data):
    images = []
    abs_start_coord = self.get_start_coord(gear_coord, image_type_data.rel_start_offset, group_data)
    for row in range(image_type_data.rows):
      for col in range(image_type_data.columns):
        if image_type_data.pass_fn(col, row):
          continue
        start_y = abs_start_coord[0] + (image_type_data.next_offset[0] * row)
        start_x = abs_start_coord[1] + (image_type_data.next_offset[1] * col)
        single_img = self.get_image_from_start(img, (start_y, start_x), image_type_data.size)
        images.append(single_img)
    return images


  def get_start_coord(self, gear_coord, rel_start_offset, group_data):
    y_gear_pos, x_gear_pos = gear_coord
    y_rel_offset, x_rel_offset = rel_start_offset
    y_point = group_data.start_y + (y_gear_pos-1) * group_data.y_gear_offset + y_rel_offset
    x_point = group_data.start_x + (x_gear_pos-1) * group_data.x_gear_offset + x_rel_offset
    return (y_point, x_point)


  def get_image_from_start(self, img, abs_start_coord, size):
    low_y, low_x = abs_start_coord
    height, width = size
    high_y = low_y + height
    high_x = low_x + width
    return img[low_y:high_y, low_x:high_x]


  def get_group_data(self, is_blueprint):
    return ImageSplitter.BLUEPRINT_GROUP_DATA if is_blueprint else ImageSplitter.STANDARD_GROUP_DATA
