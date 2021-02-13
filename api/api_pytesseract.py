import pytesseract

class ApiPyTesseract:

  def image_to_string(self, img):
    return pytesseract.image_to_string(img)
