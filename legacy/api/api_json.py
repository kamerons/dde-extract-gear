import json

class ApiJson():

  def __init__(self, args):
    self.safe = args.safe


  def load(self, path):
    return json.load(path)


  def dump(self, data, fp):
    if self.safe:
      return None
    return json.dump(data, fp)
