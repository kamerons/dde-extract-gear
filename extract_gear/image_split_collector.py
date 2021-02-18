from fuzzywuzzy import fuzz
import numpy as np
import os
import sys

from extract_gear.image_splitter import ImageSplitter
from folder.folder import Folder

class ImageSplitCollector:

  def __init__(self, args, api_builtin, api_cv2, image_splitter):
    self.api_builtin = api_builtin
    self.api_cv2 = api_cv2
    self.sub_task = args.command[1]
    self.image_splitter = image_splitter


  def run(self):
    if self.sub_task == 'stat':
      self.run_extract_stat_data()
    elif self.sub_task == 'level':
      self.run_extract_level_data()
    elif self.sub_task == 'set':
      self.run_extract_set_data()
    elif self.sub_task == 'card':
      self.run_extract_card_data()
    else:
      self.api_builtin.print("Failed to recognize sub-task")
      self.api_builtin.exit()


  def run_extract_stat_data(self):
    num = 0
    files = sorted(os.listdir(Folder.PREPROCESS_FOLDER))
    for file_name in files:
      img = self.api_cv2.imread(Folder.PREPROCESS_FOLDER + file_name)
      print("Processing " + file_name)
      gear_coord = int(file_name[1]), int(file_name[0])
      images = self.image_splitter.extract_stat_images(img, gear_coord)
      i = 0
      for img in images:
        self.api_cv2.show_img(img)
        if i in range(4):
          name = "defense_%03d_%d.png" % (num, i)
        elif i in range(4, 10):
          name = "row1_%03d_%d.png" % (num, i - 4)
        else:
          name = "row2_%03d_%d.png" % (num, i - 10)
        self.api_cv2.imwrite('%s%s' % (Folder.STAT_CROP_FOLDER, name), img)
        num += 1
        i += 1


  def run_extract_level_data(self):
    num = 0
    files = sorted(os.listdir(Folder.PREPROCESS_FOLDER))
    for file_name in files:
      img = self.api_cv2.imread(Folder.PREPROCESS_FOLDER + file_name)
      print("Processing " + file_name)
      gear_coord = int(file_name[1]), int(file_name[0])
      images = self.image_splitter.extract_level_images(img, gear_coord)
      img = images[0]
      self.api_cv2.show_img(img)
      see_all = input("Save another image?  Enter any character to see the slideshow")

      if see_all != "":
        border_size = 3
        level_size = ImageSplitter.LEVEL_DATA.size
        img_total = np.full((level_size[0]*5 + 5*border_size, level_size[1], 3),
          (255, 255, 255), dtype=np.uint8)
        for y in range(level_size[0]):
          for x in range(level_size[1]):
            i = 0
            for img in images:
              img_total[border_size*i + y + i*level_size[0], x] = img[y, x]
              i += 1

        self.api_cv2.show_img(img_total)
        index_to_save = int(input('Which image should be saved? (Zero-based)'))
        img = images[index_to_save]

      self.api_cv2.imwrite("%s%03d.png" % (Folder.LEVEL_CROP_FOLDER, num), img)
      num += 1


  def run_extract_set_data(self):
    num = 0
    files = sorted(os.listdir(Folder.PREPROCESS_FOLDER))
    for file_name in files:
      img = self.api_cv2.imread(Folder.PREPROCESS_FOLDER + file_name)
      print("Processing %d of %d"  % (num + 1, len(files)))
      gear_coord = int(file_name[1]), int(file_name[0])
      img = self.image_splitter.extract_set_image(img, gear_coord)
      self.api_cv2.show_img(img)
      self.api_cv2.imwrite('%s%03d.png' % (Folder.SET_CROP_FOLDER, num), img)
      num += 1


  def run_extract_card_data(self):
    num = 0
    files = sorted(os.listdir(Folder.PREPROCESS_FOLDER))
    for file_name in files:
      img = self.api_cv2.imread(Folder.PREPROCESS_FOLDER + file_name)
      print("Processing %d of %d"  % (num + 1, len(files)))
      gear_coord = int(file_name[1]), int(file_name[0])
      img = self.image_splitter.extract_stat_card(img, gear_coord)
      print(str(img.shape))
      self.api_cv2.show_img(img)
      self.api_cv2.imwrite('%s%03d.png' % (Folder.SET_CROP_FOLDER, num), img)
      num += 1
