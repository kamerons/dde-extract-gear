import numpy as np
import os
import sys

from extract_gear.index import Index
from folder.folder import Folder

class ModelEvaluator:

  def __init__(self, args, api_builtin, api_cv2, api_json, card_reader, image_splitter, page_detector):
    self.api_builtin = api_builtin
    self.api_cv2 = api_cv2
    self.card_reader = card_reader
    self.image_splitter = image_splitter
    self.api_json = api_json
    self.api_builtin.safe = True
    self.api_cv2.safe = True
    self.is_blueprint = False
    self.api_json.safe = True
    self.sub_task = args.command[1]
    self.page_detector = page_detector


  def run(self):
    if self.sub_task == "card":
      self.api_builtin.print("Beginning model evaluation task.")
      self.api_builtin.print("Model evaluation can only be run in safe mode")
      self.api_builtin.input("Press enter to confirm")
      self.evaluate_model()
    elif self.sub_task == "page":
      self.api_builtin.print("Beginning page evaluation task.")
      self.api_builtin.print("Model evaluation can only be run in safe mode")
      self.api_builtin.input("Press enter to confirm")
      self.evaluate_page()
    else:
      self.api_builtin.print("Unrecognized subtask, valid values are: [card, page]")


  def evaluate_page(self):
    failed = []
    for _ in range(2):
      self.api_builtin.print("Beginning %s files" % ("blueprint" if self.is_blueprint else "standard"))
      index_file = Folder.BLUEPRINT_PAGE_INDEX if self.is_blueprint else Folder.STANDARD_PAGE_INDEX
      data_folder = Folder.ROW_BLUEPRINT_FOLDER if self.is_blueprint else Folder.ROW_STANDARD_FOLDER
      with self.api_builtin.open(index_file, "r") as fp:
        index = self.api_json.load(fp)
      for data in index:
        img_before = self.api_cv2.imread(data_folder + data['before'])
        img_after = self.api_cv2.imread(data_folder + data['after'])
        guess = self.page_detector.get_data_for_last_page(img_before, img_after, self.is_blueprint)
        if guess[0] != data['start_row'] or guess[1] != data['end_row'] or guess[2] != data['end_col']:
          data['blueprint'] = self.is_blueprint
          failed.append((guess, data))
      self.is_blueprint = not self.is_blueprint
    self.api_builtin.print("failed for %d" %  len(failed))
    for guess, expected in failed:
      self.api_builtin.print("guessed: %s" % str(guess))
      self.api_builtin.print("expected: %s" % str(expected))


  def evaluate_model(self):
    for _ in range(2):
      self.api_builtin.print("Beginning %s files" % ("blueprint" if self.is_blueprint else "standard"))
      index = self.read_index()
      failed = self.get_failed(index)
      self.slideshow_failed(failed)
      self.is_blueprint = not self.is_blueprint


  def read_index(self):
    file_name = Folder.BLUEPRINT_CARD_FILE if self.is_blueprint else Folder.CARD_FILE
    with open(file_name, "r") as fp:
      return self.api_json.load(fp)


  def get_failed(self, index):
    failed = []
    for i in range(len(index)):
      self.detect_if_card_is_inaccurate(failed, index, i)
    return failed


  def slideshow_failed(self, failed):
    self.api_builtin.print("Showing %d failed images" % len(failed))
    for file_name, guess in failed:
      self.api_builtin.print(guess)
      self.api_builtin.print(file_name)
      folder = Folder.BLUEPRINT_FOLDER if self.is_blueprint else Folder.PREPROCESS_FOLDER
      img = self.api_cv2.imread(folder + file_name)
      gear_coord = int(file_name[1]), int(file_name[0])
      img = self.image_splitter.extract_stat_card(img, gear_coord, self.is_blueprint)
      self.api_cv2.show_img(img)


  def detect_if_card_is_inaccurate(self, failed, index, i):
    data = index[i]
    file_name = data[Index.FILE_NAME_KEY]
    gear_coord = int(file_name[1]), int(file_name[0])
    folder = Folder.BLUEPRINT_FOLDER if self.is_blueprint else Folder.PREPROCESS_FOLDER
    img = self.api_cv2.imread(folder + file_name)
    card_data = self.card_reader.get_img_data(img, gear_coord, self.is_blueprint)
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
