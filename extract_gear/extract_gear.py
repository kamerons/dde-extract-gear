from extract_gear.card_reader import CardReader

from folder.folder import Folder

class ExtractGear:

  ARMOR_TYPES = ["shoulder_pad", "mask", "hat", "greaves", "shield", "bracer", "belt"]


  def __init__(self, api_builtin, api_cv2, api_pyautogui, api_json, api_time, card_reader):
    self.api_builtin = api_builtin
    self.api_cv2 = api_cv2
    self.api_pyautogui = api_pyautogui
    self.api_json = api_json
    self.api_time = api_time
    self.card_reader = card_reader


  def countdown(self, x, printX):
    while x > 0:
      if printX:
        self.api_builtin.print(x)
      x -= 1
      self.api_time.sleep(1)


  def run(self):
    row_index = RowIndex(self.api_builtin)
    failed = []
    for armor_type in ExtractGear.ARMOR_TYPES:
      self.api_builtin.input(
        "Beginning collection for %s.  Press enter when ready." % armor_type)
      row_index.update_row_pages()
      row_index.reset_for_new_type()
      self.api_builtin.print("Beginning collection. you will have 10 seconds")
      self.countdown(10, True)
      index = []
      for page in range(1, row_index.num_pages + 1):
        if page == row_index.num_pages:
          row_index.update_row_index_for_last_page()
          self.api_builtin.print("You will have 10 seconds")
          self.countdown(10, True)
        elif page >= 2:
          row_index.reset_for_full_page()
          self.api_builtin.print("Switch to the next page, you will have 10 seconds")
          self.countdown(10, True)
        for row in range(row_index.cur_start_row, row_index.end_row + 1):
          end_col = 5 if row != row_index.end_row else row_index.end_col
          for column in range(row_index.cur_start_col, end_col + 1):
            self.add_data_to_index(column, row, page, index, armor_type, failed)
            if row != row_index.end_row or column != row_index.end_col:
              self.countdown(3, False)
          row_index.cur_start_col = 1
      with self.api_builtin.open(Folder.COLLECT_FILE, "w") as fp:
        self.api_builtin.print("Saving progress to disc")
        self.api_json.dump(index, fp)
    self.api_builtin.print(failed)


  def add_data_to_index(self, column, row, page, index, armor_type, failed):
      return self.recursive_add_to_index(0, column, row, page, index, armor_type, failed)

  def recursive_add_to_index(self, depth, column, row, page, index, armor_type, failed):
    name = '%s%d%d.png' % (Folder.TMP_FOLDER, column, row)
    self.api_pyautogui.screenshot(name)
    self.api_builtin.print("COL %d ROW %d" % (column, row))
    img = self.api_cv2.imread(name)
    data = self.card_reader.get_img_data(img, (row, column))
    if not 'base' in data and depth >= 3:
      self.api_builtin.print("failed to read too many times, continuing")
      failed.append({'row': row, 'column': column, 'page': page, 'armor_type': armor_type})
      return
    elif not 'base' in data:
      self.api_builtin.print("Failed to read. Re-trying")
      self.countdown(3, False)
      return self.recursive_add_to_index(depth + 1, column, row, page, index, armor_type, failed)
    data['row'] = row
    data['column'] = column
    data['page'] = page
    data['armor_type'] = armor_type
    self.api_builtin.print(str(data))
    index.append(data)


class RowIndex:
  start_row = 1
  start_col = 1
  cur_start_row = 1
  cur_start_col = 1
  end_row = 3
  end_col = 5
  num_pages = 1


  def __init__(self, api_builtin):
    self.api_builtin = api_builtin
    self.start_row = int(self.api_builtin.input("enter the starting row, typically 1\n> "))
    self.start_col = int(self.api_builtin.input("enter the starting column, typically 3\n> "))
    self.cur_start_col = 1
    self.cur_start_row = 1


  def update_row_pages(self):
    self.num_pages = int(self.api_builtin.input("enter the number of pages\n> "))


  def update_row_index_for_last_page(self):
    self.cur_start_row = int(self.api_builtin.input("Reached the final page.  Enter the starting row\n> "))
    self.cur_start_col = int(self.api_builtin.input("Enter the starting column\n> "))
    self.end_row = int(self.api_builtin.input("Enter the ending row.\n> "))
    self.end_col = int(self.api_builtin.input("enter the ending column.\n> "))


  def reset_for_new_type(self):
    self.end_row = 3
    self.end_col = 5
    self.cur_start_col = self.start_col
    self.cur_start_row = self.start_row


  def reset_for_full_page(self):
    self.end_row = 3
    self.end_col = 5
    self.cur_start_col = 1
    self.cur_start_row = 1
