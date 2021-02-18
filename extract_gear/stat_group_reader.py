import numpy as np

from extract_gear.index import Index
from folder.folder import Folder
from train.train_stat_type import TrainStatType

class StatGroupReader:

  TOTAL_NUM_IMAGES = 14


  def __init__(self, preprocess_factory, api_tensorflow, image_scaler):
    self.preprocess_factory = preprocess_factory
    self.api_tensorflow = api_tensorflow
    self.initialized = False
    self.stat_type_model = None
    self.stat_value_model = None
    self.image_scaler = image_scaler


  def get_stat_types_and_values(self, images):
    self.initialize_if_necessary()
    value_scaled_images = self.image_scaler.prepare_for_classification(images)
    predictions = self.stat_type_model.predict_classes(value_scaled_images,
      batch_size=StatGroupReader.TOTAL_NUM_IMAGES, verbose=0)
    stats = {}
    for i in range(StatGroupReader.TOTAL_NUM_IMAGES):
      self.update_stats_with_image(predictions[i], images[i], stats)
    return stats


  def update_stats_with_image(self, prediction, img, stats):
    if Index.STAT_OPTIONS[prediction] != Index.NONE:
      stat_num = self.get_stat_num_for_img(img)
      if stat_num != None:
        stats[Index.STAT_OPTIONS[prediction]] = stat_num


  def get_stat_num_for_img(self, img):
    preprocessor = self.preprocess_factory.get_stat_preprocessor(img)
    preprocessor.process_stat()
    if (len(preprocessor.digits) == 0):
      return None
    return self.get_stat_num_from_nonzero_digits(preprocessor.digits)


  def get_stat_num_from_nonzero_digits(self, digit_images):
    value_scaled_digits = self.image_scaler.prepare_for_classification(digit_images)
    digit_predictions = self.stat_value_model.predict_classes(value_scaled_digits, verbose=0)
    return self.build_num_from_digits(digit_predictions)


  def build_num_from_digits(self, digit_predictions):
    num = 0
    for digit in digit_predictions:
      num = num * 10
      num += digit
    return num


  def initialize_if_necessary(self):
    if not self.initialized:
      self.api_tensorflow.initialize_tensorflow()
      self.stat_type_model = self.api_tensorflow.load_model(Folder.STAT_TYPE_MODEL_FOLDER)
      self.stat_value_model = self.api_tensorflow.load_model(Folder.STAT_VALUE_MODEL_FOLDER)
      self.initialized = True
