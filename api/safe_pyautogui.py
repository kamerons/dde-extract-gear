from api.api_pyautogui import ApiPyAutoGui

class SafePyAutoGui(ApiPyAutoGui):

  def screenshot(self, file_location):
    print("would write to location %s" % file_location)
