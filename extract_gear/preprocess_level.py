from extract_gear.preprocess import PreProcessor

class PreProcessLevel(PreProcessor):

  def __init__(self, img):
    self.img = img
    self.x_size = img.shape[1]
    self.y_size = img.shape[0]


  def process_level(self):
    for y in range(self.y_size):
      for x in range(self.x_size):
        pixel = self.img[y,x]
        if self.is_cyan(pixel):
          self.img[y,x] = [0, 0, 0]
        else:
          self.img[y,x] = [255, 255, 255]
    return self.img
