import os

import numpy as np

from extract_gear.index import Index
from extract_gear.image_splitter import ImageSplitter
from folder.folder import Folder

class TrainStatType:

  NUM_EPOCHS = 10
  LEARN_RATE = .0000002


  def __init__(self, args, api_builtin, api_cv2, api_json, api_random, api_tensorflow):
    self.api_builtin = api_builtin
    self.api_cv2 = api_cv2
    self.api_json = api_json
    self.api_random = api_random
    self.safe = args.safe
    self.api_builtin.safe = True
    self.api_cv2.safe = True
    self.api_json.safe = True
    self.api_tensorflow = api_tensorflow


  def train(self):
    self.api_tensorflow.initialize_tensorflow()
    with self.api_builtin.open(Folder.INDEX_FILE, "r") as fp:
      index = self.api_json.load(fp)
      train, test = self.split_index(.7, index)

      x_train, y_train = TrainStatType.get_preprocess(train)
      x_test, y_test = TrainStatType.get_preprocess(test)

      datagen = self.api_tensorflow.ImageDataGenerator(
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

      opt = self.api_tensorflow.Adam(lr=TrainStatType.LEARN_RATE)
      model.compile(optimizer=opt, loss=self.api_tensorflow.SparseCategoricalCrossentropy(from_logits=True),
        metrics=['accuracy'])
      model.fit(x_train, y_train, epochs=TrainStatType.NUM_EPOCHS, validation_data=(x_test, y_test))
      predictions = model.predict_classes(x_test)
      predictions = predictions.reshape(1,-1)[0]
      self.api_builtin.print(self.api_tensorflow.classification_report(y_test, predictions, target_names=Index.STAT_OPTIONS))
      if not self.safe:
        model.save(Folder.STAT_TYPE_MODEL_FOLDER)
      else:
        self.api_builtin.print("Would save model to: " + Folder.STAT_TYPE_MODEL_FOLDER)


  def get_preprocess(data):
    x = []
    y = []
    for feature, label in data:
      x.append(feature)
      y.append(label)

    x = np.array(x) / 255
    x.reshape(-1, ImageSplitter.STAT_DATA.size[0], ImageSplitter.STAT_DATA.size[1], 1)
    y = np.array(y)
    return (x, y)


  def preview(self, arr):
    print(str(arr[1]))
    self.api_builtin.print(Index.STAT_OPTIONS[arr[1]])
    self.api_cv2.show_img(arr[0])


  def get_model(self):
    model = self.api_tensorflow.Sequential()
    model.add(self.api_tensorflow.Conv2D(32,3,padding="same", activation="relu",
      input_shape=(ImageSplitter.STAT_DATA.size[0], ImageSplitter.STAT_DATA.size[1], 3)))
    model.add(self.api_tensorflow.MaxPool2D())

    model.add(self.api_tensorflow.Conv2D(32, 3, padding="same", activation="relu"))
    model.add(self.api_tensorflow.MaxPool2D())

    model.add(self.api_tensorflow.Conv2D(64, 3, padding="same", activation="relu"))
    model.add(self.api_tensorflow.MaxPool2D())
    model.add(self.api_tensorflow.Dropout(0.4))

    model.add(self.api_tensorflow.Flatten())
    model.add(self.api_tensorflow.Dense(128,activation="relu"))
    model.add(self.api_tensorflow.Dense(len(Index.STAT_OPTIONS)))
    return model


  def split_index(self, ratio, index):
    self.api_random.shuffle(index)
    num = {}
    num_train = {}
    for key in Index.STAT_OPTIONS:
      num[key] = 0
      num_train[key] = 0

    for d in index:
      num[d[Index.STAT_TYPE_KEY]] += 1

    minimum = len(index)
    for key in Index.STAT_OPTIONS:
      if num[key] < minimum:
        minimum = num[key]

    train = []
    test = []
    for d in index:
      stat_type = d[Index.STAT_TYPE_KEY]
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
    file_name = Folder.STAT_CROP_FOLDER + data[Index.FILE_NAME_KEY]
    stat_index = Index.STAT_OPTIONS.index(stat_type)
    return [self.api_cv2.imread(file_name), stat_index]
