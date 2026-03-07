import pyautogui

class ApiPyAutoGui:

  PRINT_FORMAT_STR = "Would write to %s"

  def __init__(self, args, api_builtin):
    self.safe = args.safe
    self.api_builtin = api_builtin


  def screenshot(self, file_location):
    if self.safe:
      self.api_builtin.print(ApiPyAutoGui.PRINT_FORMAT_STR % file_location)
    else:
      return pyautogui.screenshot(file_location)
