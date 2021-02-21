import os
from datetime import datetime

from extract_gear.cli import Cli
from folder.folder import Folder

# Creates an index file of the form:
# [
#   {
#     'file_name': 'name.png',
#     'type': 'electric',
#     'num': 80
#   },
#   {}...
# ]
class Index:

  NONE = "none"

  STAT_OPTIONS = ['base', 'fire', 'electric', 'poison', 'hero_hp', 'hero_dmg', 'hero_rate', 'hero_speed',
    'offense', 'defense',  'tower_hp', 'tower_dmg', 'tower_rate', 'tower_range', NONE]

  STAT_TYPE_KEY = "type"
  FILE_NAME_KEY = "file_name"
  STAT_VALUE_KEY = "num"

  def __init__(self, args, api_builtin, api_curses, api_cv2, api_json, api_time):
    self.api_builtin = api_builtin
    self.api_cv2 = api_cv2
    self.api_curses = api_curses
    self.api_json = api_json
    self.api_time = api_time

    self.file = args.file
    self.img = []
    self.data_index = []
    self.stage = 0
    self.cli = None
    self.idx = 0


  def run(self):
    self.api_builtin.begin_message("manual index creation")
    self.api_curses.wrapper(self.create_index_manual)


  def create_index_manual(self, stdscr):
    self.api_curses.start_color()
    self.api_curses.use_default_colors()
    for i in range(0, self.api_curses.get_COLORS()):
      self.api_curses.init_pair(i+1, i, -1)
    self.cli = Cli(stdscr, Index.STAT_OPTIONS + ['reshow', 'correct', 'break'], api_curses=self.api_curses)
    if self.file:
      self.set_state_for_resume()

    if self.stage == 0:
      self.cli.print("Beginning index creation.\n", Cli.GREEN)
      self.collect_loop(stdscr)
      self.write_file("collection-complete")
      self.stage = 1
      self.cli.print("Congratulations, index creation is complete!\n", Cli.GREEN)

    self.cli.print("Beginning index correction.  You will now have a chance to correct the data\n", Cli.GREEN)
    self.api_time.sleep(3)

    self.correct_loop(stdscr)
    self.write_file("correction-complete")
    self.cli.print("Congratulations, index correction is complete, this prompt will now exit\n", Cli.GREEN)


  def collect_loop(self, stdscr):
    files = sorted(os.listdir(Folder.STAT_CROP_FOLDER))
    while self.idx <  len(files):
      file_name = files[self.idx]
      self.img = self.api_cv2.imread(Folder.STAT_CROP_FOLDER + file_name)
      data = self.collect_data_item()
      if data == 'correct':
        self.idx = max(self.idx - 1, 0)
        self.data_index = self.data_index[:len(self.data_index)-1]
        continue

      data[Index.FILE_NAME_KEY] = file_name
      self.data_index.append(data)
      self.idx += 1
      if self.idx % 100 == 0:
        self.cli.print("\nComplete %d of %d.  Auto-saving work.\n" % (self.idx, len(files)), Cli.BLUE)
        self.write_file("autosave-")
      elif self.idx % 10 == 0:
        self.cli.print("\nComplete %d of %d\n" % (self.idx, len(files)), Cli.BLUE)

    self.idx = 0


  def collect_data_item(self):
    data = {}
    self.api_cv2.show_img(self.img)
    stat_type = self.get_stat_type()
    if stat_type == 'correct':
      return stat_type

    if stat_type != Index.NONE:
      stat_value = self.get_stat_value()
      if stat_value == 'correct':
        return stat_value
      else:
        data[Index.STAT_VALUE_KEY] = stat_value
    data[Index.STAT_TYPE_KEY] = stat_type

    return data


  def get_stat_type(self):
    stat_type = ""
    while not stat_type in Index.STAT_OPTIONS:
      stat_type = self.cli.input("Enter the type of the stat: Valid options %s\n>" % str(Index.STAT_OPTIONS))
      if self.process_special_cmd(stat_type):
        continue
      #most common typo is extra charater at the end
      elif stat_type[0:len(stat_type) - 1] in Index.STAT_OPTIONS:
        stat_type = stat_type[0:len(stat_type - 1)]
      elif stat_type == 'correct':
        return 'correct'
      elif not stat_type in Index.STAT_OPTIONS:
        self.cli.print("Invalid stat type entered!\n", Cli.RED)
    return stat_type


  def get_stat_value(self):
    integer_value = ""
    while not integer_value.isnumeric():
      integer_value = self.cli.input("Enter the number associated with the stat: \n>")
      if self.process_special_cmd(integer_value):
        continue
      elif integer_value == 'correct':
        return 'correct'
      if not integer_value.isnumeric():
        self.cli.print("Please enter a valid integer\n", Cli.RED)
    return int(integer_value)


  def correct_loop(self, stdscr):
    while self.idx < len(self.data_index):
      correct = " "
      data = self.data_index[self.idx]
      self.img = self.api_cv2.imread(Folder.STAT_CROP_FOLDER + data[Index.FILE_NAME_KEY])
      self.print_stat_data(data)
      self.api_cv2.show_img(self.img)
      while correct != "":
        correct = self.cli.input("Correct the data?\n>")
        if self.process_special_cmd(correct):
          self.print_stat_data(data)
          continue
        elif correct == "correct":
          self.idx = max(self.idx - 1, 0)
          break
        elif correct != "":
          tmp = self.collect_data_item()
          if tmp == 'correct':
            self.idx = max(self.idx - 1, 0)
            break
          else:
            new_data = tmp
            new_data[Index.FILE_NAME_KEY] = data[Index.FILE_NAME_KEY]
            data = new_data
            break

      if correct != 'correct' or tmp != 'correct':
        self.idx += 1
      if self.idx % 50 == 0:
        self.cli.print("\nComplete %d of %d\n" % (self.idx, len(self.data_index)), Cli.BLUE)


  def process_special_cmd(self, input):
    if input == 'reshow':
      self.api_cv2.show_img(self.img)
      return True
    elif input == 'break':
      self.write_file("manual-")
      self.save_progress({'stage': self.stage, 'idx': len(self.data_index)})
      return True
    else:
      return False


  def set_state_for_resume(self):
    with self.api_builtin.open(self.file, "r") as fp:
      self.data_index = self.api_json.load(fp)
      total = len(os.listdir(Folder.STAT_CROP_FOLDER))
      if len(self.data_index) == total:
        self.idx = 0
        self.stage = 1
      else:
        self.idx = len(self.data_index)
        self.cli.print("Resuming collection from %d of %d\n" % (self.idx, total))


  def print_stat_data(self, data):
    stat_type = data[Index.STAT_TYPE_KEY]
    print_str = str(data) + "\n"
    if stat_type in ['electric', 'hero_speed', 'tower_range']:
      self.cli.print(print_str, Cli.BLUE)
    elif stat_type in ['fire', 'hero_hp', 'tower_hp']:
      self.cli.print(print_str, Cli.RED)
    elif stat_type in ['poison', 'hero_rate', 'tower_rate', 'defense']:
      self.cli.print(print_str, Cli.GREEN)
    elif stat_type in ['base', 'hero_dmg', 'tower_dmg', 'offense']:
      self.cli.print(print_str, Cli.BROWN)
    else:
      self.cli.print(print_str)

  def write_file(self, prefix=""):
    with self.api_builtin.open(Folder.STAT_SAVE_FOLDER + prefix + Index.get_time() + '-index.json', 'w') as fp:
      self.api_json.dump(self.data_index, fp)


  def save_progress(self, data):
    self.cli.print("saving progress and exiting")
    with self.api_builtin.open(Folder.PROGRESS_FILE, 'w') as fp:
      self.api_json.dump(data, fp)
      exit()


  def get_time():
    return datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
