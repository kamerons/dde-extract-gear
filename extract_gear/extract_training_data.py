
import cv2
X_STAT_OFFSET = 60
Y_STAT_OFFSET = 87

X_GEAR_OFFSET = 174
Y_GEAR_OFFSET = 177

X_LEVEL_OFFSET = 180
Y_LEVEL_OFFSET = 268

X_SET_OFFSET = 100
Y_SET_OFFSET = -100

LEVEL_WIDTH = 70
LEVEL_HEIGHT = 30

SET_WIDTH = 140
SET_HEIGHT = 20

LEVEL_ONE_STAT_ROW_OFFSET = 88

X_START = 390
Y_START = 375

STAT_SIZE = 56

dir = 'data/'
def make_stat_img(img, index, x, y):
  x_coord = X_START + (x-1) * X_GEAR_OFFSET
  y_coord = Y_START + (y-1) * Y_GEAR_OFFSET

  orig_x_coord = x_coord
  for i in range(4):
    tmp_img = img[y_coord:y_coord + STAT_SIZE, x_coord:x_coord + STAT_SIZE]
    cv2.imshow('img', tmp_img)
    cv2.imwrite(dir + 'stat/process/defense_%d_%d.png' % (index, i), tmp_img)
    x_coord += X_STAT_OFFSET

  x_coord = orig_x_coord
  y_coord += Y_STAT_OFFSET

  for i in range(6):
    tmp_img = img[y_coord:y_coord + STAT_SIZE, x_coord:x_coord + STAT_SIZE]
    cv2.imwrite(dir + 'stat/process/row1_%d_%d.png' % (index, i + 4), tmp_img)
    x_coord += X_STAT_OFFSET

  x_coord = orig_x_coord
  y_coord += Y_STAT_OFFSET
  for i in range(4):
    tmp_img = img[y_coord:y_coord + STAT_SIZE, x_coord:x_coord + STAT_SIZE]
    cv2.imwrite(dir + 'stat/process/row2_%d_%d.png' % (index, i + 10), tmp_img)
    x_coord += X_STAT_OFFSET

def make_level_img(img, index, x, y):
  x_coord = X_START + (x-1) * X_GEAR_OFFSET + X_LEVEL_OFFSET
  y_coord = Y_START + (y-1) * Y_GEAR_OFFSET + Y_LEVEL_OFFSET

  tmp_img = img[y_coord:y_coord + LEVEL_HEIGHT, x_coord:x_coord + LEVEL_WIDTH]
  cv2.imshow('img', tmp_img)
  cv2.waitKey(0)
  cv2.destroyAllWindows()
  q = input("Use other input?")
  if q != "":
    if q == "u":
      tmp_img = img[y_coord - LEVEL_ONE_STAT_ROW_OFFSET:y_coord - LEVEL_ONE_STAT_ROW_OFFSET + LEVEL_HEIGHT, x_coord:x_coord + LEVEL_WIDTH]
    elif q == "r":
      tmp_img = img[y_coord:y_coord + LEVEL_HEIGHT, x_coord + STAT_SIZE:x_coord + STAT_SIZE+ LEVEL_WIDTH]
    cv2.imshow('img', tmp_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    "If it's still wrong write some code to correct it yourself!"
  cv2.imwrite(dir + 'level/process/%d.png' % index, tmp_img)

def get_set_img(img, y, x):
  x_coord = X_START + (x-1) * X_GEAR_OFFSET + X_SET_OFFSET
  y_coord = Y_START + (y-1) * Y_GEAR_OFFSET + Y_SET_OFFSET

  return img[y_coord:y_coord + SET_HEIGHT, x_coord:x_coord + SET_WIDTH]


def make_set_img(img, index, x, y):
  tmp_img = get_set_img(img, y, x)
  cv2.waitKey(0)
  cv2.destroyAllWindows()
  cv2.imwrite(dir + 'set/process/%d.png' % index, tmp_img)