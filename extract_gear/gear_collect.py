from api.api_pyautogui import ApiPyAutoGui
from api.api_time import ApiTime

class GearCollecter:

  def __init__(self, api_pyautogui=None, api_time=None):
    self.api_pyautogui = api_pyautogui if api_pyautogui else ApiPyAutoGui()
    self.api_time = api_time if api_time else ApiTime()


  def countdown(self, x, printX):
    while x > 0:
      if printX:
        print(x)
      x -= 1
      self.api_time.sleep(1)


  def run(self):
    print("press enter when ready, you will have 10 seconds to prepare")
    input()
    self.countdown(10, True)
    dir = 'data/preprocess/'
    i = 0
    while True:
      for row in range(1, 4):
        for column in range(1, 6):
          name = '%s%d%d_%03d.png' % (dir, column, row, i)
          self.api_pyautogui.screenshot(name)
          print("Took screenshot: %s" % name)
          if row == 3 and column == 5:
            print("Switch to the next page, you will have 10 seconds")
            self.countdown(10, True)
          else:
            self.countdown(4, False)
          i += 1
