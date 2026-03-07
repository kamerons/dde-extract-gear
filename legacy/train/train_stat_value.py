import os
import numpy as np
import sys

from extract_gear.create_index_task import CreateIndexTask
from extract_gear.index import Index
from extract_gear.image_splitter import ImageSplitter
from extract_gear.preprocess_stat import PreProcessStat
from folder.folder import Folder
from train.train_stat_base import TrainStatBase

class TrainStatValue(TrainStatBase):

  NUM_EPOCHS = 1000


  def __init__(self, args, api_builtin, api_cv2, api_json, api_random, api_tensorflow, image_scaler):
    class_names = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "blob"]
    super().__init__(args, api_builtin, api_cv2, api_json, api_tensorflow, image_scaler,
    TrainStatValue.NUM_EPOCHS, class_names, Folder.STAT_VALUE_MODEL_FOLDER, 2000, .67)
    self.api_random = api_random
    self.ratio = .7


  def split_index(self):
    with self.api_builtin.open(Folder.DIGIT_INDEX_FILE, "r") as fp:
      index = self.api_json.load(fp)
    self.api_random.shuffle(index)
    minimum = self.get_limiting_digit(index)
    return self.get_train_and_test_data(index, minimum)


  def get_limiting_digit(self, index):
    max_seen_of_each_digit_type = {}
    for i in self.class_names:
      max_seen_of_each_digit_type[i] = 0

    for data in index:
      max_seen_of_each_digit_type[str(data[CreateIndexTask.DIGIT_KEY])] += 1

    minimum = sys.maxsize
    for digit in self.class_names:
      if max_seen_of_each_digit_type[digit] < minimum:
        minimum = max_seen_of_each_digit_type[digit]
    return minimum


  def get_train_and_test_data(self, index, minimum):
    train = []
    test = []

    seen_of_each_digit = {}
    for digit in self.class_names:
      seen_of_each_digit[digit] = 0

    for data_item in index:
      digit_type = str(data_item[CreateIndexTask.DIGIT_KEY])
      image_and_digit = self.read_img(data_item, digit_type)
      seen_of_each_digit[digit_type] += 1
      if seen_of_each_digit[digit_type] <= self.ratio * minimum:
        train.append(image_and_digit)
      elif seen_of_each_digit[digit_type] <= minimum:
        test.append(image_and_digit)
    return train, test


  def read_img(self, data, digit):
    file_name = Folder.DIGIT_CROP_FOLDER + data[Index.FILE_NAME_KEY]
    img = self.api_cv2.imread(file_name)
    digit_index = self.class_names.index(digit)
    return [img, digit_index]
