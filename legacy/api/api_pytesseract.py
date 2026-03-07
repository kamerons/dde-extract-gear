class ApiPyTesseract:

  def initialize_pytesseract(self):
    from pytesseract import image_to_string as its
    self.image_to_string = its
