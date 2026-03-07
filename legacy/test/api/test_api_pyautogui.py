import json
import unittest
from unittest.mock import Mock

from api.api_pyautogui import ApiPyAutoGui
from test.util.test_util import Arg

class TestApiJson(unittest.TestCase):


  def test_screenshot_safeMode(self):
    mock_apibuiltin = Mock()
    args = Arg(quiet=True, safe=True)
    api_pyautogui = ApiPyAutoGui(args, mock_apibuiltin)
    file_path = "test/api/should_not_write.png"
    api_pyautogui.screenshot(file_path)
    mock_apibuiltin.print.assert_called_once_with(ApiPyAutoGui.PRINT_FORMAT_STR % file_path)
