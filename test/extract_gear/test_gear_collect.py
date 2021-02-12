import timeout_decorator
import unittest
from unittest.mock import Mock, call

from api.safe_builtin import SafeBuiltIn
from api.safe_pyautogui import SafePyAutoGui
from extract_gear.gear_collect import GearCollecter

class TestGearCollect(unittest.TestCase):


  @timeout_decorator.timeout(1)
  def test_run(self):
    mock_builtin = Mock()
    mock_pyautogui = Mock()
    gear_collect = GearCollecter(mock_builtin, mock_pyautogui, api_time=Mock())
    gear_collect.run()
    pyautogui_call_sample = [call("data/preprocess/11_000.png"),
      call("data/preprocess/53_029.png"), call("data/preprocess/11_030.png")]
    mock_pyautogui.screenshot.assert_has_calls(pyautogui_call_sample, any_order=True)
