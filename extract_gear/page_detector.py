import numpy as np
from sys import maxsize

from extract_gear.armor_visitor import ArmorVisitor
from folder.folder import Folder

class DistData:
  def __init__(self, size):
    self.rows = []
    for _ in range(size):
      self.rows.append(0)
    self.end_pos = None


class PageDetector:

  ROW_STANDARD_THRESHOLD = 1_000_000
  ROW_BLUEPRINT_THRESHOLD = 4_000

  EMPTY_STANDARD_THRESHOLD = 10_000_000
  EMPTY_BLUEPRINT_THRESHOLD = 30_000_000


  def __init__(self, api_cv2, image_splitter):
    self.api_cv2 = api_cv2
    self.image_splitter = image_splitter


  def get_data_for_last_page(self, before_img, after_img, is_blueprint=False):
    most_similar_row, euclidean_distance, end_pos = self.detect_most_similar_row(before_img,
      after_img, is_blueprint)
    row_threshold = PageDetector.ROW_BLUEPRINT_THRESHOLD if is_blueprint \
      else PageDetector.ROW_STANDARD_THRESHOLD
    if euclidean_distance > row_threshold:
      start_row = 1
    else:
      start_row = most_similar_row + 1

    if end_pos == None:
      end_pos = (6, 4) if is_blueprint else (3, 5)

    return (start_row,) + end_pos


  def detect_most_similar_row(self, before_img, after_img, is_blueprint):
    last_row_start_index = 20 if is_blueprint else 10
    before_row_images = self.image_splitter.extract_page_images(before_img, is_blueprint)[last_row_start_index:]
    before_histograms = self.cache_before_images(before_row_images)
    after_images = self.image_splitter.extract_page_images(after_img, is_blueprint)
    empty_gear_histogram = self.get_empty_gear_histogram()
    return self.get_best_row(before_histograms, after_images, empty_gear_histogram, is_blueprint, before_row_images)


  def cache_before_images(self, images):
    histograms = []
    for img in images:
      histogram = self.get_histogram(img)
      histograms.append(histogram)
    return histograms


  def get_best_row(self, before_histograms, after_images, empty_gear_histogram, is_blueprint, dm):
    num_rows = 6 if is_blueprint else 3
    if is_blueprint:
      armor_visitor = ArmorVisitor(1, 1, 1, 1, 4, num_rows, num_col_page=4, num_row_page=num_rows)
    else:
      armor_visitor = ArmorVisitor(1, 1, 1, 1, 5, num_rows)

    dist_data = DistData(num_rows)
    callback_fn = self.get_visit_fn(dist_data, after_images, before_histograms, empty_gear_histogram,
      is_blueprint, dm)
    armor_visitor.iterate(callback_fn)

    best_row, smallest_dist = self.get_best_from_dist(dist_data)

    return (best_row + 1), smallest_dist, dist_data.end_pos


  def get_visit_fn(self, dist_data, after_images, before_histograms, empty_gear_histogram,
    is_blueprint, dm):
    def visit_callback(gear_coord, page_num, index):
      row, col = gear_coord
      img = after_images[index]
      histogram = self.get_histogram(img)
      dist_data.rows[row - 1] += self.euclidean_distance(histogram, before_histograms[col - 1])
      if dist_data.end_pos == None:
        empty_gear_diff = self.euclidean_distance(histogram, empty_gear_histogram)
        empty_threshold = PageDetector.EMPTY_BLUEPRINT_THRESHOLD if is_blueprint \
          else PageDetector.EMPTY_STANDARD_THRESHOLD
        if empty_gear_diff <= empty_threshold:
          dist_data.end_pos = self.get_last_pos(gear_coord, is_blueprint)
    return visit_callback


  def euclidean_distance(self, histogram1, histogram2):
    stop_point = min(len(histogram1), len(histogram2))
    distance = 0
    for i in range(stop_point):
      distance += (histogram1[i] - histogram2[i]) ** 2
    return distance


  def get_empty_gear_histogram(self):
    empty_gear_file = Folder.STANDARD_EMPTY_GEAR
    img = self.api_cv2.imread(empty_gear_file)
    histogram = self.get_histogram(img)
    return histogram


  def get_histogram(self, img):
    gray_img = self.api_cv2.cvtColor(img, self.api_cv2.COLOR_BGR2GRAY())
    histogram = self.api_cv2.calcHist([gray_img], [0], None, [256], [0, 256])
    return histogram


  def get_last_pos(self, gear_cool, is_blueprint):
    row, col = gear_cool
    last_col_pos = 4 if is_blueprint else 5
    if col == 1:
      return (row, last_col_pos)
    else:
      return (row , col - 1)


  def get_best_from_dist(self, dist_data):
    smallest_dist = maxsize
    best_row = 0
    for row in range(len(dist_data.rows)):
      if dist_data.rows[row] < smallest_dist:
        best_row = row
        smallest_dist = dist_data.rows[row]
    return best_row, smallest_dist
