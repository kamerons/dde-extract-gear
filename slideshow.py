from preprocess import PreProcess
import pytesseract
import cv2
import os
import random
import numpy as np
import json


dir = 'data/stat/'
def confirm_color():
  index = []
  with open(dir + "save/correction-complete09-02-2021_02-57-04-index.json") as fp:
    index = json.load(fp)
  failed = []
  total = 0
  for data in index:
    if data['type'] == "none":
      continue
    total += 1
    if total % 100 == 0:
      print("Complete %d of at most %d" % (total, len(index)))
    img = cv2.imread(dir + 'process/' + data['file_name'])
    preprocessor = PreProcess(img)
    img = preprocessor.process()
    guess = pytesseract.image_to_string(img).strip()
    guess = "".join(e for e in guess if e.isalnum())
    if guess != str(data['num']):
      fail_data = data.copy()
      fail_data['guess'] = guess
      failed.append(fail_data)

  num_success = total - len(failed)
  print("Accuracy: %d/%d or %f" % (num_success, total, float(num_success) / total))
  print("showing failed images")
  for failure in failed:
    img = cv2.imread(dir + 'stat/process/' + failure['file_name'])
    preprocessor = PreProcess(np.array(img, copy=True))
    img2 = preprocessor.process()
    img3 = np.full((56,56*2, 3), (0, 0, 0), dtype=np.uint8)

    for x in range(56):
      for y in range(56):
        img3[y,x] = img[y,x]
        img3[y,x+56] = img2[y,x]
    print("Guess was %s, actual was %s for %s" % (failure['guess'], failure['num'], failure['file_name']))
    cv2.imshow('img', img3)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

confirm_color()
