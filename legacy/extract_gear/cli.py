class Cli:

  RED = 203
  BLUE = 70
  GREEN = 120
  BROWN = 179


  def __init__(self, stdscr, options, api_curses):
    self.api_curses = api_curses
    self.options = options
    self.buffer = ""
    self.stdscr = stdscr
    self.stdscr.scrollok(True)


  def print(self, msg, color=None):
    if color == None:
      self.stdscr.addstr(msg)
    else:
      self.stdscr.addstr(msg, self.api_curses.color_pair(color))
    self.stdscr.refresh()


  def input(self, prompt):
    self.buffer = ""
    ch = ''
    self.stdscr.addstr(prompt)
    while True:
      self.api_curses.flushinp()
      int_char = self.stdscr.getch()
      ch = chr(int_char)
      if ch == '\t':
        self.complete()
      #263 is for tmux users
      elif (ord(ch) == 263 or ord == '\b'):
        if len(self.buffer) > 0:
          self.backspace()
      elif ch == '\n':
        self.stdscr.addstr(ch)
        return self.buffer
      else:
        self.buffer += ch
        self.stdscr.addstr(ch)
    return self.buffer


  def backspace(self):
    self.stdscr.addstr("\b \b")
    self.buffer = self.buffer[:len(self.buffer)-1]


  def complete(self):
    valid_completions = [
        option for option in self.options
        if option.startswith(self.buffer)
      ]
    if len(valid_completions) == 0:
      return
    elif len(valid_completions) == 1:
      stop_point = len(valid_completions[0])
    else:
      stop_point = len(self.buffer)
      for i in range(stop_point, len(valid_completions[0])):
        if valid_completions[0][i] != valid_completions[1][i]:
          stop_point = i
          break
    completion_left = valid_completions[0][len(self.buffer):stop_point]
    self.buffer += completion_left
    self.stdscr.addstr(completion_left)
