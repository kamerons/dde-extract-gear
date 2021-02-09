
import cv2
X_STAT_OFFSET = 60
Y_STAT_OFFSET = 87

X_GEAR_OFFSET = 174
Y_GEAR_OFFSET = 177

X_START = 390
Y_START = 375

SIZE = 56

def make_img(img, index, x, y):
  x_coord = X_START + (x-1) * X_GEAR_OFFSET
  y_coord = Y_START + (y-1) * Y_GEAR_OFFSET

  orig_x_coord = x_coord
  for i in range(4):
    tmp_img = img[y_coord:y_coord + SIZE, x_coord:x_coord + SIZE]
    cv2.imshow('img', tmp_img)
    cv2.imwrite('data/process/defense_%d_%d.png' % (index, i), tmp_img)
    x_coord += X_STAT_OFFSET

  x_coord = orig_x_coord
  y_coord += Y_STAT_OFFSET

  for i in range(6):
    tmp_img = img[y_coord:y_coord + SIZE, x_coord:x_coord + SIZE]
    cv2.imwrite('data/process/row1_%d_%d.png' % (index, i + 4), tmp_img)
    x_coord += X_STAT_OFFSET

  x_coord = orig_x_coord
  y_coord += Y_STAT_OFFSET
  for i in range(4):
    tmp_img = img[y_coord:y_coord + SIZE, x_coord:x_coord + SIZE]
    cv2.imwrite('data/process/row2_%d_%d.png' % (index, i + 10), tmp_img)
    x_coord += X_STAT_OFFSET