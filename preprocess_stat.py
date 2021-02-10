class PreProcessStat:
  NUM_PIXEL_THRESHOLD = 60
  PIXEL_VALUE_THRESHOLD = 3
  PIXEL_COLOR_THRESHOLD = 40

  AREA_THRESHOLD = 30

  LOW_X = 11
  LOW_Y = 31
  HIGH_X = 51
  HIGH_Y = 55

  img = None
  x_size = 0
  y_size = 0

  def __init__(self, img):
    self.img = img
    self.x_size = img.shape[1]
    self.y_size = img.shape[0]

  def process_stat(self):
    for x in range(self.x_size):
      for y in range(self.y_size):
        if x < PreProcessStat.LOW_X or x >= PreProcessStat.HIGH_X or y < PreProcessStat.LOW_Y or y >= PreProcessStat.HIGH_Y:
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
    self.trim_edges()
    self.trim_splotches()
    return self.img

  def is_cyan(self, pixel):
    blue, green, red = pixel
    return blue == 255 and green == 255 and red < 200


  def is_red(self, pixel):
    blue, green, red = pixel
    return (red > PreProcessStat.PIXEL_COLOR_THRESHOLD
      and blue < PreProcessStat.PIXEL_VALUE_THRESHOLD
      and green < PreProcessStat.PIXEL_VALUE_THRESHOLD)

  def is_green(self, pixel):
    blue, green, red = pixel
    return (green > PreProcessStat.PIXEL_COLOR_THRESHOLD
      and blue < PreProcessStat.PIXEL_VALUE_THRESHOLD
      and red < PreProcessStat.PIXEL_VALUE_THRESHOLD)

  def is_gray(self, pixel):
    blue, green, red = pixel
    return (self.safe_difference(blue, green) < PreProcessStat.PIXEL_VALUE_THRESHOLD
      and self.safe_difference(blue, red) < PreProcessStat.PIXEL_VALUE_THRESHOLD
      and blue > PreProcessStat.PIXEL_COLOR_THRESHOLD)

  def safe_difference(self, c1, c2):
    if c1 > c2:
      return c1 - c2
    else:
      return c2 - c1

  def trim_splotches(self):
    visited = []
    for x in range(PreProcessStat.LOW_X, PreProcessStat.HIGH_X):
      for y in range(PreProcessStat.LOW_Y, PreProcessStat.HIGH_Y):
        if [y, x] in visited:
          continue
        if self.is_color(self.img[y, x]):
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
    if not [y-1,x] in visited and y - 1 >= PreProcessStat.LOW_Y and self.is_color(self.img[y - 1, x]):
      toVisit.append([y-1,x])
    if not [y+1,x] in visited and y + 1 < PreProcessStat.HIGH_Y and self.is_color(self.img[y + 1, x]):
      toVisit.append([y+1,x])
    if not [y,x-1] in visited and x - 1 >= PreProcessStat.LOW_X and self.is_color(self.img[y, x - 1]):
      toVisit.append([y,x-1])
    if not [y,x+1] in visited and x + 1 < PreProcessStat.HIGH_X and self.is_color(self.img[y, x + 1]):
      toVisit.append([y,x+1])
    return toVisit

  def trim_edges(self):
    for x in range(PreProcessStat.LOW_X, PreProcessStat.HIGH_X):
      if self.is_color(self.img[PreProcessStat.LOW_Y, x]):
        self.remove_area(PreProcessStat.LOW_Y, x)
      if self.is_color(self.img[PreProcessStat.HIGH_Y - 1, x]):
        self.remove_area(PreProcessStat.HIGH_Y - 1, x)
    for y in range(PreProcessStat.LOW_Y, PreProcessStat.HIGH_Y):
      if self.is_color(self.img[y, PreProcessStat.LOW_X]):
        self.remove_area(y, PreProcessStat.LOW_X)
      if self.is_color(self.img[y, PreProcessStat.HIGH_X - 1]):
        self.remove_area(y, PreProcessStat.HIGH_X - 1)

  def is_color(self, pixel):
    blue, green, red = pixel
    return blue == 0 and green == 0 and red == 0
