import tensorflow as tf
config = tf.compat.v1.ConfigProto()
config.gpu_options.allow_growth = True
tf.compat.v1.keras.backend.set_session(tf.compat.v1.Session(config=config))

import tensorflow.keras
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Conv2D, MaxPool2D, Flatten, Dropout
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.optimizers import Adam

from sklearn.metrics import classification_report,confusion_matrix

import os
import numpy as np
import sys

from api.safe_builtin import SafeBuiltIn
from api.safe_cv2 import SafeCv2
from api.safe_json import SafeJson
from api.api_random import ApiRandom

from extract_gear.index import Index
from extract_gear.extract_image import ExtractImage
from extract_gear.preprocess_stat import PreProcessStat
from folder.folder import Folder

class TrainStatValue:

  def __init__(self, safe):
    self.api_builtin = SafeBuiltIn()
    self.api_cv2 = SafeCv2()
    self.api_json = SafeJson()
    self.api_random = ApiRandom()
    self.safe = safe


  def train(self):
    with self.api_builtin.open(Folder.INDEX_FILE, "r") as fp:
      index = self.api_json.load(fp)
      train, test = self.split_index(.7, index)

      x_train, y_train = TrainStatValue.get_preprocess(train)
      x_test, y_test = TrainStatValue.get_preprocess(test)

      datagen = ImageDataGenerator(
        featurewise_center=False,
        samplewise_center=False,
        featurewise_std_normalization=False,
        samplewise_std_normalization=False,
        zca_whitening=False,
        rotation_range=0,
        zoom_range=0.0,
        width_shift_range=0.1,
        height_shift_range=0.1,
        horizontal_flip=False,
        vertical_flip=False)
      datagen.fit(x_train)

      model = self.get_model()
      model.summary(print_fn=self.api_builtin.print)

      opt = Adam(lr=0.0000005)
      model.compile(optimizer=opt, loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=['accuracy'])
      model.fit(x_train, y_train, epochs=4000, validation_data=(x_test, y_test))
      predictions = model.predict_classes(x_test)
      predictions = predictions.reshape(1,-1)[0]
      self.api_builtin.print(classification_report(y_test, predictions, target_names=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]))
      if not self.safe:
        model.save(Folder.STAT_VALUE_MODEL_FOLDER)
      else:
        self.api_builtin.print("Would save model to: " + Folder.STAT_VALUE_MODEL_FOLDER)


  def get_preprocess(data):
    x = []
    y = []
    for feature, label in data:
      x.append(feature)
      y.append(label)

    x = np.array(x) / 255
    x.reshape(-1, ExtractImage.STAT_SIZE, ExtractImage.STAT_SIZE, 1)
    y = np.array(y)
    return (x, y)


  def get_model(self):
    model = Sequential()
    model.add(Conv2D(32,3,padding="same", activation="relu",
      input_shape=(ExtractImage.STAT_SIZE,ExtractImage.STAT_SIZE,3)))
    model.add(MaxPool2D())

    model.add(Conv2D(32, 3, padding="same", activation="relu"))
    model.add(MaxPool2D())

    model.add(Conv2D(64, 3, padding="same", activation="relu"))
    model.add(MaxPool2D())
    model.add(Dropout(0.4))

    model.add(Flatten())
    model.add(Dense(128,activation="relu"))
    model.add(Dense(10))
    return model


  def split_index(self, ratio, index):
    self.api_random.shuffle(index)
    num = {}
    num_train = {}
    for i in range(10):
      num[i] = 0
      num_train[i] = 0

    for d in index:
      if d[Index.STAT_TYPE_KEY] != Index.NONE:
        for digit in self.get_digits(d[Index.STAT_VALUE_KEY]):
          num[digit] += 1

    minimum = sys.maxsize
    for d in range(10):
      if num[d] < minimum:
        minimum = num[d]

    train = []
    test = []
    for data_item in index:
      if data_item[Index.STAT_TYPE_KEY] == Index.NONE:
        continue
      img_and_num = self.read_img(data_item)
      for img, num in img_and_num:
        if num_train[num] < ratio * minimum:
          num_train[num] += 1
          train.append([img, num])
        elif num_train[num] >= minimum:
          continue
        else:
          num_train[num] += 1
          test.append([img, num])
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
