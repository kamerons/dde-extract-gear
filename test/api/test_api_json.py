import json
import unittest

from api.api_json import ApiJson
from test.util.test_util import Arg

class TestApiJson(unittest.TestCase):


  def test_dump_safeMode(self):
    args = Arg(quiet=True, safe=True)
    api_json = ApiJson(args)
    self.assertEqual(None, api_json.dump({}, None))


  def test_dump_unsafeMode(self):
    args = Arg(quiet=True, safe=False)
    api_json = ApiJson(args)
    should_fail = True
    try:
      api_json.dump({}, None)
    except:
      should_fail = False
    if should_fail:
      self.fail("Should throw exception when writing data in unsafe mode")

