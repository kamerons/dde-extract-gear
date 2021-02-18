import os
import numpy as np
import sys

from extract_gear.index import Index
from extract_gear.image_splitter import ImageSplitter
from extract_gear.preprocess_stat import PreProcessStat
from folder.folder import Folder

class TrainStatValue:

  LEARN_RATE = .0000005
  NUM_EPOCHS = 4000


  def __init__(self, args, api_builtin, api_cv2, api_json, api_random, api_tensorflow, image_scaler):
    self.api_builtin = api_builtin
    self.api_cv2 = api_cv2
    self.api_json = api_json
    self.api_random = api_random
    self.safe = args.safe
    self.api_builtin.safe = True
    self.api_cv2.safe = True
    self.api_json.safe = True
    self.api_tensorflow = api_tensorflow
    self.image_scaler = image_scaler


  def train(self):
    self.api_tensorflow.initialize_tensorflow()
    with self.api_builtin.open(Folder.INDEX_FILE, "r") as fp:
      index = self.api_json.load(fp)
      train, test = self.split_index(.7, index)

      x_train, y_train = self.image_scaler.prepare_for_classification(train)
      x_test, y_test = self.image_scaler.prepare_for_classification(test)

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

      opt = self.api_tensorflow.Adam(lr=0.0000005)
      model.compile(optimizer=opt, loss=self.api_tensorflow.SparseCategoricalCrossentropy(from_logits=True),
        metrics=['accuracy'])
      model.fit(x_train, y_train, epochs=4000, validation_data=(x_test, y_test))
      predictions = model.predict_classes(x_test)
      predictions = predictions.reshape(1,-1)[0]
      self.api_builtin.print(self.api_tensorflow.classification_report(y_test, predictions,
        target_names=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]))
      if not self.safe:
        model.save(Folder.STAT_VALUE_MODEL_FOLDER)
      else:
        self.api_builtin.print("Would save model to: " + Folder.STAT_VALUE_MODEL_FOLDER)


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
    model.add(self.api_tensorflow.Dense(10))
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
