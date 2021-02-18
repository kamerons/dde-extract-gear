import os
import numpy as np

from folder.folder import Folder

class CardReader:

  def __init__(self, api_builtin, api_cv2, image_splitter, stat_group_reader, set_type_reader):
    self.api_builtin = api_builtin
    self.api_cv2 = api_cv2
    self.image_splitter = image_splitter
    self.stat_group_reader = stat_group_reader
    self.set_type_reader = set_type_reader


  def run(self):
    files = sorted(os.listdir(Folder.PREPROCESS_FOLDER))
    for file_name in files:
      coord = int(file_name[1]), int(file_name[0])
      img = self.api_cv2.imread(Folder.PREPROCESS_FOLDER + file_name)
      card = self.image_splitter.extract_stat_card(img, coord)
      copy = np.full(card.shape, (0,0,0), dtype=np.uint8)
      for y in range(card.shape[0]):
        for x in range(copy.shape[1]):
          copy[y,x] = card[y,x]
      self.api_builtin.print(self.get_img_data(img, coord))
      self.api_cv2.show_img(copy)


  def get_img_data(self, img, coord):
    set_type_image = self.image_splitter.extract_set_image(img, coord)
    armor_type = self.set_type_reader.get_armor_type(set_type_image)
    stat_images = self.image_splitter.extract_stat_images(img, coord)
    stats = self.stat_group_reader.get_stat_types_and_values(stat_images)
    max_level = 16
    current_level = 1
    data = {'armor_set': armor_type, 'current_level': current_level, 'max_level': max_level}
    for stat_key in stats:
      data[stat_key] = int(stats[stat_key])
    return data
