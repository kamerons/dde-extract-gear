from api.api_cv2 import ApiCv2

class SafeCv2(ApiCv2):

  def __init__(self, quiet_mode=False):
    super().__init__(quiet_mode)


  def imwrite(self, file_name, img):
    print("Fake writing image to %s" % file_name)
