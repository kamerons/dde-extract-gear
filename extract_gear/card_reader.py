import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

import tensorflow as tf
config = tf.compat.v1.ConfigProto()
config.gpu_options.allow_growth = True
tf.compat.v1.keras.backend.set_session(tf.compat.v1.Session(config=config))

import tensorflow.keras
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Conv2D, MaxPool2D, Flatten, Dropout
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.optimizers import Adam

import numpy as np

from api.api_fuzzywuzzy import ApiFuzzyWuzzy
from api.api_pytesseract import ApiPyTesseract
from api.safe_cv2 import SafeCv2

from extract_gear.extract_image import ExtractImage
from extract_gear.preprocess_set import PreProcessSet
from extract_gear.preprocess_stat import PreProcessStat
from extract_gear.index import Index

from folder.folder import Folder

from train.train_stat_type import TrainStatType

class CardReader:

  SET_TYPES = ["Chain Armor Set", "Dark Lord's Set", "Dragon Slayer Set",
    "Goblin Raider Set", "Great Hero Set", "Leather Armor Set", "Knight Set", "Plate Armor Set"]

  MIN_LEVENSHTEIN = 65


  def __init__(self, extract_image=None, api_cv2=None, api_fuzzzywuzzy=None, api_pytesseract=None):
    self.api_cv2 = api_cv2 if api_cv2 else SafeCv2()
    self.api_fuzzzywuzzy = api_fuzzzywuzzy if api_fuzzzywuzzy else ApiFuzzyWuzzy()
    self.api_pytesseract = api_pytesseract if api_pytesseract else ApiPyTesseract()
    self.extract_image = extract_image if extract_image else ExtractImage()
    self.stat_type_model = tensorflow.keras.models.load_model(Folder.STAT_TYPE_MODEL_FOLDER)
    self.stat_value_model = tensorflow.keras.models.load_model(Folder.STAT_VALUE_MODEL_FOLDER)


  def run(self):
    files = sorted(os.listdir(Folder.PREPROCESS_FOLDER))
    for file_name in files:
      print("File name: %s" % file_name)
      coord = int(file_name[1]), int(file_name[0])
      img = self.api_cv2.imread(Folder.PREPROCESS_FOLDER + file_name)
      card = self.extract_image.extract_stat_card(img, coord)
      copy = np.full(card.shape, (0,0,0), dtype=np.uint8)
      for y in range(card.shape[0]):
        for x in range(copy.shape[1]):
          copy[y,x] = card[y,x]
      print(self.get_img_data(img, coord))
      #self.api_cv2.show_img(copy)


  def get_img_data(self, img, coord):
    armor_type = self.get_armor_type(img, coord)
    #self.api_cv2.show_img(self.extract_image.extract_stat_card(img, coord))
    stats = self.get_stat_types(img, coord)
    max_level = 16
    current_level = 1
    data = {'armor_set': armor_type, 'current_level': current_level, 'max_level': max_level}
    for stat_key in stats:
      data[stat_key] = stats[stat_key]
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
    img = self.extract_image.extract_set_image(img, coord[0], coord[1])
    set_processor = PreProcessSet(img)
    processed_img = set_processor.process_set()
    guess = self.api_pytesseract.image_to_string(processed_img).strip()
    return guess


  def get_stat_types(self, img, coord):
    images = self.extract_image.extract_stat_images(img, coord[0], coord[1])
    processed_images = self.preprocess_for_stat_type(images)
    predictions = self.stat_type_model.predict_classes(processed_images, batch_size=10, verbose=0)
    stats = {}
    for i in range(14):
      prediction = predictions[i]
      print(Index.STAT_OPTIONS[prediction])
      #self.api_cv2.show_img(processed_images[i])
      if Index.STAT_OPTIONS[prediction] != Index.NONE:
        stats[Index.STAT_OPTIONS[prediction]] = self.get_stat_num(images[i])
    return stats


  def get_stat_num(self, img):
    preprocessor = PreProcessStat(img)
    #self.api_cv2.show_img(img)
    preprocessor.process_stat()
    #for i in preprocessor.digits:
    #  self.api_cv2.show_img(i)
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
    x.reshape(-1, ExtractImage.STAT_SIZE, ExtractImage.STAT_SIZE, 1)
    return x
