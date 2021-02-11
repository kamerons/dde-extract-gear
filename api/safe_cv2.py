from api.api_cv2 import ApiCv2

class SafeCv2(ApiCv2):

  def imwrite(self, file_name, img):
    print("Fake writing image to %s" % file_name)