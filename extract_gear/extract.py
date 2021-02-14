from fuzzywuzzy import fuzz
import numpy as np
import os
import sys
import pytesseract

from api.api_cv2 import ApiCv2
from extract_gear.extract_image import ExtractImage
from folder.folder import Folder

class Extract:

  def __init__(self, api_cv2=None):
    self.api_cv2 = api_cv2 if api_cv2 else ApiCv2()


  def run(self, method):
    if method == 'stat':
      self.run_extract_stat_data()
    elif method == 'level':
      self.run_extract_level_data()
    elif method == 'set':
      self.run_extract_set_data()
    else:
      # Delay expensive tensorflow import until necessary
      from extract_gear.extract_real_data import ExtractRealData

      extract_real_data = ExtractRealData()
      extract_real_data.run()


  def run_extract_stat_data(self):
    num = 0
    files = sorted(os.listdir(Folder.PREPROCESS_FOLDER))
    extract_image = ExtractImage()
    for file_name in files:
      img = self.api_cv2.imread(Folder.PREPROCESS_FOLDER + file_name)
      print("Processing " + file_name)
      y = int(file_name[1])
      x = int(file_name[0])
      images = extract_image.extract_stat_images(img, y, x)
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
    extract_image = ExtractImage()
    for file_name in files:
      img = self.api_cv2.imread(Folder.PREPROCESS_FOLDER + file_name)
      print("Processing " + file_name)
      y = int(file_name[1])
      x = int(file_name[0])
      images = extract_image.extract_level_images(img, y, x)
      img = images[0]
      self.api_cv2.show_img(img)
      see_all = input("Save another image?  Enter any character to see the slideshow")

      if see_all != "":
        border_size = 3

        img_total = np.full((ExtractImage.LEVEL_HEIGHT*5 + 5 * border_size, ExtractImage.LEVEL_WIDTH, 3),
          (255, 255, 255), dtype=np.uint8)
        for y in range(ExtractImage.LEVEL_HEIGHT):
          for x in range(ExtractImage.LEVEL_WIDTH):
            i = 0
            for img in images:
              img_total[border_size * i + y + i * ExtractImage.LEVEL_HEIGHT,x] = img[y, x]
              i += 1

        self.api_cv2.show_img(img)
        index_to_save = int(input('Which image should be saved? (Zero-based)'))
        img = images[index_to_save]

      self.api_cv2.imwrite("%s%03d.png" % (Folder.LEVEL_CROP_FOLDER, num), img)
      num += 1


  def run_extract_set_data(self):
    num = 0
    files = sorted(os.listdir(Folder.PREPROCESS_FOLDER))
    extract_image = ExtractImage()
    for file_name in files:
      img = self.api_cv2.imread(Folder.PREPROCESS_FOLDER + file_name)
      print("Processing %d of %d"  % (num + 1, len(files)))
      y = int(file_name[1])
      x = int(file_name[0])
      img = extract_image.extract_set_image(img, y, x)
      self.api_cv2.imshow('img', img)
      self.api_cv2.waitKey(0)
      self.api_cv2.destroyAllWindows()
      self.api_cv2.imwrite('%s%03d.png' % (Folder.SET_CROP_FOLDER, num), img)
      num += 1
