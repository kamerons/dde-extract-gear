import cv2
import os
import json
import time
import curses
from cli import Cli, red, blue, green, brown
from datetime import datetime
import sys

# [
#   {
#     'file_name': 'name.png',
#     'type': 'electric',
#     'num': 80
#   },
#   {}...
# ]

armor_types = ['electric', 'fire', 'poison', 'base', 'hero_dmg', 'hero_hp', 'hero_speed',
    'hero_rate', 'offense', 'defense', 'tower_dmg', 'tower_rate', 'tower_hp', 'tower_range', 'none']
dir = 'data/stat/'
class Index:

  img = []
  index = []
  stage = 0
  cli = None

  def get_time():
    return datetime.now().strftime("%d-%m-%Y_%H-%M-%S")

  def __init__(self):
    self.img = []
    self.index = []
    self.stage = 0
    self.cli = None
    self.start_index = 0

  def process_special_cmd(self, input):
    if input == 'reshow':
      self.show_img()
      return True
    elif input == 'break':
      self.write_file("manual-")
      self.save_progress({'stage': self.stage, 'idx': len(self.index)})
      return True
    else:
      return False

  def show_img(self):
    cv2.imshow('img', self.img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

  def collect_data(self):
    data = {}
    self.show_img()
    set_type = ""
    while not set_type in armor_types:
      set_type = self.cli.cli_input("Enter the type of the stat: Valid options %s\n>" % str(armor_types))
      special = self.process_special_cmd(set_type)
      if special:
        continue
      #most common typo is extra charater at the end
      elif set_type[0:len(set_type) - 1] in armor_types:
        set_type = set_type[0:len(set_type - 1)]
      elif set_type == 'correct':
        return 'correct'
      elif not set_type in armor_types:
        self.cli.cli_print("Invalid stat type entered!\n", red)


    data['type'] = set_type
    if set_type != 'none':
      integer_value = ""
      is_not_int = True
      while is_not_int:
        integer_value = self.cli.cli_input("Enter the number associated with the stat: \n>")
        special = self.process_special_cmd(integer_value)
        if special:
          continue
        elif integer_value == 'correct':
          return 'correct'
        try:
          int(integer_value)
          is_not_int = False
        except:
          self.cli.cli_print("Please enter a valid integer\n", red)
      data['num'] = int(integer_value)
    return data

  def write_file(self, prefix=""):
    with open(dir + "save/" + prefix + Index.get_time() + '-index.json', 'w') as fp:
      json.dump(self.index, fp)

  def save_progress(self, data):
    self.cli.cli_print("saving progress and exiting")
    with open(dir + 'save/progress.json', 'w') as fp:
      json.dump(data, fp)
      exit()

  def collect_loop(self, stdscr):
    files = sorted(os.listdir(dir + 'process/'))
    i = self.start_index
    self.start_index = 0
    while i <  len(files):
      file_name = files[i]
      data = {}
      self.img = cv2.imread(dir + 'process/' + file_name)
      tmp = self.collect_data()
      if tmp == 'correct':
        i = i -1 if i - 1 >= 0 else 0
        self.index = self.index[:len(self.index)-1]
        continue
      else:
        data = tmp
      data['file_name'] = file_name
      self.index.append(data)
      i += 1
      if i % 100 == 0:
        self.cli.cli_print("\nComplete %d of %d.  Auto-saving work.\n" % (i, len(files)))
        self.write_file("autosave-")
      elif i % 10 == 0:
        self.cli.cli_print("\nComplete %d of %d\n" % (i, len(files)))

  def correct_loop(self, stdscr):
    i = self.start_index
    self.start_index = 0
    while i < len(self.index):
      correct = " "
      data = self.index[i]
      self.img = cv2.imread(dir + 'process/' + data['file_name'])
      while correct != "":
        type_thing = data['type']
        if type_thing in ['electric', 'hero_speed', 'tower_range']:
          self.cli.cli_print(str(data), blue)
        elif type_thing in ['fire', 'hero_hp', 'tower_hp']:
          self.cli.cli_print(str(data), red)
        elif type_thing in ['poison', 'hero_rate', 'tower_rate', 'defense']:
          self.cli.cli_print(str(data), green)
        elif type_thing in ['base', 'hero_dmg', 'tower_dmg', 'offense']:
          self.cli.cli_print(str(data), brown)
        else:
          self.cli.cli_print(str(data))
        self.cli.cli_print("\n")
        self.show_img()
        correct = self.cli.cli_input("Correct the data?\n>")
        if correct == 'reshow':
          continue
        elif correct == 'break':
          self.write_file("manual-")
          self.save_progress({'stage': self.stage, 'idx': len(self.index)})
        elif correct != "":
          tmp = self.collect_data()
          if tmp == 'correct':
            i = i -1 if i - 1 >= 0 else 0
            break
          else:
            new_data = tmp
            new_data['file_name'] = data['file_name']
            data = new_data
      if i % 50 == 0:
        self.cli.cli_print("\nComplete %d of %d\n" % (i, len(files)))
      i += 1
    self.write_file("correction-complete")
    self.cli.cli_print("Congratulations, data correction is complete, this prompt will now exit\n")
    time.sleep(3)

  def main_loop(self, stdscr):
    self.cli = Cli(stdscr, armor_types + ['reshow', 'correct', 'break'])
    if len(sys.argv) == 2:
      inputfile = sys.argv[1]
      with open(inputfile) as fp:
        self.index = json.load(fp)
        total = len(os.listdir(dir + 'process/'))
        if len(self.index) == total:
          self.stage = 1
        else:
          self.start_index = len(self.index)
          self.cli.cli_print("resuming collection from %d of %d\n" % (self.start_index, total))
    if self.stage == 0:
      self.collect_loop(stdscr)
      self.write_file("collection-complete")
      self.stage = 1

    self.cli.cli_print("Congratulations, data entry is complete, you will now have a chance to correct the data\n")
    time.sleep(3)

    self.correct_loop(stdscr)

index_instance = Index()
curses.wrapper(index_instance.main_loop)

# def run(stdscr):
#   curses.use_default_colors()
#   curses.start_color()
#   for i in range(0, curses.COLORS):
#       curses.init_pair(i + 1, i, -1)
#   try:
#       for i in range(0, 255):
#           stdscr.addstr(str(i) + " ", curses.color_pair(i))
#   except curses.ERR:
#       # End of screen reached
#       pass
#   stdscr.getch()

# curses.wrapper(run)