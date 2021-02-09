import select
import sys
import curses
import time

red = 203
blue = 70
green = 120
brown = 179

class Cli:
  _options = []
  _buffer = ""
  _stdscr = None

  def __init__(self, stdscr, options):
    self._options = options
    self._buffer = ""
    self._stdscr = stdscr
    self._stdscr.scrollok(True)
    curses.use_default_colors()
    curses.start_color()
    for i in range(0, curses.COLORS):
      curses.init_pair(i + 1, i, -1)

  def cli_print(self, msg, color="NONE"):
    if color == "NONE":
      self.safe_addstr(msg)
    else:
      self.safe_addstr(msg, color)
    self._stdscr.refresh()

  def cli_input(self, prompt):
    self._buffer = ""
    ch = ''
    self.safe_addstr(prompt)
    while True:
      curses.flushinp()
      int_char = self._stdscr.getch()
      ch = chr(int_char)
      if ch == '\t':
        self.complete()
      #263 is for tmux users
      elif (ord(ch) == 263 or ord == '\b'):
        if len(self._buffer) > 0:
          self.backspace()
      elif ch == '\n':
        self.safe_addstr(ch)
        return self._buffer
      else:
        self._buffer += ch
        self.safe_addstr(ch)
    return self._buffer

  def backspace(self):
    self.safe_addstr("\b \b")
    self._buffer = self._buffer[:len(self._buffer)-1]

  def complete(self):
    valid_completions = [
          option for option in self._options
          if option.startswith(self._buffer)
        ]
    if len(valid_completions) == 0:
      return
    elif len(valid_completions) == 1:
      stop_point = len(valid_completions[0])
    else:
      stop_point = len(self._buffer)
      for i in range(stop_point, len(valid_completions[0])):
        if valid_completions[0][i] != valid_completions[1][i]:
          stop_point = i
          break
    completion_left = valid_completions[0][len(self._buffer):stop_point]
    self._buffer += completion_left
    self.safe_addstr(completion_left)

  def safe_addstr(self, message, color=None):
    if color is None:
      self._stdscr.addstr(message)
    else:
      self._stdscr.addstr(message, curses.color_pair(color))




