from fuzzywuzzy import fuzz

class ApiFuzzyWuzzy:

  def ratio(self, text_a, text_b):
    return fuzz.ratio(text_a, text_b)
