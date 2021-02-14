from api.api_time import ApiTime
from api.safe_builtin import SafeBuiltIn
from api.safe_cv2 import SafeCv2
from api.safe_json import SafeJson
from api.safe_pyautogui import SafePyAutoGui

from extract_gear.card_reader import CardReader

from folder.folder import Folder

class ExtractGear:

  ARMOR_TYPES = ["shoulder_pad", "mask", "hat", "greaves", "shield", "bracer", "belt"]


  def __init__(self, api_builtin, api_cv2=None, api_pyautogui=None, api_json=None, api_time=None):
    self.api_builtin = api_builtin if api_builtin else SafeBuiltIn()
    self.api_cv2 = api_cv2 if api_cv2 else SafeCv2()
    self.api_pyautogui = api_pyautogui if api_pyautogui else SafePyAutoGui()
    self.api_json = api_json if api_json else SafeJson()
    self.api_time = api_time if api_time else ApiTime()
    self.card_reader = CardReader()


  def countdown(self, x, printX):
    while x > 0:
      if printX:
        self.api_builtin.print(x)
      x -= 1
      self.api_time.sleep(1)


  def run(self):
    start_row = int(self.api_builtin.input("enter the starting row, typically 1\n>"))
    start_col = int(self.api_builtin.input("enter the starting column, typically 3\n>"))
    for armor_type in ExtractGear.ARMOR_TYPES:
      self.api_builtin.input(
        "Beginning collection for %s.  Press enter when ready." % armor_type)
      num_pages = int(self.api_builtin.input("enter the number of FULL pages\n>"))
      self.api_builtin.print("Beginning collection. you will have 10 seconds")
      self.countdown(10, True)
      index = []
      for page in range(1, num_pages + 1):
        for row in range(1, 4):
          for column in range(1, 6):
            if page == 1 and (row < start_row) or (row == start_row and column < start_col):
              continue
            name = '%s%d%d.png' % (Folder.TMP_FOLDER, column, row)
            self.api_pyautogui.screenshot(name)
            print("COL %d ROW %d" % (column, row))
            img = self.api_cv2.imread(name)
            data = self.card_reader.get_img_data(img, (row, column))
            print(str(data))
            index.append(data)
            if row == 3 and column == 5:
              self.api_builtin.print("Switch to the next page, you will have 10 seconds")
              self.countdown(10, True)
            else:
              self.countdown(4, False)
      with self.api_builtin.open(Folder.COLLECT_FILE) as fp:
        self.api_json.dump(index, fp)
