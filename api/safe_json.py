from api.api_json import ApiJson

class SafeJson(ApiJson):

  def dump(self, data, fp):
    return None
