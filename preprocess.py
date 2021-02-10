class PreProcess:
  NUM_PIXEL_THRESHOLD = 60
  PIXEL_VALUE_THRESHOLD = 3
  PIXEL_COLOR_THRESHOLD = 40

  AREA_THRESHOLD = 30

  LOW_X = 11
  LOW_Y = 31
  HIGH_X = 51
  HIGH_Y = 55

  img = None

  def __init__(self, img):
    self.img = img

  def run(self, img):
    pass

  def process(self):
    for x in range(56):
      for y in range(56):
        if x < PreProcess.LOW_X or x >= PreProcess.HIGH_X or y < PreProcess.LOW_Y or y >= PreProcess.HIGH_Y:
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

  def is_red(self, pixel):
    blue, green, red = pixel
    return (red > PreProcess.PIXEL_COLOR_THRESHOLD
      and blue < PreProcess.PIXEL_VALUE_THRESHOLD
      and green < PreProcess.PIXEL_VALUE_THRESHOLD)

  def is_green(self, pixel):
    blue, green, red = pixel
    return (green > PreProcess.PIXEL_COLOR_THRESHOLD
      and blue < PreProcess.PIXEL_VALUE_THRESHOLD
      and red < PreProcess.PIXEL_VALUE_THRESHOLD)

  def is_gray(self, pixel):
    blue, green, red = pixel
    return (self.safe_difference(blue, green) < PreProcess.PIXEL_VALUE_THRESHOLD
      and self.safe_difference(blue, red) < PreProcess.PIXEL_VALUE_THRESHOLD
      and blue > PreProcess.PIXEL_COLOR_THRESHOLD)

  def safe_difference(self, c1, c2):
    if c1 > c2:
      return c1 - c2
    else:
      return c2 - c1

  def trim_splotches(self):
    visited = []
    for x in range(PreProcess.LOW_X, PreProcess.HIGH_X):
      for y in range(PreProcess.LOW_Y, PreProcess.HIGH_Y):
        if [y, x] in visited:
          continue
        if self.is_color(self.img[y, x]):
          aSize, aVisited = self.size_area(y, x)
          if aSize < PreProcess.AREA_THRESHOLD:
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
    if not [y-1,x] in visited and y - 1 >= PreProcess.LOW_Y and self.is_color(self.img[y - 1, x]):
      toVisit.append([y-1,x])
    if not [y+1,x] in visited and y + 1 < PreProcess.HIGH_Y and self.is_color(self.img[y + 1, x]):
      toVisit.append([y+1,x])
    if not [y,x-1] in visited and x - 1 >= PreProcess.LOW_X and self.is_color(self.img[y, x - 1]):
      toVisit.append([y,x-1])
    if not [y,x+1] in visited and x + 1 < PreProcess.HIGH_X and self.is_color(self.img[y, x + 1]):
      toVisit.append([y,x+1])
    return toVisit

  def trim_edges(self):
    for x in range(PreProcess.LOW_X, PreProcess.HIGH_X):
      if self.is_color(self.img[PreProcess.LOW_Y, x]):
        self.remove_area(PreProcess.LOW_Y, x)
      if self.is_color(self.img[PreProcess.HIGH_Y - 1, x]):
        self.remove_area(PreProcess.HIGH_Y - 1, x)
    for y in range(PreProcess.LOW_Y, PreProcess.HIGH_Y):
      if self.is_color(self.img[y, PreProcess.LOW_X]):
        self.remove_area(y, PreProcess.LOW_X)
      if self.is_color(self.img[y, PreProcess.HIGH_X - 1]):
        self.remove_area(y, PreProcess.HIGH_X - 1)

  def is_color(self, pixel):
    blue, green, red = pixel
    return blue == 0 and green == 0 and red == 0
