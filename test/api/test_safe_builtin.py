import unittest

from api.safe_builtin import SafeBuiltIn
from api.safe_builtin import EmptyContextManger

class TestSafeBuiltIn(unittest.TestCase):

  FILE_PATH = "test/api/test.txt"
  CONTENTS = "contents"


  def test_open_readMode(self):
    with open(TestSafeBuiltIn.FILE_PATH, "w") as fp:
      fp.write(TestSafeBuiltIn.CONTENTS)
    safe_builtin = SafeBuiltIn()
    with safe_builtin.open(TestSafeBuiltIn.FILE_PATH, "r") as fp:
      self.assertEqual(TestSafeBuiltIn.CONTENTS, fp.readline())


  def test_open_writeMode(self):
    safe_builtin = SafeBuiltIn()
    fp = safe_builtin.open(TestSafeBuiltIn.FILE_PATH, "w")
    self.assertEqual(type(fp), EmptyContextManger)


  def test_open_writeModeWithSyntax(self):
    safe_builtin = SafeBuiltIn()
    hit = False
    with safe_builtin.open(TestSafeBuiltIn.FILE_PATH, "w") as fp:
      self.assertEqual(type(fp), EmptyContextManger)
      hit = True
    self.assertTrue(hit)
