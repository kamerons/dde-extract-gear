from preprocess import PreProcessor

class PreProcessStat(PreProcessor):

  AREA_THRESHOLD = 30

  LOW_X = 11
  LOW_Y = 31
  HIGH_X = 51
  HIGH_Y = 55


  def __init__(self, img):
    self.img = img
    self.x_size = img.shape[1]
    self.y_size = img.shape[0]


  def process_stat(self):
    self.increase_contrast()
    self.trim_edges()
    self.trim_splotches()
    return self.img


  def increase_contrast(self):
    for y in range(self.y_size):
      for x in range(self.x_size):
        if (not y in range(PreProcessStat.LOW_Y, PreProcessStat.HIGH_Y)
          or not x in range(PreProcessStat.LOW_X, PreProcessStat.HIGH_X)):
          self.img[y,x] = [255, 255, 255]
          continue
        pixel = self.img[y,x]
        if self.is_red(pixel):
          self.img[y,x] = [0, 0, 0]
        elif self.is_green(pixel):
          self.img[y,x] = [0, 0, 0]
        elif self.is_gray(pixel):
          self.img[y,x] = [0, 0, 0]
        else:
          self.img[y,x] = [255, 255, 255]


  # often, we detect erroneous detail close to the edge of the bounding box. However, a number
  # will never directly touch the edge of the box. Remove any such detail, cleaning up the image
  def trim_edges(self):
    for y in range(PreProcessStat.LOW_Y, PreProcessStat.HIGH_Y):
      if self.is_black(self.img[y, PreProcessStat.LOW_X]):
        self.remove_area(y, PreProcessStat.LOW_X)
      if self.is_black(self.img[y, PreProcessStat.HIGH_X - 1]):
        self.remove_area(y, PreProcessStat.HIGH_X - 1)

    for x in range(PreProcessStat.LOW_X, PreProcessStat.HIGH_X):
      if self.is_black(self.img[PreProcessStat.LOW_Y, x]):
        self.remove_area(PreProcessStat.LOW_Y, x)
      if self.is_black(self.img[PreProcessStat.HIGH_Y - 1, x]):
        self.remove_area(PreProcessStat.HIGH_Y - 1, x)


  # Remove small leftovers pixels that have a small area. Numbers will never have a small area
  def trim_splotches(self):
    visited = []
    for x in range(PreProcessStat.LOW_X, PreProcessStat.HIGH_X):
      for y in range(PreProcessStat.LOW_Y, PreProcessStat.HIGH_Y):
        if [y, x] in visited:
          continue
        if self.is_black(self.img[y, x]):
          aSize, aVisited = self.size_area(y, x)
          if aSize < PreProcessStat.AREA_THRESHOLD:
            self.remove_area(y, x)
          for coord in aVisited:
            visited.append(coord)


  def remove_area(self, y, x):
    toVisit = []
    y1 = y
    x1 = x
    self.img[y1, x1] = [255, 255, 255]
    for coord in self.add_neighbors(y1, x1):
      toVisit.append(coord)
    while toVisit != []:
      y1, x1 = toVisit.pop()
      self.img[y1,x1] = [255, 255, 255]
      for coord in self.add_neighbors(y1, x1):
        toVisit.append(coord)


  def size_area(self, y, x):
    visited = [[y,x]]
    toVisit = []
    y1 = y
    x1 = x
    aSize = 1
    for coord in self.add_neighbors(y1, x1, visited=visited):
      toVisit.append(coord)
    while toVisit != []:
      y1, x1 = toVisit.pop()
      visited.append([y1, x1])
      aSize += 1
      for coord in self.add_neighbors(y1, x1, visited=visited):
        toVisit.append(coord)
    return aSize, visited


  def add_neighbors(self, y, x, visited=[]):
    toVisit = []
    if not [y-1,x] in visited and y - 1 >= PreProcessStat.LOW_Y and self.is_black(self.img[y - 1, x]):
      toVisit.append([y-1,x])
    if not [y+1,x] in visited and y + 1 < PreProcessStat.HIGH_Y and self.is_black(self.img[y + 1, x]):
      toVisit.append([y+1,x])
    if not [y,x-1] in visited and x - 1 >= PreProcessStat.LOW_X and self.is_black(self.img[y, x - 1]):
      toVisit.append([y,x-1])
    if not [y,x+1] in visited and x + 1 < PreProcessStat.HIGH_X and self.is_black(self.img[y, x + 1]):
      toVisit.append([y,x+1])
    return toVisit
