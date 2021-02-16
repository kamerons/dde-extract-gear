import timeout_decorator
import unittest
from unittest.mock import Mock, call

from extract_gear.collect_gear_task import CollectGearTask
from folder.folder import Folder

class TestGearCollect(unittest.TestCase):

  @timeout_decorator.timeout(1)
  def test_run(self):
    mock_builtin = Mock()
    mock_pyautogui = Mock()
    collect_gear_task = CollectGearTask(mock_builtin, mock_pyautogui, Mock())
    collect_gear_task.run()
    pyautogui_call_sample = []
    for file_name in ["11_000.png", "53_029.png", "11_030.png"]:
      pyautogui_call_sample.append(call(Folder.PREPROCESS_FOLDER + file_name))
    mock_pyautogui.screenshot.assert_has_calls(pyautogui_call_sample, any_order=True)
