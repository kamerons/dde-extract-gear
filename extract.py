from fuzzywuzzy import fuzz
import numpy as np
import os
import sys
import pytesseract

from api.api_cv2 import ApiCv2
from extract_image import ExtractImage
from extract_real_data import ExtractRealData

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
      self.run_get_least_confident_armor_type()


  def run_extract_stat_data(self):
    num = 0
    files = sorted(os.listdir('data/preprocess/'))
    extract_image = ExtractImage()
    for file_name in files:
      img = self.api_cv2.imread('data/preprocess/' + file_name)
      print("Processing " + file_name)
      y = int(file_name[1])
      x = int(file_name[0])
      images = extract_image.extract_stat_images(img, y, x)
      i = 0
      for img in images:
        self.api_cv2.imshow('img', img)
        self.api_cv2.waitKey(0)
        self.api_cv2.destroyAllWindows()
        if i in range(4):
          name = "defense_%03d_%d.png" % (num, i)
        elif i in range(4, 10):
          name = "row1_%03d_%d.png" % (num, i - 4)
        else:
          name = "row2_%03d_%d.png" % (num, i - 10)
        self.api_cv2.imwrite('data/stat/process/%s' % name, img)
        num += 1
        i += 1


  def run_extract_level_data(self):
    num = 0
    files = sorted(os.listdir('data/preprocess/'))
    extract_image = ExtractImage()
    for file_name in files:
      img = self.api_cv2.imread('data/preprocess/' + file_name)
      print("Processing " + file_name)
      y = int(file_name[1])
      x = int(file_name[0])
      images = extract_image.extract_level_images(img, y, x)
      img = images[0]
      self.api_cv2.imshow('img', img)
      self.api_cv2.waitKey(0)
      self.api_cv2.destroyAllWindows()
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

        self.api_cv2.imshow('img', img_total)
        self.api_cv2.waitKey(0)
        self.api_cv2.destroyAllWindows()
        index_to_save = int(input('Which image should be saved? (Zero-based)'))
        img = images[index_to_save]

      self.api_cv2.imwrite("data/level/process/%03d.png" % num, img)
      num += 1


  def run_extract_set_data(self):
    num = 0
    files = sorted(os.listdir('data/preprocess/'))
    extract_image = ExtractImage()
    for file_name in files:
      img = self.api_cv2.imread('data/preprocess/' + file_name)
      print("Processing %d of %d"  % (num + 1, len(files)))
      y = int(file_name[1])
      x = int(file_name[0])
      img = extract_image.extract_set_image(img, y, x)
      self.api_cv2.imshow('img', img)
      self.api_cv2.waitKey(0)
      self.api_cv2.destroyAllWindows()
      self.api_cv2.imwrite('data/set/process/%03d.png' % num, img)
      num += 1


  def run_get_least_confident_armor_type(self):
    files = sorted(os.listdir('data/preprocess'))
    smallest_diff = 100
    smallest_diff_file_name = ""
    extract_real_data = ExtractRealData()
    for file_name in files:
      img = self.api_cv2.imread('data/preprocess/' + file_name)
      guess = extract_real_data.get_armor_type_guess(img, int(file_name[1]), int(file_name[0]))
      highest = 0
      second_highest = -1
      for armor_type in ExtractRealData.ARMOR_TYPES:
        ratio = fuzz.ratio(armor_type.lower(), guess.lower())
        if ratio > highest:
          second_highest = highest
          highest = ratio
        elif ratio > second_highest:
          second_highest = ratio
      confidence = highest - second_highest
      if confidence < smallest_diff:
        smallest_diff = confidence
        smallest_diff_file_name = file_name
      for armor_type in ExtractRealData.ARMOR_TYPES:
        ratio = fuzz.ratio(armor_type.lower(), guess.lower())

    img = self.api_cv2.imread('data/preprocess/' + smallest_diff_file_name)
    guess = extract_real_data.get_armor_type_guess(img, int(smallest_diff_file_name[1]), int(smallest_diff_file_name[0]))
    print("The guess was %s" % guess)
    highest = 0
    second_highest = -1
    for armor_type in ExtractRealData.ARMOR_TYPES:
      ratio = fuzz.ratio(armor_type.lower(), guess.lower())
      if ratio > highest:
        second_highest = highest
        highest = ratio
      elif ratio > second_highest:
        second_highest = ratio
    print("the confidence was %d" % (highest - second_highest))
