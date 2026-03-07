import numpy as np

from extract_gear.preprocess import PreProcessor

class PreProcessStat(PreProcessor):

  AREA_THRESHOLD = 30

  LOW_Y = 31
  LOW_X = 11
  HIGH_Y = 55
  HIGH_X = 51


  def __init__(self, img):
    self.img = img
    self.y_size = img.shape[0]
    self.x_size = img.shape[1]
    self.digits = []


  def process_stat(self):
    self.increase_contrast()
    self.trim_splotches()
    return self.img


  def increase_contrast(self):
    for x in range(self.x_size):
      for y in range(self.y_size):
        if (not y in range(PreProcessStat.LOW_Y, PreProcessStat.HIGH_Y)
          or not x in range(PreProcessStat.LOW_X, PreProcessStat.HIGH_X)):
          self.img[y,x] = [255, 255, 255]
          continue
        coord = (y,x)
        pixel = self.img[coord]
        if self.is_red(pixel):
          self.img[coord] = [0, 0, 0]
        elif self.is_green(pixel):
          self.img[coord] = [0, 0, 0]
        elif self.is_gray(pixel):
          self.img[coord] = [0, 0, 0]
        else:
          self.img[coord] = [255, 255, 255]


  def copy_digit(self, coordinates):
    min_y = PreProcessStat.HIGH_Y
    min_x = PreProcessStat.HIGH_X
    for coordinate in coordinates:
      min_y = min(min_y, coordinate[0])
      min_x = min(min_x, coordinate[1])

    digit = np.full((56,56,3), (255, 255, 255), dtype=np.uint8)
    y_adj = 25 - min_y
    x_adj = 25 - min_x
    for coordinate in coordinates:
      y = coordinate[0] + y_adj
      x = coordinate[1] + x_adj
      digit[y,x] = [0, 0, 0]
    self.digits.append(digit)


  # Remove small leftovers pixels that have a small area. Numbers will never have a small area
  def trim_splotches(self):
    visited = []
    # this order ensures we encounter the leftmost digits first
    for x in range(PreProcessStat.LOW_X, PreProcessStat.HIGH_X):
      for y in range(PreProcessStat.LOW_Y, PreProcessStat.HIGH_Y):
        coord = (y,x)
        if coord in visited:
          continue
        if self.is_black(self.img[coord]):
          aSize, aVisited = self.size_area(coord)
          if aSize < PreProcessStat.AREA_THRESHOLD:
            self.remove_area(coord)
          else:
            self.copy_digit(aVisited)
          for visited_coord in aVisited:
            visited.append(visited_coord)


  def remove_area(self, start_coord):
    toVisit = []
    self.img[start_coord] = [255, 255, 255]
    for coord in self.add_neighbors(start_coord):
      toVisit.append(coord)
    while toVisit != []:
      cur_coord = toVisit.pop()
      self.img[coord] = [255, 255, 255]
      for coord in self.add_neighbors(cur_coord):
        toVisit.append(coord)


  def size_area(self, coord):
    visited = [coord]
    toVisit = []
    aSize = 1
    for coord in self.add_neighbors(coord, visited=visited):
      toVisit.append(coord)
    while toVisit != []:
      coord = toVisit.pop()
      if coord in visited:
        continue
      visited.append(coord)
      aSize += 1
      for coord in self.add_neighbors(coord, visited=visited):
        toVisit.append(coord)
    return aSize, visited


  def add_neighbors(self, coord, visited=[]):
    y, x = coord
    toVisit = []
    if not (y-1,x) in visited and y - 1 >= PreProcessStat.LOW_Y and self.is_black(self.img[y-1, x]):
      toVisit.append((y-1,x))
    if not (y+1,x) in visited and y + 1 < PreProcessStat.HIGH_Y and self.is_black(self.img[y+1, x]):
      toVisit.append((y+1,x))
    if not (y,x-1) in visited and x - 1 >= PreProcessStat.LOW_X and self.is_black(self.img[y, x-1]):
      toVisit.append((y,x-1))
    if not (y,x+1) in visited and x + 1 < PreProcessStat.HIGH_X and self.is_black(self.img[y, x+1]):
      toVisit.append((y,x+1))
    return toVisit
