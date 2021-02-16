class ApiBuiltIn:

  def __init__(self, args):
    self.safe = args.safe


  def open(self, path, mode):
    if mode == 'r' or not self.safe:
      return open(path, mode)
    else:
      return EmptyContextManger()


  def print(self, msg):
    return print(msg)


  def input(self, prompt):
    return input(prompt)


  def exit(self):
    exit()


# We need this so we can use the with as syntax.  It doesn't need to do anything since we don't actually
# open the file
class EmptyContextManger:
  def __enter__(self):
    return self

  def __exit__(self, exception_type, exception_value, trace_back):
    pass
