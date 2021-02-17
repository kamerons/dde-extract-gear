import json
import numpy as np
import os
import sys

from extract_gear.index import Index
from folder.folder import Folder

class ModelEvaluator:

  def __init__(self, args, api_builtin, api_cv2, api_pytesseract, preprocess_factory):
    self.api_builtin = api_builtin
    self.api_cv2 = api_cv2
    self.sub_task = args.command[1]
    self.api_pytesseract = api_pytesseract
    self.preprocess_factory = preprocess_factory


  def run(self):
    self.api_pytesseract.initialize_pytesseract()
    if self.sub_task == 'stat':
      self.run_confirm_stat()
    elif self.sub_task == 'level':
      self.run_confirm_level()
    elif self.sub_task == 'set':
      self.run_confirm_set()
    elif self.sub_task == 'none':
      self.run_preprocess_none()
    else:
      self.api_builtin.print("Falied to recognize subtask")
      self.api_builtin.exit()


  def run_preprocess_none(self):
    index = []
    with self.api_builtin.open(Folder.STAT_SAVE_FOLDER + "correction-complete09-02-2021_02-57-04-index.json", "r") as fp:
      index = json.load(fp)

    for data in index:
      if data[Index.STAT_TYPE_KEY] != Index.NONE:
        continue
      img = self.api_cv2.imread(Folder.STAT_CROP_FOLDER + data[Index.FILE_NAME_KEY])
      preprocessor = self.preprocess_factory.get_stat_preprocessor(np.array(img, copy=True))
      img2 = preprocessor.process_stat()
      img3 = np.full((56,56*2, 3), (0, 0, 0), dtype=np.uint8)

      self.api_builtin.print(len(preprocessor.digits))
      for y in range(56):
        for x in range(56):
          img3[y,x] = img[y,x]
          img3[y,x+56] = img2[y,x]
      self.api_cv2.show_img(img3)


  def run_confirm_stat(self):
    index = []
    with self.api_builtin.open(Folder.STAT_SAVE_FOLDER + "correction-complete09-02-2021_02-57-04-index.json", "r") as fp:
      index = json.load(fp)

    failed = []
    total = self.calculate_success_rate(index, failed)

    num_success = total - len(failed)
    self.api_builtin.print("Accuracy: %d/%d or %f" % (num_success, total, float(num_success) / total))
    self.api_builtin.print("showing failed images")
    self.slideshow_failed(failed)


  def run_confirm_level(self):
    for file_name in os.listdir(Folder.LEVEL_CROP_FOLDER):
      img = self.api_cv2.imread(Folder.LEVEL_CROP_FOLDER + file_name)
      preprocessor = self.preprocess_factory.get_level_preprocessor(img)
      img = preprocessor.process_level()
      guess = self.api_pytesseract.image_to_string(img).strip()
      self.api_builtin.print("The guess for this file was: %s" % guess)
      self.api_cv2.show_img(img)


  def run_confirm_set(self):
    for file_name in os.listdir(Folder.SET_CROP_FOLDER):
      img = self.api_cv2.imread(Folder.SET_CROP_FOLDER + file_name)
      preprocessor = self.preprocess_factory.get_set_preprocessor(img)
      img = preprocessor.process_set()
      guess = self.api_pytesseract.image_to_string(img).strip()
      self.api_builtin.print("The guess for this file was: %s" % guess)


  def calculate_success_rate(self, index, failed):
    total = 0
    for data in index:
      if data[Index.STAT_TYPE_KEY] == Index.NONE:
        continue
      img = self.api_cv2.imread(Folder.STAT_CROP_FOLDER + data[Index.FILE_NAME_KEY])
      preprocessor = self.preprocess_factory.get_stat_preprocessor(img)
      img = preprocessor.process_stat()
      guess = self.api_pytesseract.image_to_string(img).strip()
      guess = "".join(e for e in guess if e.isalnum())
      if guess != str(data[Index.STAT_VALUE_KEY]):
        fail_data = data.copy()
        fail_data['guess'] = guess
        failed.append(fail_data)
      total += 1
      if total % 100 == 0:
        self.api_builtin.print("Complete %d of at most %d" % (total, len(index)))
    return total


  def slideshow_failed(self, failed):
    for failure in failed:
      img = self.api_cv2.imread(Folder.STAT_CROP_FOLDER + failure[Index.FILE_NAME_KEY])
      preprocessor = self.preprocess_factory.get_stat_preprocessor(np.array(img, copy=True))
      img2 = preprocessor.process_stat()
      img3 = np.full((56,56*2, 3), (0, 0, 0), dtype=np.uint8)

      for y in range(56):
        for x in range(56):
          img3[y,x] = img[y,x]
          img3[y,x+56] = img2[y,x]
      self.api_builtin.print("Guess was %s, actual was %s for %s" % (failure['guess'], failure[Index.STAT_VALUE_KEY], failure[Index.FILE_NAME_KEY]))
      self.api_cv2.show_img(img3)
