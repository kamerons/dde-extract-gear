from preprocess import PreProcess
import cv2
import os
import random
import numpy as np

def confirm_color():
  lst = os.listdir('data/process/')
  random.shuffle(lst)
  for file_name in lst:
    img = cv2.imread('data/process/' + file_name)
    preprocessor = PreProcess(np.array(img, copy=True))
    img2 = preprocessor.process()
    img3 = np.full((56,56*2, 3), (0, 0, 0), dtype=np.uint8)
    for x in range(56):
      for y in range(56):
        img3[y,x] = img[y,x]
        img3[y,x+56] = img2[y,x]
    cv2.imshow('img', img3)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

confirm_color()