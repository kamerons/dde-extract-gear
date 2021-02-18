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

from test.util.test_util import Arg

class TestClassRepository(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    TestClassRepository.expected_args = Arg(quiet=True, safe=True,
      command=["unused", "subtask"], file="file")
    Configs.config.override(TestClassRepository.expected_args)


  def test_setTypeReader(self):
    set_type_reader = Internal2.set_type_reader()
    self.assertEqual(type(set_type_reader.api_fuzzzywuzzy), api.api_fuzzywuzzy.ApiFuzzyWuzzy)
    self.assertEqual(type(set_type_reader.api_pytesseract), api.api_pytesseract.ApiPyTesseract)
    self.assertEqual(type(set_type_reader.preprocess_factory), PreprocessFactory)


  def test_statGroupReader(self):
    stat_group_reader = Internal2.stat_group_reader()
    self.assertEqual(type(stat_group_reader.api_tensorflow), api.api_tensorflow.ApiTensorflow)
    self.assertEqual(type(stat_group_reader.preprocess_factory), PreprocessFactory)
    self.assertEqual(type(stat_group_reader.image_scaler), ImageScaler)


  def test_cardReader(self):
    card_reader = Internal3.card_reader()
    self.assertEqual(type(card_reader.image_splitter), ImageSplitter)
    self.assertEqual(type(card_reader.api_builtin), api.api_builtin.ApiBuiltIn)
    self.assertEqual(type(card_reader.api_cv2), api.api_cv2.ApiCv2)
    self.assertEqual(type(card_reader.image_splitter), ImageSplitter)
    self.assertEqual(type(card_reader.stat_group_reader), StatGroupReader)
    self.assertEqual(type(card_reader.set_type_reader), SetTypeReader)


  def test_imageSplitTask(self):
    image_split_task = TaskProvider.image_split_task()
    self.assertEqual("subtask", image_split_task.sub_task)
    self.assertEqual(type(image_split_task.api_builtin), api.api_builtin.ApiBuiltIn)
    self.assertEqual(type(image_split_task.api_cv2), api.api_cv2.ApiCv2)
    self.assertEqual(type(image_split_task.image_splitter), ImageSplitter)


  def test_modelEvaluatorTask(self):
    model_evaluator_task = TaskProvider.model_evaluator_task()
    self.assertEqual("subtask", model_evaluator_task.sub_task)
    self.assertEqual(type(model_evaluator_task.api_builtin), api.api_builtin.ApiBuiltIn)
    self.assertEqual(type(model_evaluator_task.api_cv2), api.api_cv2.ApiCv2)
    self.assertEqual(type(model_evaluator_task.api_pytesseract), api.api_pytesseract.ApiPyTesseract)
    self.assertEqual(type(model_evaluator_task.preprocess_factory), PreprocessFactory)
    self.assertEqual(type(model_evaluator_task.card_reader), CardReader)


  def test_collectGearTask(self):
    collect_gear_task = TaskProvider.collect_gear_task()
    self.assertEqual(type(collect_gear_task.api_builtin), api.api_builtin.ApiBuiltIn)
    self.assertEqual(type(collect_gear_task.api_pyautogui), api.api_pyautogui.ApiPyAutoGui)
    self.assertEqual(type(collect_gear_task.api_time), api.api_time.ApiTime)


  def test_indexTask(self):
    index_task = TaskProvider.index_task()
    self.assertEqual("file", index_task.file)
    self.assertEqual(type(index_task.api_builtin), api.api_builtin.ApiBuiltIn)
    self.assertEqual(type(index_task.api_curses), api.api_curses.ApiCurses)
    self.assertEqual(type(index_task.api_cv2), api.api_cv2.ApiCv2)
    self.assertEqual(type(index_task.api_json), api.api_json.ApiJson)
    self.assertEqual(type(index_task.api_time), api.api_time.ApiTime)


  def test_trainStatValueTask(self):
    train_stat_value_task = TaskProvider.train_stat_type_task()
    self.assertEqual(bool, type(train_stat_value_task.safe))
    self.assertEqual(type(train_stat_value_task.api_builtin), api.api_builtin.ApiBuiltIn)
    self.assertEqual(type(train_stat_value_task.api_cv2), api.api_cv2.ApiCv2)
    self.assertEqual(type(train_stat_value_task.api_json), api.api_json.ApiJson)
    self.assertEqual(type(train_stat_value_task.api_random), api.api_random.ApiRandom)
    self.assertEqual(type(train_stat_value_task.api_tensorflow), api.api_tensorflow.ApiTensorflow)
    self.assertEqual(type(train_stat_value_task.image_scaler), ImageScaler)


  def test_trainStatTypeTask(self):
    train_stat_type_task = TaskProvider.train_stat_type_task()
    self.assertEqual(bool, type(train_stat_type_task.safe))
    self.assertEqual(type(train_stat_type_task.api_builtin), api.api_builtin.ApiBuiltIn)
    self.assertEqual(type(train_stat_type_task.api_cv2), api.api_cv2.ApiCv2)
    self.assertEqual(type(train_stat_type_task.api_json), api.api_json.ApiJson)
    self.assertEqual(type(train_stat_type_task.api_random), api.api_random.ApiRandom)
    self.assertEqual(type(train_stat_type_task.api_tensorflow), api.api_tensorflow.ApiTensorflow)
    self.assertEqual(type(train_stat_type_task.image_scaler), ImageScaler)


  def test_extractGear(self):
    extract_gear = TaskProvider.extract_gear()
    self.assertEqual(type(extract_gear.api_builtin), api.api_builtin.ApiBuiltIn)
    self.assertEqual(type(extract_gear.api_cv2), api.api_cv2.ApiCv2)
    self.assertEqual(type(extract_gear.api_json), api.api_json.ApiJson)
    self.assertEqual(type(extract_gear.api_pyautogui), api.api_pyautogui.ApiPyAutoGui)
    self.assertEqual(type(extract_gear.api_time), api.api_time.ApiTime)
    self.assertEqual(type(extract_gear.card_reader), CardReader)
