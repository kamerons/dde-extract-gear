from fuzzywuzzy import fuzz
import pytesseract

from extract_gear.extract_image import ExtractImage
from extract_gear.preprocess_set import PreProcessSet

class ExtractRealData:

  ARMOR_TYPES = ["Chain Armor Set", "Dark Lord's Set", "Dragon Slayer Set",
    "Goblin Raider Set", "Great Hero Set", "Leather Armor Set", "Knight Set", "Plate Armor Set"]

  MIN_LEVENSHTEIN = 65


  def __init__(self):
    pass


  def get_armor_type(self, img, y, x):
    guess = self.get_armor_type_guess(img, y, x)
    highest = 0
    highest_type = ""
    for armor_type in ExtractRealData.ARMOR_TYPES:
      ratio = fuzz.ratio(armor_type.lower(), guess.lower())
      if ratio > highest:
        highest_type = armor_type
        highest = ratio
    if highest >= ExtractRealData.MIN_LEVENSHTEIN:
      return highest_type
    return None


  def get_armor_type_guess(self, img, y, x):
    extract_image = ExtractImage()
    img = extract_image.extract_set_image(img, y, x)
    set_processor = PreProcessSet(img)
    processed_img = set_processor.process_set()
    guess = pytesseract.image_to_string(processed_img).strip()
    return guess
