import timeout_decorator
import unittest
from unittest.mock import Mock, call

from api.safe_builtin import SafeBuiltIn
from api.safe_pyautogui import SafePyAutoGui
from extract_gear.gear_collect import GearCollecter
from folder.folder import Folder

class TestGearCollect(unittest.TestCase):


  @timeout_decorator.timeout(1)
  def test_run(self):
    mock_builtin = Mock()
    mock_pyautogui = Mock()
    gear_collect = GearCollecter(mock_builtin, mock_pyautogui, api_time=Mock())
    gear_collect.run()
    pyautogui_call_sample = []
    for file_name in ["11_000.png", "53_029.png", "11_030.png"]:
      pyautogui_call_sample.append(call(Folder.PREPROCESS_FOLDER + file_name))
    mock_pyautogui.screenshot.assert_has_calls(pyautogui_call_sample, any_order=True)
