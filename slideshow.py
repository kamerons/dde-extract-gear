from preprocess_stat import PreProcessStat
from preprocess_level import PreProcessLevel
from preprocess_set import PreProcessSet
import pytesseract
import cv2
import os
import random
import numpy as np
import json
import sys

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
    preprocessor = PreProcessStat(img)
    img = preprocessor.process_stat()
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
    preprocessor = PreProcessStat(np.array(img, copy=True))
    img2 = preprocessor.process_stat()
    img3 = np.full((56,56*2, 3), (0, 0, 0), dtype=np.uint8)

    for x in range(56):
      for y in range(56):
        img3[y,x] = img[y,x]
        img3[y,x+56] = img2[y,x]
    print("Guess was %s, actual was %s for %s" % (failure['guess'], failure['num'], failure['file_name']))
    cv2.imshow('img', img3)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def confirm_stat():
  for file_name in os.listdir('data/level/process/'):
    img = cv2.imread('data/level/process/' + file_name)
    preprocessor = PreProcessLevel(img)
    img = preprocessor.process_level()
    guess = pytesseract.image_to_string(img).strip()
    print("The guess for this file was: %s" % guess)
    cv2.imshow('img', img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def confirm_set():
  for file_name in os.listdir('data/set/process/'):
    img = cv2.imread('data/set/process/' + file_name)
    preprocessor = PreProcessSet(img)
    img = preprocessor.process_set()
    guess = pytesseract.image_to_string(img).strip()
    print("The guess for this file was: %s" % guess)

if sys.argv[1] == 'stat':
  confirm_color()
elif sys.argv[1] == 'level':
  confirm_stat()
else:
  confirm_set()