from extract_gear.armor_visitor import ArmorVisitor

from folder.folder import Folder


class CollectGearTask:

  def __init__(self, args, api_builtin, api_keyboard, api_pyautogui, api_time):
    self.api_builtin = api_builtin
    self.api_keyboard = api_keyboard
    self.api_pyautogui = api_pyautogui
    self.api_time = api_time
    self.sub_task = args.command[1]
    self.i = 0


  def run(self):
    self.api_builtin.begin_message("gear collection")
    self.collect_gear()


  def collect_gear(self):
    if self.sub_task == "blueprint":
      num_col = 4
      num_row = 6
      folder = Folder.BLUEPRINT_FOLDER
      self.api_builtin.print("Collecting data for blueprint. Press enter when ready")
    else:
      num_col = 5
      num_row = 3
      folder = Folder.PREPROCESS_FOLDER
      self.api_builtin.print("Collecting data for standard gear. Press enter when ready")

    start_pos = self.api_builtin.input_safe_int("Enter the starting column (1-5), typically 3\n> ")
    final_page = self.api_builtin.input_safe_int("Enter the number of pages\n> ")
    last_page_start_row = self.api_builtin.input_safe_int("Enter the starting row on the last page\n> ")
    last_page_end_row = self.api_builtin.input_safe_int("Enter the last row on the last page\n> ")
    last_page_end_col = self.api_builtin.input_safe_int("Enter the last column on the last page\n> ")

    armor_iterator = ArmorVisitor(final_page, start_pos, 1, last_page_start_row, last_page_end_col,
      last_page_end_row, num_col_page=num_col, num_row_page=num_row)
    self.api_builtin.print("Preparing to collect data for %s. Press o then p to take a screenshot")

    armor_iterator.iterate(self.get_screenshot_fn(folder))


  def get_screenshot_fn(self, folder):
    def screenshot_callback(gear_coord, page, index):
      # small hack TODO add a debouncer
      self.api_keyboard.wait_for('o')
      self.api_keyboard.wait_for('p')
      name = '%s%d%d_%03d.png' % (Folder.BLUEPRINT_FOLDER, gear_coord[1], gear_coord[0], self.i)
      self.api_pyautogui.screenshot(name)
      if not self.api_pyautogui.safe:
        self.api_builtin.print("Took screenshot: %s" % name)
      self.i += 1
    return screenshot_callback
