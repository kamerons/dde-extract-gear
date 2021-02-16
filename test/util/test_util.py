class TestUtil:

  def get_class_attributes(clz):
    return [(attr, getattr(clz, attr)) for attr in dir(clz) if not callable(getattr(clz, attr))
      and not attr.startswith("__")]


  def restore_class_attributes(clz, attributes):
    for attribute_name, attribute_value in attributes:
      setattr(clz, attribute_name, attribute_value)


class Arg:

  def __init__(self, quiet=True, safe=True, command=[], file=""):
    self.quiet = quiet
    self.safe = safe
    self.command = command
    self.file = file
