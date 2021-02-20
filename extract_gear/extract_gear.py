from extract_gear.armor_visitor import ArmorVisitor

from folder.folder import Folder

class ExtractGear:

  ARMOR_TYPES = ["shoulder_pad", "mask", "hat", "greaves", "shield", "bracer", "belt"]
  MAX_RECURSE = 3


  def __init__(self, api_builtin, api_cv2, api_pyautogui, api_json, api_time, api_keyboard, card_reader):
    self.api_builtin = api_builtin
    self.api_cv2 = api_cv2
    self.api_pyautogui = api_pyautogui
    self.api_json = api_json
    self.api_time = api_time
    self.api_keyboard = api_keyboard
    self.card_reader = card_reader


  def run(self):
    failed = []
    index = []
    start_pos = self.api_builtin.input_safe_int("Enter the starting column (1-5), typically 3\n> ")
    for is_blueprint in [True, False]:
      num_col = 4 if is_blueprint else 5
      num_row = 6 if is_blueprint else 3
      self.api_builtin.print("Is blueprint is: %s" % str(is_blueprint))
      for armor_type in ExtractGear.ARMOR_TYPES:
        self.api_builtin.input(
          "Beginning collection for %s.  Press enter when ready." % armor_type)
        final_page = self.api_builtin.input_safe_int("Enter the number of pages\n> ")
        last_page_start_row = self.api_builtin.input_safe_int("Enter the starting row on the last page\n> ")
        last_page_end_row = self.api_builtin.input_safe_int("Enter the last row on the last page\n> ")
        last_page_end_col = self.api_builtin.input_safe_int("Enter the last column on the last page\n> ")
        armor_iterator = ArmorVisitor(final_page, start_pos, 1, last_page_start_row, last_page_end_col,
          last_page_end_row, num_col_page=num_col, num_row_page=num_row)
        self.api_builtin.print("Preparing to collect data for %s. Press o then p to take a screenshot")

        armor_iterator.iterate(self.get_add_data_to_index_fn(armor_type, is_blueprint, index, failed))

        with self.api_builtin.open(Folder.COLLECT_FILE, "w") as fp:
          self.api_builtin.print("Saving progress to disc")
          self.api_json.dump(index, fp)
      self.api_builtin.print(failed)


  # We need to curry this function call so we can append to the index without making it
  # an instance variable on the class
  def get_add_data_to_index_fn(self, armor_type, is_blueprint, index, failed):
    def true_callback(gear_coord, page_num):
      return self.add_data_to_index(gear_coord, page_num, armor_type, is_blueprint, index, failed)
    return true_callback


  def add_data_to_index(self, gear_coord, page, armor_type, is_blueprint, index, failed):
      return self.recursive_add_to_index(0, gear_coord, page, armor_type, is_blueprint, index, failed)


  def recursive_add_to_index(self, depth, gear_coord, page, armor_type, is_blueprint, index, failed):
    # small hack TODO add a debouncer
    self.api_keyboard.wait_for('o')
    self.api_keyboard.wait_for('p')
    name = '%s%d%d.png' % (Folder.TMP_FOLDER, gear_coord[1], gear_coord[0])
    self.api_pyautogui.screenshot(name)
    self.api_builtin.print("ROW %d COL %d" % (gear_coord[0], gear_coord[1]))
    img = self.api_cv2.imread(name)
    data = self.card_reader.get_img_data(img, gear_coord, is_blueprint=is_blueprint)
    if not 'base' in data and depth >= ExtractGear.MAX_RECURSE:
      self.api_builtin.print("failed to read too many times, continuing")
      failed.append({'row': gear_coord[0], 'column': gear_coord[1], 'page': page, 'armor_type': armor_type})
      return
    elif not 'base' in data:
      self.api_builtin.print("Failed to read. Re-trying")
      return self.recursive_add_to_index(depth + 1, gear_coord, page, armor_type, is_blueprint, index, failed)
    data['row'] = gear_coord[0]
    data['column'] = gear_coord[1]
    data['page'] = page
    data['armor_type'] = armor_type
    data['is_blueprint'] = is_blueprint
    self.api_builtin.print(str(data))
    index.append(data)
