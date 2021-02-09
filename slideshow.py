import cv2
import os

def run4():
  num = 0
  files = os.listdir('data/preprocess/')
  files.sort()
  to_delete = []
  for file_name in files:
    img = cv2.imread('data/preprocess/' + file_name)
    cv2.imshow('img', img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    delete = input("filename: %s, delete, y or n" % file_name)
    if delete == 'y':
      to_delete += file_name
  print(str(to_delete))

run4()