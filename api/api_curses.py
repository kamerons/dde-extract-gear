import curses

class ApiCurses:

  def use_default_colors(self):
    return curses.use_default_colors()


  def init_pair(self, pair_number, fg, bg):
    return curses.init_pair(pair_number, fg, bg)


  def start_color(self):
    return curses.start_color()


  def flushinp(self):
    return curses.flushinp()


  def color_pair(self, color):
    return curses.color_pair(color)


  def get_COLORS(self):
    return curses.COLORS


  def wrapper(self, method):
    return curses.wrapper(method)
