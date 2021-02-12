import json

class ApiJson():

  def load(self, path):
    return json.load(path)


  def dump(self, data, fp):
    return json.dump(data, fp)
