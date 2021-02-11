from preprocess import PreProcessor

class PreProcessSet(PreProcessor):

  LOW_X = 11
  LOW_Y = 31
  HIGH_X = 51
  HIGH_Y = 55


  def __init__(self, img):
    self.img = img
    self.x_size = img.shape[1]
    self.y_size = img.shape[0]


  def process_set(self):
    for y in range(self.y_size):
      for x in range(self.x_size):
        pixel = self.img[y,x]
        if self.is_white(pixel):
          self.img[y,x] = [0, 0, 0]
        else:
          self.img[y,x] = [255, 255, 255]
    return self.img
