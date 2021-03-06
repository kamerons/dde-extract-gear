import cv2

class ApiCv2:

  def __init__(self, args, api_builtin):
    self.show_images = not args.quiet
    self.safe = args.safe
    self.quiet = args.quiet
    self.api_builtin = api_builtin


  def imread(self, file_name):
    return cv2.imread(file_name)


  def imwrite(self, file_name, img):
    if not self.safe:
      return cv2.imwrite(file_name, img)


  def cvtColor(self, image, color):
    return cv2.cvtColor(image, color)


  def COLOR_BGR2GRAY(self):
    return cv2.COLOR_BGR2GRAY


  def calcHist(self, images, channels, mask, histSize, ranges):
    return cv2.calcHist(images, channels, mask, histSize, ranges)


  def show_img(self, img, window_name="img", waitKey=0):
    if self.show_images:
      cv2.imshow(window_name, img)
      cv2.waitKey(waitKey)
      cv2.destroyAllWindows()
