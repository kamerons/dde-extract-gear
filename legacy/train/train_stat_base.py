import os
import numpy as np
import sys

from extract_gear.index import Index
from extract_gear.image_splitter import ImageSplitter
from extract_gear.preprocess_stat import PreProcessStat
from folder.folder import Folder

class TrainStatBase:

  def __init__(self, args, api_builtin, api_cv2, api_json, api_tensorflow, image_scaler,
    num_epochs, class_names, save_file, decay_steps, decay_rate):
    self.api_builtin = api_builtin
    self.api_cv2 = api_cv2
    self.api_json = api_json
    self.safe = args.safe
    self.api_builtin.safe = True
    self.api_cv2.safe = True
    self.api_json.safe = True
    self.api_tensorflow = api_tensorflow
    self.image_scaler = image_scaler
    self.num_epochs = num_epochs
    self.class_names = class_names
    self.save_file = save_file
    self.decay_steps = decay_steps
    self.decay_rate = decay_rate


  def train(self):
    self.api_tensorflow.initialize_tensorflow()
    train, test = self.split_index()

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

    initial_learning_rate = .00002
    lr_schedule = self.api_tensorflow.ExponentialDecay(
      initial_learning_rate,
      decay_steps=self.decay_steps,
      decay_rate=self.decay_rate,
      staircase=False)

    opt = self.api_tensorflow.Adam(learning_rate=lr_schedule)
    model.compile(optimizer=opt, loss=self.api_tensorflow.SparseCategoricalCrossentropy(from_logits=True),
      metrics=['accuracy'])
    model.fit(x_train, y_train, epochs=self.num_epochs, validation_data=(x_test, y_test))
    predictions = model.predict_classes(x_test)
    predictions = predictions.reshape(1,-1)[0]
    self.api_builtin.print(self.api_tensorflow.classification_report(y_test, predictions,
      target_names=self.class_names))
    if not self.safe:
      self.api_builtin.print("Saving model to: " + self.save_file)
      model.save(self.save_file)
    else:
      self.api_builtin.print("Would save model to: " + self.save_file)


  def get_model(self):
    model = self.api_tensorflow.Sequential()
    model.add(self.api_tensorflow.Conv2D(16,3,padding="same", activation="relu",
      input_shape=(ImageSplitter.STAT_DATA.size[0], ImageSplitter.STAT_DATA.size[1], 3)))
    model.add(self.api_tensorflow.MaxPool2D())

    model.add(self.api_tensorflow.Conv2D(16, 3, padding="same", activation="relu"))
    model.add(self.api_tensorflow.MaxPool2D())

    model.add(self.api_tensorflow.Conv2D(32, 3, padding="same", activation="relu"))
    model.add(self.api_tensorflow.MaxPool2D())
    model.add(self.api_tensorflow.Dropout(0.4))

    model.add(self.api_tensorflow.Flatten())
    model.add(self.api_tensorflow.Dense(64,activation="relu"))
    model.add(self.api_tensorflow.Dense(len(self.class_names)))
    return model


  def preview(self, image_and_class):
    image, clz = image_and_class
    print(self.class_names[clz])
    self.api_cv2.show_img(image)


  def split_index(self):
    return None, None, None
