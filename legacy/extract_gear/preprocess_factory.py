from extract_gear.preprocess_level import PreProcessLevel
from extract_gear.preprocess_set import PreProcessSet
from extract_gear.preprocess_stat import PreProcessStat

class PreprocessFactory:

  def get_set_preprocessor(self, img):
    return PreProcessSet(img)


  def get_stat_preprocessor(self, img):
    return PreProcessStat(img)


  def get_level_preprocessor(self, img):
    return PreProcessLevel(img)
