import pyautogui
import cv2
from extract_gear.screen import Screen
from extract_gear.extract_training_data import *
import numpy as np
import tkinter
from PIL import Image, ImageTk
import os



# def run():
#   screen = Screen()
#   img = cv2.imread('../../Pictures/row1_column1.png')
#   x = Screen.START_X - 45
#   y = Screen.START_Y - 12

#   add_mark(img, x, y)
#   # for i in range(4):
#   #  add_mark(img, x + Screen.X_STAT_OFFSET * i, y)
#   # for i in range(4):
#   #  add_mark(img, x + Screen.X_STAT_OFFSET * i, y + Screen.Y_STAT_OFFSET)
#   # for i in range(4):
#   #  add_mark(img, x + Screen.X_STAT_OFFSET* i, y + 2*Screen.Y_STAT_OFFSET)

#   cv2.imshow('img',img)
#   cv2.waitKey(0)
#   cv2.destroyAllWindows()


# def add_mark(img, x, y):
#   x_border = 56
#   y_border = 56
#   for x1 in range(x_border * 2 + 1):
#     x2 = x1 - x_border
#     for y1 in range(y_border * 2 + 1):
#       y2 = y1 - y_border
#       if y2 == 0 and x2 == 0:
#         img[round(y2 + y), round(x2 + x)] = [0, 0, 0]
#       else:
#         img[round(y2 + y), round(x2 + x)] = [255, 255, 255]

# def run2():
#   screen = Screen()
#   img = cv2.imread('../../Pictures/row2_column4.png')
#   sampled = screen.interpret_gear(img, 4, 2)
#   for sample in sampled:
#     add_mark(img, sample[0], sample[1])
#   #cv2.imshow('img',img)
#   #cv2.waitKey(0)
#   #cv2.destroyAllWindows()
#   cv2.imwrite('../../Pictures/sampled.png', img)

# def run3():
#   img = cv2.imread('../../Pictures/row1_column1.png')
#   make_img(img, 1, 1)

def run4():
  num = 0
  files = sorted(os.listdir('data/preprocess/'))
  for file_name in files:
    img = cv2.imread('data/preprocess/' + file_name)
    print("Processing " + file_name)
    make_img(img, num, int(file_name[0]), int(file_name[1]))
    num += 10


run4()