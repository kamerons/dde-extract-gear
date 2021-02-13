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

from api.safe_builtin import SafeBuiltIn
from api.safe_cv2 import SafeCv2
from api.safe_json import SafeJson
from api.api_random import ApiRandom

from extract_gear.index import Index
from extract_gear.extract_image import ExtractImage
from folder.folder import Folder

class TrainStatType:

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

      x_train, y_train = TrainStatType.get_preprocess(train)
      x_test, y_test = TrainStatType.get_preprocess(test)

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
      self.api_builtin.print(classification_report(y_test, predictions, target_names=Index.STAT_OPTIONS))
      if not self.safe:
        model.save(Folder.STAT_TYPE_MODEL_FOLDER)
      else:
        self.api_builtin.print("Would save model to: " + Folder.STAT_TYPE_MODEL_FOLDER)


  def get_preprocess(data):
    x = []
    y = []
    for data_item in data:
      if type(data_item) == tuple:
        x.append(data_item[0])
        y.append(data_item[1])
      else:
        x.append(data_item)

    x = np.array(x) / 255
    x.reshape(-1, ExtractImage.STAT_SIZE, ExtractImage.STAT_SIZE, 1)
    y = np.array(y)
    return (x, y)


  def preview(self, arr):
    print(str(arr[1]))
    self.api_builtin.print(Index.STAT_OPTIONS[arr[1]])
    self.api_cv2.show_img(arr[0])


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
    model.add(Dense(len(Index.STAT_OPTIONS)))
    return model


  def split_index(self, ratio, index):
    self.api_random.shuffle(index)
    num = {}
    num_train = {}
    for key in Index.STAT_OPTIONS:
      num[key] = 0
      num_train[key] = 0

    for d in index:
      num[d[Index.TYPE_KEY]] += 1

    minimum = len(index)
    for key in Index.STAT_OPTIONS:
      if num[key] < minimum:
        minimum = num[key]

    train = []
    test = []
    for d in index:
      stat_type = d[Index.TYPE_KEY]
      if num_train[stat_type] < ratio * minimum:
        num_train[stat_type] += 1
        x = self.read_img(d, stat_type)
        train.append(x)
      elif num_train[stat_type] >= minimum:
        continue
      else:
        num_train[stat_type] += 1
        x = self.read_img(d, stat_type)
        test.append(x)
    return train, test


  def read_img(self, data, stat_type):
    file_name = Folder.STAT_CROP_FOLDER + data[Index.FILE_KEY]
    stat_index = Index.STAT_OPTIONS.index(stat_type)
    return [self.api_cv2.imread(file_name), stat_index]
