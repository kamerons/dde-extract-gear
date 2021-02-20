import unittest
import timeout_decorator

from extract_gear.armor_visitor import ArmorVisitor, Page

class TestArmorVisitor(unittest.TestCase):

  @timeout_decorator.timeout(1)
  def test_page_fullPage(self):
    page = Page(1, 1, 5, 3)

    actual_positions = self.get_all(page)
    row_one = self.create_full_row(1, 5)
    row_two = self.create_full_row(2, 5)
    row_three = self.create_full_row(3, 5)
    expected_positions = row_one + row_two + row_three
    self.assertEqual(expected_positions, actual_positions)


  @timeout_decorator.timeout(1)
  def test_page_startsEarly(self):
    page = Page(3, 1, 5, 3)

    actual_positions = self.get_all(page)
    row_one = self.create_row(1, 3, 5)
    row_two = self.create_full_row(2, 5)
    row_three = self.create_full_row(3, 5)
    expected_positions = row_one + row_two + row_three
    self.assertEqual(expected_positions, actual_positions)


  @timeout_decorator.timeout(1)
  def test_page_endsEarly(self):
    page = Page(1, 1, 3, 3)

    actual_positions = self.get_all(page)
    row_one = self.create_full_row(1, 5)
    row_two = self.create_full_row(2, 5)
    row_three = self.create_row(3, 1, 3)
    expected_positions = row_one + row_two + row_three
    self.assertEqual(expected_positions, actual_positions)


  @timeout_decorator.timeout(1)
  def test_page_endsRowEarly(self):
    page = Page(1, 1, 4, 2)

    actual_positions = self.get_all(page)
    row_one = self.create_full_row(1, 5)
    row_two = self.create_row(2, 1, 4)
    expected_positions = row_one + row_two
    self.assertEqual(expected_positions, actual_positions)


  @timeout_decorator.timeout(1)
  def test_page_endsAndStartsEarly(self):
    page = Page(2, 1, 4, 3)

    actual_positions = self.get_all(page)
    row_one = self.create_row(1, 2, 5)
    row_two = self.create_full_row(2, 5)
    row_three = self.create_row(3, 1, 4)
    expected_positions = row_one + row_two + row_three
    self.assertEqual(expected_positions, actual_positions)


  def test_armorVisitor_iterate_onePage(self):
    armor_visitor = ArmorVisitor(1, 1, 1, 1, 5, 3)
    coordinate_collector = CoordinateCollector()

    armor_visitor.iterate(coordinate_collector.collect_coordinates_callback)

    row_one = self.create_full_row(1, 5, page=1)
    row_two = self.create_full_row(2, 5, page=1)
    row_three = self.create_full_row(3, 5, page=1)
    expected_positions = row_one + row_two + row_three

    self.assertEqual(expected_positions, coordinate_collector.coordinates)


  def test_armorVisitor_iterate_onePartialPage(self):
    armor_visitor = ArmorVisitor(1, 3, 1, 1, 4, 3)
    coordinate_collector = CoordinateCollector()

    armor_visitor.iterate(coordinate_collector.collect_coordinates_callback)

    row_one = self.create_row(1, 3, 5, page=1)
    row_two = self.create_full_row(2, 5, page=1)
    row_three = self.create_row(3, 1, 4, page=1)
    expected_positions = row_one + row_two + row_three

    self.assertEqual(expected_positions, coordinate_collector.coordinates)


  def test_armorVisitor_iterate_threePages(self):
    armor_visitor = ArmorVisitor(3, 3, 1, 2, 4, 3)
    coordinate_collector = CoordinateCollector()

    armor_visitor.iterate(coordinate_collector.collect_coordinates_callback)

    row_one = self.create_row(1, 3, 5, page=1)
    row_two = self.create_full_row(2, 5, page=1)
    row_three = self.create_full_row(3, 5, page=1)
    page_two = self.create_full_page(2, 3, 5)
    p3_row_two = self.create_full_row(2, 5, page=3)
    p3_row_three = self.create_row(3, 1, 4, page=3)
    expected_positions = row_one + row_two + row_three + page_two + p3_row_two + p3_row_three

    self.assertEqual(expected_positions, coordinate_collector.coordinates)


  def create_full_page(self, page_num, num_rows, num_cols):
    rows = []
    for i in range(1, num_rows + 1):
      rows += self.create_full_row(i, num_cols, page=page_num)
    return rows


  def create_full_row(self, row_num, length, page=None):
    return self.create_row(row_num, 1, length, page)


  def create_row(self, row_num, row_start, row_end, page=None):
    coords = []
    for i in range(row_start, row_end + 1):
      coord = (row_num, i) if page == None else (row_num, i, page)
      coords.append(coord)
    return coords


  def get_all(self, page):
    data = []
    for position in page:
      data.append(position)
    return data


class CoordinateCollector:

  def __init__(self):
    self.coordinates = []


  def collect_coordinates_callback(self, gear_coord, page_num):
    self.coordinates.append(gear_coord + (page_num,))
