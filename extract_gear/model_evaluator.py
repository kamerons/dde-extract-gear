import json
import numpy as np
import os
import sys

from extract_gear.index import Index
from folder.folder import Folder

class ModelEvaluator:

  def __init__(self, api_builtin, api_cv2, card_reader, image_splitter):
    self.api_builtin = api_builtin
    self.api_cv2 = api_cv2
    self.card_reader = card_reader
    self.image_splitter = image_splitter


  def run(self):
    index = self.read_index()
    failed = self.get_failed(index)
    self.slideshow_failed(failed)


  def read_index(self):
    with open(Folder.CARD_FILE, "r") as fp:
      return json.load(fp)


  def get_failed(self, index):
    failed = []
    for i in range(len(index)):
      self.detect_if_card_is_inaccurate(failed, index, i)
    return failed


  def slideshow_failed(self, failed):
    self.api_builtin.print("Showing %d failed images" % len(failed))
    for file_name, guess in failed:
      self.api_builtin.print(guess)
      img = self.api_cv2.imread(Folder.PREPROCESS_FOLDER + file_name)
      gear_coord = int(file_name[1]), int(file_name[0])
      img = self.image_splitter.extract_stat_card(img, gear_coord)
      self.api_cv2.show_img(img)


  def detect_if_card_is_inaccurate(self, failed, index, i):
    data = index[i]
    file_name = data[Index.FILE_NAME_KEY]
    gear_coord = int(file_name[1]), int(file_name[0])
    img = self.api_cv2.imread(Folder.PREPROCESS_FOLDER + file_name)
    card_data = self.card_reader.get_img_data(img, gear_coord)
    if not self.is_accurate(card_data, data):
      failed.append([file_name, card_data])
    if (i+1) % 10 == 0:
      self.api_builtin.print("Complete %d of %d" %(i+1, len(index)))


  def is_accurate(self, card_data, verified_data):
    self.trim_data(card_data, verified_data)
    return card_data == verified_data


  def trim_data(self, card_data, verified_data):
    verified_data[Index.FILE_NAME_KEY] = ""
    card_data[Index.FILE_NAME_KEY] = ""
    verified_data["current_level"] = ""
    card_data["current_level"] = ""
    verified_data["max_level"] = ""
    card_data["max_level"] = ""
