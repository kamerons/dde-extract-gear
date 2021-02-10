from extract_gear.extract_training_data import get_set_img
from preprocess_set import PreProcessSet
from fuzzywuzzy import fuzz
import os
import cv2
import pytesseract

armor_types = ["Chain Armor Set", "Dark Lord's Set", "Dragon Slayer Set",
  "Goblin Raider Set", "Great Hero Set", "Leather Armor Set", "Knight Set", "Plate Armor Set"]

MIN_LEVENSHTEIN = 65
class ExtractRealData:
  def __init__(self):
    pass

  def run_get_all_types(self):
    files = sorted(os.listdir('data/preprocess'))
    smallest_diff = 100
    smallest_diff_file_name = ""
    for file_name in files:
      img = cv2.imread('data/preprocess/' + file_name)
      guess = self.get_armor_type_guess(img, int(file_name[1]), int(file_name[0]))
      highest = 0
      second_highest = -1
      for armor_type in armor_types:
        ratio = fuzz.ratio(armor_type.lower(), guess.lower())
        if ratio > highest:
          second_highest = highest
          highest = ratio
        elif ratio > second_highest:
          second_highest = ratio
      confidence = highest - second_highest
      if confidence < smallest_diff:
        smallest_diff = confidence
        smallest_diff_file_name = file_name
      for armor_type in armor_types:
        ratio = fuzz.ratio(armor_type.lower(), guess.lower())

    img = cv2.imread('data/preprocess/' + smallest_diff_file_name)
    guess = self.get_armor_type_guess(img, int(smallest_diff_file_name[1]), int(smallest_diff_file_name[0]))
    print("The guess was %s" % guess)
    highest = 0
    second_highest = -1
    for armor_type in armor_types:
      ratio = fuzz.ratio(armor_type.lower(), guess.lower())
      if ratio > highest:
        second_highest = highest
        highest = ratio
      elif ratio > second_highest:
        second_highest = ratio
    print("the confidence was %d" % (highest - second_highest))


  def get_armor_type(self, img, y, x):
    guess = self.get_armor_type_guess(img, y, x)
    highest = 0
    highest_type = ""
    for armor_type in armor_types:
      ratio = fuzz.ratio(armor_type.lower(), guess.lower())
      if ratio > highest:
        highest_type = armor_type
        highest = ratio
    if highest >= MIN_LEVENSHTEIN:
      return highest_type
    return None


  def get_armor_type_guess(self, img, y, x):
    img = get_set_img(img, y, x)
    set_processor = PreProcessSet(img)
    processed_img = set_processor.process_set()
    guess = pytesseract.image_to_string(processed_img).strip()
    return guess

ExtractRealData().run_get_all_types()