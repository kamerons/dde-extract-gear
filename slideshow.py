import json
import numpy as np
import os
import pytesseract
import sys

from api.api_cv2 import ApiCv2
from preprocess_stat import PreProcessStat
from preprocess_level import PreProcessLevel
from preprocess_set import PreProcessSet

class SlideShow:

  def __init__(self, api_cv2=None):
    self.api_cv2 = api_cv2 if api_cv2 else ApiCv2()


  def run(self, method):
    if method == 'stat':
      self.run_confirm_stat()
    elif method == 'level':
      self.run_confirm_level()
    else:
      self.run_confirm_set()


  def run_confirm_stat(self):
    index = []
    with open("data/stat/save/correction-complete09-02-2021_02-57-04-index.json") as fp:
      index = json.load(fp)

    failed = []
    total = self.calculate_success_rate(index, failed)

    num_success = total - len(failed)
    print("Accuracy: %d/%d or %f" % (num_success, total, float(num_success) / total))
    print("showing failed images")
    self.slideshow_failed(failed)


  def run_confirm_level(self):
    for file_name in os.listdir('data/level/process/'):
      img = self.api_cv2.imread('data/level/process/' + file_name)
      preprocessor = PreProcessLevel(img)
      img = preprocessor.process_level()
      guess = pytesseract.image_to_string(img).strip()
      print("The guess for this file was: %s" % guess)
      self.api_cv2.imshow('img', img)
      self.api_cv2.waitKey(0)
      self.api_cv2.destroyAllWindows()


  def run_confirm_set(self):
    for file_name in os.listdir('data/set/process/'):
      img = self.api_cv2.imread('data/set/process/' + file_name)
      preprocessor = PreProcessSet(img)
      img = preprocessor.process_set()
      guess = pytesseract.image_to_string(img).strip()
      print("The guess for this file was: %s" % guess)


  def calculate_success_rate(self, index, failed):
    total = 0
    for data in index:
      if data['type'] == "none":
        continue
      img = self.api_cv2.imread('data/stat/process/' + data['file_name'])
      preprocessor = PreProcessStat(img)
      img = preprocessor.process_stat()
      guess = pytesseract.image_to_string(img).strip()
      guess = "".join(e for e in guess if e.isalnum())
      if guess != str(data['num']):
        fail_data = data.copy()
        fail_data['guess'] = guess
        failed.append(fail_data)
      total += 1
      if total % 100 == 0:
        print("Complete %d of at most %d" % (total, len(index)))
    return total


  def slideshow_failed(self, failed):
    for failure in failed:
      img = self.api_cv2.imread('data/stat/process/' + failure['file_name'])
      preprocessor = PreProcessStat(np.array(img, copy=True))
      img2 = preprocessor.process_stat()
      img3 = np.full((56,56*2, 3), (0, 0, 0), dtype=np.uint8)

      for y in range(56):
        for x in range(56):
          img3[y,x] = img[y,x]
          img3[y,x+56] = img2[y,x]
      print("Guess was %s, actual was %s for %s" % (failure['guess'], failure['num'], failure['file_name']))
      self.api_cv2.imshow('img', img3)
      self.api_cv2.waitKey(0)
      self.api_cv2.destroyAllWindows()
