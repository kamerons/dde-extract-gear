import keyboard

class ApiKeyboard:

  def wait_for(self, char):
    while True:
      key = keyboard.read_key()
      if key == char or key == '\\':
        break