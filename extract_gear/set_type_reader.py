class SetTypeReader:

  SET_TYPES = ["Chain Armor Set", "Dark Lord's Set", "Dragon Slayer Set",
    "Goblin Raider Set", "Great Hero Set", "Leather Armor Set", "Knight Set", "Plate Armor Set"]

  MIN_LEVENSHTEIN = 65


  def __init__(self, preprocess_factory, api_fuzzzywuzzy, api_pytesseract):
    self.preprocess_factory = preprocess_factory
    self.api_fuzzzywuzzy = api_fuzzzywuzzy
    self.api_pytesseract = api_pytesseract
    self.initialized = False


  def get_armor_type(self, img):
    self.initialize_if_necessary()
    guess = self.get_armor_type_guess(img)
    return self.get_closet_armor_type_to_guess(guess)


  def get_armor_type_guess(self, img):
    set_processor = self.preprocess_factory.get_set_preprocessor(img)
    processed_img = set_processor.process_set()
    guess = self.api_pytesseract.image_to_string(processed_img).strip()
    return guess


  def get_closet_armor_type_to_guess(self, guess):
    highest = 0
    highest_type = ""
    for armor_type in SetTypeReader.SET_TYPES:
      ratio = self.api_fuzzzywuzzy.ratio(armor_type.lower(), guess.lower())
      if ratio > highest:
        highest_type = armor_type
        highest = ratio
    if highest >= SetTypeReader.MIN_LEVENSHTEIN:
      return highest_type
    return None


  def initialize_if_necessary(self):
    if not self.initialized:
      self.api_pytesseract.initialize_pytesseract()
      self.initialized = True
