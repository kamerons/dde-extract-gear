import unittest
from unittest.mock import Mock
import timeout_decorator
import os

from api.api_cv2 import ApiCv2
from test.util.test_util import Arg

class TestApiCv2(unittest.TestCase):

  @timeout_decorator.timeout(1)
  def test_safeMode(self):
    arg = Arg(quiet=True, safe=True)
    api_cv2 = ApiCv2(arg, Mock())
    should_fail = False
    try:
      api_cv2.imwrite("test/api/test.txt", [])
    except:
      should_fail = True
    if should_fail:
      self.fail("Should not throw exception when attempting to write file in safe mode")
