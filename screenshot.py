import pyautogui
from time import sleep

def countdown(x, printX):
  while x > 0:
    if printX:
      print(x)
    x -= 1
    sleep(1)

print("press enter when ready, you will have 10 seconds to prepare")

unused = input()
countdown(10, True)

i = 0
while True:
  for row in range(1, 4):
    for column in range(1, 6):
      name = 'data/preprocess/%d%d_%03d.png' % (column, row, i)
      pyautogui.screenshot(name)
      print("Took screenshot: %s" % name)
      if row == 3 and column == 5:
        print("Switch to the next page, you will have 10 seconds")
        countdown(10, True)
      else:
        countdown(4, False)
      i += 1


