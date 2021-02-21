import os

import numpy as np

from extract_gear.index import Index
from extract_gear.image_splitter import ImageSplitter
from folder.folder import Folder
from train.train_stat_base import TrainStatBase

class TrainStatType(TrainStatBase):

  NUM_EPOCHS = 1000


  def __init__(self, args, api_builtin, api_cv2, api_json, api_random, api_tensorflow, image_scaler):
    super().__init__(args, api_builtin, api_cv2, api_json, api_tensorflow, image_scaler,
    TrainStatType.NUM_EPOCHS, Index.STAT_OPTIONS, Folder.STAT_TYPE_MODEL_FOLDER, 2000, .67)
    self.api_random = api_random
    self.ratio = .7


  def split_index(self):
    with self.api_builtin.open(Folder.ICON_INDEX_FILE, "r") as fp:
      index = self.api_json.load(fp)
    self.api_random.shuffle(index)
    minimum = self.get_limiting_stat_type(index)
    return self.get_train_and_test_data(index, minimum)


  def get_limiting_stat_type(self, index):
    max_seen_of_each_stat_type = {}
    for stat_type in Index.STAT_OPTIONS:
      max_seen_of_each_stat_type[stat_type] = 0

    for data in index:
      max_seen_of_each_stat_type[data[Index.STAT_TYPE_KEY]] += 1

    minimum = len(index)
    for stat_type in Index.STAT_OPTIONS:
      if max_seen_of_each_stat_type[stat_type] < minimum:
        minimum = max_seen_of_each_stat_type[stat_type]
    return minimum


  def get_train_and_test_data(self, index, minimum):
    train = []
    test = []

    seen_of_each_stat_type = {}
    for stat_type in Index.STAT_OPTIONS:
      seen_of_each_stat_type[stat_type] = 0

    for data in index:
      stat_type = data[Index.STAT_TYPE_KEY]
      image_and_stat_type = self.read_img(data, stat_type)
      seen_of_each_stat_type[stat_type] += 1
      if seen_of_each_stat_type[stat_type] <= self.ratio * minimum:
        train.append(image_and_stat_type)
      elif seen_of_each_stat_type[stat_type] <= minimum:
        test.append(image_and_stat_type)
    return train, test


  def read_img(self, data, stat_type):
    file_name = Folder.ICON_CROP_FOLDER + data[Index.FILE_NAME_KEY]
    img = self.api_cv2.imread(file_name)
    stat_index = Index.STAT_OPTIONS.index(stat_type)
    return [img, stat_index]
