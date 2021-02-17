import os
import numpy as np

from extract_gear.index import Index
from extract_gear.image_splitter import ImageSplitter
from folder.folder import Folder
from train.train_stat_type import TrainStatType

class CardReader:

  SET_TYPES = ["Chain Armor Set", "Dark Lord's Set", "Dragon Slayer Set",
    "Goblin Raider Set", "Great Hero Set", "Leather Armor Set", "Knight Set", "Plate Armor Set"]

  MIN_LEVENSHTEIN = 65


  def __init__(self, image_splitter, preprocess_factory, api_cv2, api_fuzzzywuzzy, api_pytesseract, api_tensorflow):
    self.api_cv2 = api_cv2
    self.api_fuzzzywuzzy = api_fuzzzywuzzy
    self.api_pytesseract = api_pytesseract
    self.image_splitter = image_splitter
    self.api_tensorflow = api_tensorflow
    self.preprocess_factory = preprocess_factory

    self.stat_type_model = None
    self.stat_value_model = None
    self.initialized = False


  def run(self):
    files = sorted(os.listdir(Folder.PREPROCESS_FOLDER))
    for file_name in files:
      print("File name: %s" % file_name)
      coord = int(file_name[1]), int(file_name[0])
      img = self.api_cv2.imread(Folder.PREPROCESS_FOLDER + file_name)
      card = self.image_splitter.extract_stat_card(img, coord)
      copy = np.full(card.shape, (0,0,0), dtype=np.uint8)
      for y in range(card.shape[0]):
        for x in range(copy.shape[1]):
          copy[y,x] = card[y,x]
      print(self.get_img_data(img, coord))


  def get_img_data(self, img, coord):
    if not self.initialized:
      self.lazy_init()
    armor_type = self.get_armor_type(img, coord)
    stats = self.get_stat_types(img, coord)
    max_level = 16
    current_level = 1
    data = {'armor_set': armor_type, 'current_level': current_level, 'max_level': max_level}
    for stat_key in stats:
      data[stat_key] = int(stats[stat_key])
    return data


  def get_armor_type(self, img, coord):
    guess = self.get_armor_type_guess(img, coord)
    highest = 0
    highest_type = ""
    for armor_type in CardReader.SET_TYPES:
      ratio = self.api_fuzzzywuzzy.ratio(armor_type.lower(), guess.lower())
      if ratio > highest:
        highest_type = armor_type
        highest = ratio
    if highest >= CardReader.MIN_LEVENSHTEIN:
      return highest_type
    return None


  def get_armor_type_guess(self, img, coord):
    img = self.image_splitter.extract_set_image(img, coord)
    set_processor = self.preprocess_factory.get_set_preprocessor(img)
    processed_img = set_processor.process_set()
    guess = self.api_pytesseract.image_to_string(processed_img).strip()
    return guess


  def get_stat_types(self, img, coord):
    images = self.image_splitter.extract_stat_images(img, coord)
    processed_images = self.preprocess_for_stat_type(images)
    predictions = self.stat_type_model.predict_classes(processed_images, batch_size=10, verbose=0)
    stats = {}
    for i in range(14):
      prediction = predictions[i]
      if Index.STAT_OPTIONS[prediction] != Index.NONE:
        stat_num = self.get_stat_num(images[i])
        if stat_num != "NONE":
          stats[Index.STAT_OPTIONS[prediction]] = stat_num
    return stats


  def get_stat_num(self, img):
    preprocessor = self.preprocess_factory.get_stat_preprocessor(img)
    preprocessor.process_stat()
    if (len(preprocessor.digits) == 0):
      return "NONE"
    digits = []
    for digit_image in preprocessor.digits:
      digits.append(digit_image)
    digits = self.preprocess_for_stat_type(digits)
    digit_predictions = self.stat_value_model.predict_classes(digits, verbose=0)
    num = 0
    for digit in digit_predictions:
      num = num * 10
      num += digit
    return num


  #THIS IS COPIED CODE FROM TRAIN_STAT_TYPE
  #PLEASE FIXME
  def preprocess_for_stat_type(self, data):
    x = []
    for feature in data:
      x.append(feature)
    x = np.array(x) / 255
    x.reshape(-1, ImageSplitter.STAT_DATA.size[0], ImageSplitter.STAT_DATA.size[1], 1)
    return x


  # Delay the following operations.  We don't want our dependents to wait for these operations to complete
  # during test code, so we delay to here.
  def lazy_init(self):
    self.api_tensorflow.initialize_tensorflow()
    self.api_pytesseract.initialize_pytesseract()
    self.stat_type_model = self.api_tensorflow.load_model(Folder.STAT_TYPE_MODEL_FOLDER)
    self.stat_value_model = self.api_tensorflow.load_model(Folder.STAT_VALUE_MODEL_FOLDER)
    self.initialized = True
