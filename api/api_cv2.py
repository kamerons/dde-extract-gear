import cv2

class ApiCv2:

  def imread(self, file_name):
    return cv2.imread(file_name)


  def imwrite(self, file_name, img):
    return cv2.imwrite(file_name, img)


  def imshow(self, window_name, img):
    return cv2.imshow(window_name, img)


  def waitKey(self, wait_time):
    return cv2.waitKey(wait_time)


  def destroyAllWindows(self):
    return cv2.destroyAllWindows()


  def filter2D(self, img, ddepth, kernel):
    return cv2.filter2D(img, ddepth, kernel)

  def show_img(self, img, window_name="img", waitKey=0):
    cv2.imshow(window_name, img)
    cv2.waitKey(waitKey)
    cv2.destroyAllWindows()
