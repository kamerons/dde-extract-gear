import timeout_decorator
import unittest
from unittest.mock import Mock, call

from extract_gear.collect_gear_task import CollectGearTask
from folder.folder import Folder
from test.util.test_util import TestUtil

class TestGearCollect(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    TestGearCollect.ORIGINAL_COLLECTGEARTASK_ATTRIBUTES = TestUtil.get_class_attributes(CollectGearTask)


  @classmethod
  def tearDownClass(cls):
    TestUtil.restore_class_attributes(CollectGearTask, TestGearCollect.ORIGINAL_COLLECTGEARTASK_ATTRIBUTES)


  @timeout_decorator.timeout(1)
  def test_run_fileNamesCorrect(self):
    CollectGearTask.NUM_ROWS = 2
    CollectGearTask.NUM_COLUMNS = 3
    CollectGearTask.MAX_GEAR = 6
    mock_builtin = Mock()
    mock_pyautogui = Mock()
    collect_gear_task = CollectGearTask(mock_builtin, mock_pyautogui, Mock())
    collect_gear_task.run()
    pyautogui_call_sample = []
    for file_name in ["11_000.png", "21_001.png", "31_002.png", "12_003.png", "22_004.png", "32_005.png"]:
      pyautogui_call_sample.append(call(Folder.PREPROCESS_FOLDER + file_name))
    mock_pyautogui.screenshot.assert_has_calls(pyautogui_call_sample)
