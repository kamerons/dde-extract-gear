from api.api_builtin import ApiBuiltIn

class SafeBuiltIn(ApiBuiltIn):

  def open(self, path, mode):
    if mode == 'r':
      return open(path, mode)
    else:
      return EmptyContextManger()


# We need this so we can use the with as syntax.  It doesn't need to do anything since we don't actually
# open the file
class EmptyContextManger:
  def __enter__(self):
    pass

  def __exit__(self, a, b, c):
    pass
