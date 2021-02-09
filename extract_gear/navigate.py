NUM_TYPES = 7


class Navigate:
  _current_type = 0
  _current_item = 0
  _current_page = 0
  _screen = None
  _all_gear = []

  def __init__(self):
    _current_type = 0
    _current_item = 0
    _current_page = 0
    _screen = Screen()
    _all_gear = []

  def extract_all(self):
    while i < NUM_TYPES:
      break

  def extract_type(self):
    pass

  def extract_page(self):
    self.extract_row()
    move_mouse_down()
    self.extract_row()
    move_mouse_down()
    self.extract_row()
    move_mouse_down()

  def extract_row(self, y):
    self.move_mouse_start()
    self.extract_item()
    self.move_mouse_right()

    self.extract_item()
    self.move_mouse_right()

    self.extract_item()
    self.move_mouse_right()

    self.extract_item()
    self.move_mouse_right()

    self.extract_item()
    self.move_mouse_right()

  def extract_item(self):
    #possible condition for handling if there is an incomplete row/page
    gear = _screen.interpret_stats()
    print(gear)
