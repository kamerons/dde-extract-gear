import os
import numpy as np
import sys

from extract_gear.index import Index
from extract_gear.image_splitter import ImageSplitter
from extract_gear.preprocess_stat import PreProcessStat
from folder.folder import Folder
from train.train_stat_base import TrainStatBase

class TrainStatValue(TrainStatBase):

  LEARN_RATE = .0000005
  NUM_EPOCHS = 4000


  def __init__(self, args, api_builtin, api_cv2, api_json, api_random, api_tensorflow, image_scaler):
    class_names = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
    super().__init__(args, api_builtin, api_cv2, api_json, api_tensorflow, image_scaler,
    TrainStatValue.NUM_EPOCHS, TrainStatValue.LEARN_RATE, class_names)
    self.api_random = api_random
    self.ratio = .7


  def split_index(self, index):
    self.api_random.shuffle(index)
    minimum = self.get_limiting_digit(index)
    return self.get_train_and_test_data(index, minimum)


  def get_limiting_digit(self, index):
    max_seen_of_each_digit_type = {}
    for i in range(10):
      max_seen_of_each_digit_type[i] = 0

    for data in index:
      if data[Index.STAT_TYPE_KEY] != Index.NONE:
        for digit in self.get_digits(data[Index.STAT_VALUE_KEY]):
          max_seen_of_each_digit_type[digit] += 1

    minimum = sys.maxsize
    for digit in range(10):
      if max_seen_of_each_digit_type[digit] < minimum:
        minimum = max_seen_of_each_digit_type[digit]
    return minimum


  def get_train_and_test_data(self, index, minimum):
    train = []
    test = []

    seen_of_each_digit = {}
    for digit in range(10):
      seen_of_each_digit[digit] = 0

    for data_item in index:
      if data_item[Index.STAT_TYPE_KEY] == Index.NONE:
        continue
      img_and_digit = self.read_img(data_item)
      for img, digit in img_and_digit:
        if seen_of_each_digit[digit] < self.ratio * minimum:
          seen_of_each_digit[digit] += 1
          train.append([img, digit])
        elif seen_of_each_digit[digit] < minimum:
          seen_of_each_digit[digit] += 1
          test.append([img, digit])
    return train, test


  def read_img(self, data):
    file_name = Folder.STAT_CROP_FOLDER + data[Index.FILE_NAME_KEY]
    original = self.api_cv2.imread(file_name)
    preprocessor = PreProcessStat(original)
    preprocessor.process_stat()
    num = data[Index.STAT_VALUE_KEY]
    digit_nums = self.get_digits(num)
    img_and_num = []
    for i in range(len(digit_nums)):
      img_and_num.append([preprocessor.digits[i], digit_nums[i]])
    return img_and_num


  def get_digits(self, num):
    digits = []
    while num > 0:
      digits.append(num % 10)
      num = int(num / 10)
    digits.reverse()
    return digits
