from folder.folder import Folder

class CollectGearTask:

  MAX_GEAR = 1000
  NUM_ROWS = 3
  NUM_COLUMNS = 5

  def __init__(self, api_builtin, api_pyautogui, api_time):
    self.api_builtin = api_builtin
    self.api_pyautogui = api_pyautogui
    self.api_time = api_time


  def countdown(self, x, printX):
    while x > 0:
      if printX:
        self.api_builtin.print(x)
      x -= 1
      self.api_time.sleep(1)


  def run(self):
    self.api_builtin.print("press enter when ready, you will have 10 seconds to prepare")
    self.api_builtin.input("")
    self.countdown(10, True)
    i = 0
    #at most 1000 pieces of gear
    while i < CollectGearTask.MAX_GEAR:
      for row in range(1, CollectGearTask.NUM_ROWS + 1):
        for column in range(1, CollectGearTask.NUM_COLUMNS + 1):
          name = '%s%d%d_%03d.png' % (Folder.PREPROCESS_FOLDER, column, row, i)
          self.api_pyautogui.screenshot(name)
          self.api_builtin.print("Took screenshot: %s" % name)
          if row == 3 and column == 5:
            self.api_builtin.print("Switch to the next page, you will have 10 seconds")
            self.countdown(10, True)
          else:
            self.countdown(4, False)
          i += 1
          if i == CollectGearTask.MAX_GEAR:
            return
