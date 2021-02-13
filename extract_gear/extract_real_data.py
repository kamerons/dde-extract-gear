from api.api_fuzzywuzzy import ApiFuzzyWuzzy
from api.api_pytesseract import ApiPyTesseract
from extract_gear.extract_image import ExtractImage
from extract_gear.preprocess_set import PreProcessSet

class ExtractRealData:

  ARMOR_TYPES = ["Chain Armor Set", "Dark Lord's Set", "Dragon Slayer Set",
    "Goblin Raider Set", "Great Hero Set", "Leather Armor Set", "Knight Set", "Plate Armor Set"]

  MIN_LEVENSHTEIN = 65


  def __init__(self, extract_image, api_fuzzzywuzzy=None, api_pytesseract=None):
    self.api_fuzzzywuzzy = api_fuzzzywuzzy if api_fuzzzywuzzy else ApiFuzzyWuzzy()
    self.api_pytesseract = api_pytesseract if api_pytesseract else ApiPyTesseract()
    self.extract_image = extract_image


  def get_armor_type(self, img, y, x):
    guess = self.get_armor_type_guess(img, y, x)
    highest = 0
    highest_type = ""
    for armor_type in ExtractRealData.ARMOR_TYPES:
      ratio = self.api_fuzzzywuzzy.ratio(armor_type.lower(), guess.lower())
      if ratio > highest:
        highest_type = armor_type
        highest = ratio
    if highest >= ExtractRealData.MIN_LEVENSHTEIN:
      return highest_type
    return None


  def get_armor_type_guess(self, img, y, x):
    img = self.extract_image.extract_set_image(img, y, x)
    set_processor = PreProcessSet(img)
    processed_img = set_processor.process_set()
    guess = self.api_pytesseract.image_to_string(processed_img).strip()
    return guess
