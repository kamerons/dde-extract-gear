import cv2
from extract_gear.extract_training_data import *
import os
import sys

def extract_stat_data():
  num = 0
  files = sorted(os.listdir('data/preprocess/'))
  for file_name in files:
    img = cv2.imread('data/preprocess/' + file_name)
    print("Processing " + file_name)
    make_stat_img(img, num, int(file_name[0]), int(file_name[1]))
    num += 10

def extract_level_data():
  num = 0
  files = sorted(os.listdir('data/preprocess/'))
  for file_name in files:
    img = cv2.imread('data/preprocess/' + file_name)
    print("Processing " + file_name)
    make_level_img(img, num, int(file_name[0]), int(file_name[1]))
    num += 1

flag = sys.argv[1]
if sys.argv[1] == "stat":
  extract_stat_data()
elif flag == "level":
  extract_level_data()
