import unittest

import api
import extract_gear
import train

from extract_gear.class_repository import Configs, TaskProvider, Internal2, Internal3
from extract_gear.card_reader import CardReader
from extract_gear.image_splitter import ImageSplitter
from extract_gear.preprocess_factory import PreprocessFactory
from extract_gear.set_type_reader import SetTypeReader
from extract_gear.stat_group_reader import StatGroupReader

from train.image_scaler import ImageScaler

from test.util.test_util import TestUtil, Arg

class TestClassRepository(unittest.TestCase):

  expected_instances = {
    "api_builtin": api.api_builtin.ApiBuiltIn,
    "api_curses": api.api_curses.ApiCurses,
    "api_cv2": api.api_cv2.ApiCv2,
    "api_fuzzywuzzy": api.api_fuzzywuzzy.ApiFuzzyWuzzy,
    "api_json": api.api_json.ApiJson,
    "api_keyboard": api.api_keyboard.ApiKeyboard,
    "api_pyautogui": api.api_pyautogui.ApiPyAutoGui,
    "api_pytesseract": api.api_pytesseract.ApiPyTesseract,
    "api_random": api.api_random.ApiRandom,
    "api_tensorflow": api.api_tensorflow.ApiTensorflow,
    "api_time": api.api_time.ApiTime,
    "card_reader": CardReader,
    "image_splitter": ImageSplitter,
    "perprocess_factory": PreprocessFactory,
    "set_type_reader": SetTypeReader,
    "stat_group_reader": StatGroupReader,
    "safe": bool
  }


  @classmethod
  def setUpClass(cls):
    TestClassRepository.expected_args = Arg(quiet=True, safe=True,
      command=["unused", "subtask"], file="file")
    Configs.config.override(TestClassRepository.expected_args)


  def test_setTypeReader(self):
    set_type_reader = Internal2.set_type_reader()
    self.assert_obj_has_attributes_of_correct_type(set_type_reader)


  def test_statGroupReader(self):
    stat_group_reader = Internal2.stat_group_reader()
    self.assert_obj_has_attributes_of_correct_type(stat_group_reader)


  def test_cardReader(self):
    card_reader = Internal3.card_reader()
    self.assert_obj_has_attributes_of_correct_type(card_reader)


  def test_imageSplitTask(self):
    image_split_task = TaskProvider.image_split_task()
    self.assertEqual("subtask", image_split_task.sub_task)
    self.assert_obj_has_attributes_of_correct_type(image_split_task)


  def test_modelEvaluatorTask(self):
    model_evaluator_task = TaskProvider.model_evaluator_task()
    self.assert_obj_has_attributes_of_correct_type(model_evaluator_task)


  def test_collectGearTask(self):
    collect_gear_task = TaskProvider.collect_gear_task()
    self.assert_obj_has_attributes_of_correct_type(collect_gear_task)


  def test_indexTask(self):
    index_task = TaskProvider.index_task()
    self.assertEqual("file", index_task.file)
    self.assert_obj_has_attributes_of_correct_type(index_task)


  def test_trainStatValueTask(self):
    train_stat_value_task = TaskProvider.train_stat_value_task()
    self.assert_obj_has_attributes_of_correct_type(train_stat_value_task)


  def test_trainStatTypeTask(self):
    train_stat_type_task = TaskProvider.train_stat_type_task()
    self.assert_obj_has_attributes_of_correct_type(train_stat_type_task)


  def test_extractGear(self):
    extract_gear = TaskProvider.extract_gear()
    self.assert_obj_has_attributes_of_correct_type(extract_gear)


  def assert_obj_has_attributes_of_correct_type(self, obj):
    attributes = TestUtil.get_class_attributes(obj)
    for attribute_name, attribute_value in attributes:
      if attribute_name in TestClassRepository.expected_instances:
        self.assertEqual(type(attribute_value), TestClassRepository.expected_instances[attribute_name])
