import unittest

from api.api_builtin import ApiBuiltIn
from api.api_builtin import EmptyContextManger
from test.util.test_util import Arg

class TestApiBuiltIn(unittest.TestCase):

  FILE_PATH = "test/api/test.txt"
  WRITE_PATH = "test/api/test2.txt"
  CONTENTS = "contents"


  @classmethod
  def setUpClass(cls):
    with open(TestApiBuiltIn.WRITE_PATH, "w") as fp:
      fp.write(TestApiBuiltIn.CONTENTS)


  @classmethod
  def tearDownClass(cls):
    with open(TestApiBuiltIn.WRITE_PATH, "w") as _:
      pass


  def test_open_readMode_safe(self):
    args = Arg(quiet=True, safe=True)
    with open(TestApiBuiltIn.FILE_PATH, "w") as fp:
      fp.write(TestApiBuiltIn.CONTENTS)
    api_builtin = ApiBuiltIn(args)
    with api_builtin.open(TestApiBuiltIn.FILE_PATH, "r") as fp:
      self.assertEqual(TestApiBuiltIn.CONTENTS, fp.readline())


  def test_open_writeMode_safe(self):
    args = Arg(quiet=True, safe=True)
    api_builtin = ApiBuiltIn(args)
    fp = api_builtin.open(TestApiBuiltIn.FILE_PATH, "w")
    self.assertEqual(type(fp), EmptyContextManger)


  def test_open_writeModeWithSyntax_safe(self):
    args = Arg(quiet=True, safe=True)
    api_builtin = ApiBuiltIn(args)
    hit = False
    with api_builtin.open(TestApiBuiltIn.FILE_PATH, "w") as fp:
      self.assertEqual(type(fp), EmptyContextManger)
      hit = True
    self.assertTrue(hit)


  def test_open_writeMode_unsafe(self):
    args = Arg(quiet=True, safe=False)
    api_builtin = ApiBuiltIn(args)
    with api_builtin.open(TestApiBuiltIn.WRITE_PATH, "r") as fp:
      self.assertEqual(TestApiBuiltIn.CONTENTS, fp.readline())

    with api_builtin.open(TestApiBuiltIn.WRITE_PATH, "w") as _:
      pass

    with api_builtin.open(TestApiBuiltIn.WRITE_PATH, "r") as fp:
      self.assertEqual("", fp.readline())
