import unittest
from unittest.mock import Mock, call

from extract_gear.index import Index
from extract_gear.stat_group_reader import StatGroupReader
from folder.folder import Folder
from test.util.test_util import TestUtil

class TestStatGroupReader(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    TestStatGroupReader.STATGROUPREADER_ATTRIBUTES = TestUtil.get_class_attributes(StatGroupReader)
    TestStatGroupReader.INDEX_ATTRIBUTES = TestUtil.get_class_attributes(Index)


  @classmethod
  def tearDownClass(cls):
    TestUtil.restore_class_attributes(StatGroupReader, TestStatGroupReader.STATGROUPREADER_ATTRIBUTES)
    TestUtil.restore_class_attributes(Index, TestStatGroupReader.INDEX_ATTRIBUTES)


  def test_getArmorType_callsInitializeOnce(self):
    StatGroupReader.TOTAL_NUM_IMAGES = 1

    stat_value_preprocessor = Mock()
    stat_value_preprocessor.digits.__len__ = Mock(return_value=0)
    preprocess_factory = Mock()
    preprocess_factory.get_stat_preprocessor.return_value = stat_value_preprocessor

    mock_tensorflow = Mock()
    type_model = Mock()
    value_model = Mock()
    mock_tensorflow.load_model.side_effect = [type_model, value_model]
    stat_group_reader = StatGroupReader(preprocess_factory, mock_tensorflow, Mock())
    type_model.predict_classes.return_value = [0]
    value_model.predict_classes.return_value = [0]

    stat_group_reader.get_stat_types_and_values(["unprocessed images"])

    mock_tensorflow.initialize_tensorflow.assert_called_once()
    self.assertTrue(type_model is stat_group_reader.stat_type_model)
    self.assertTrue(value_model is stat_group_reader.stat_value_model)
    expected_calls = [call(Folder.STAT_TYPE_MODEL_FOLDER), call(Folder.STAT_VALUE_MODEL_FOLDER)]
    mock_tensorflow.load_model.assert_has_calls(expected_calls)

    stat_group_reader.get_stat_types_and_values("Unprocessed Set Image")

    mock_tensorflow.initialize_tensorflow.assert_called_once()


  def test_getArmorType_addsDigitsCorrectly(self):
    StatGroupReader.TOTAL_NUM_IMAGES = 1

    stat_value_preprocessor = Mock()
    stat_value_preprocessor.digits.__len__ = Mock(return_value=3)
    preprocess_factory = Mock()
    preprocess_factory.get_stat_preprocessor.return_value = stat_value_preprocessor

    mock_tensorflow = Mock()
    type_model = Mock()
    value_model = Mock()
    mock_tensorflow.load_model.side_effect = [type_model, value_model]
    stat_group_reader = StatGroupReader(preprocess_factory, mock_tensorflow, Mock())
    type_model.predict_classes.return_value = [0]
    value_model.predict_classes.return_value = [8, 2, 3]

    stats = stat_group_reader.get_stat_types_and_values(["unprocessed images"])

    self.assertEqual(823, stats[Index.STAT_OPTIONS[0]])


  def test_getArmorType_skipsStatIfThereAreNoDigits(self):
    StatGroupReader.TOTAL_NUM_IMAGES = 1

    stat_value_preprocessor = Mock()
    stat_value_preprocessor.digits.__len__ = Mock(return_value=0)
    preprocess_factory = Mock()
    preprocess_factory.get_stat_preprocessor.return_value = stat_value_preprocessor

    mock_tensorflow = Mock()
    type_model = Mock()
    value_model = Mock()
    mock_tensorflow.load_model.side_effect = [type_model, value_model]
    stat_group_reader = StatGroupReader(preprocess_factory, mock_tensorflow, Mock())
    type_model.predict_classes.return_value = [0]
    value_model.predict_classes.return_value = [0]

    stats = stat_group_reader.get_stat_types_and_values(["unprocessed images"])

    self.assertEqual({}, stats)


  def test_getArmorType_loopsThroughStatOptions(self):
    StatGroupReader.TOTAL_NUM_IMAGES = 3
    Index.NONE = "NONE"
    Index.STAT_OPTIONS = ["Class 1", "Class 2", "NONE"]

    stat_value_preprocessor = Mock()
    stat_value_preprocessor.digits.__len__ = Mock(return_value=1)
    preprocess_factory = Mock()
    preprocess_factory.get_stat_preprocessor.return_value = stat_value_preprocessor

    mock_tensorflow = Mock()
    type_model = Mock()
    value_model = Mock()
    mock_tensorflow.load_model.side_effect = [type_model, value_model]
    stat_group_reader = StatGroupReader(preprocess_factory, mock_tensorflow, Mock())
    type_model.predict_classes.return_value = [1, 2, 0]
    value_model.predict_classes.side_effect = [[7], [5]]

    stats = stat_group_reader.get_stat_types_and_values(["1", "2", "3"])

    self.assertEqual({"Class 1": 5, "Class 2": 7}, stats)


  def test_getArmorType_apiCallsCorrect(self):
    StatGroupReader.TOTAL_NUM_IMAGES = 1
    Index.STAT_OPTIONS = ["Class 1"]

    image_scaler = Mock()
    image_scaler.prepare_for_classification.side_effect = [["scaled stat icon"], ["scaled digit"]]

    stat_value_preprocessor = Mock()
    stat_value_preprocessor.digits.__len__ = Mock(return_value=1)
    stat_value_preprocessor.digits = ["processed digit"]
    preprocess_factory = Mock()
    preprocess_factory.get_stat_preprocessor.return_value = stat_value_preprocessor

    mock_tensorflow = Mock()
    type_model = Mock()
    value_model = Mock()
    mock_tensorflow.load_model.side_effect = [type_model, value_model]
    stat_group_reader = StatGroupReader(preprocess_factory, mock_tensorflow, image_scaler)
    type_model.predict_classes.return_value = [0]
    value_model.predict_classes.return_value = [0]

    stat_group_reader.get_stat_types_and_values(["unprocessed image"])

    expected_calls = [call(["unprocessed image"]), call(["processed digit"])]
    image_scaler.prepare_for_classification.assert_has_calls(expected_calls)
    type_model.predict_classes.assert_called_once_with(["scaled stat icon"], batch_size=1, verbose=0)
    preprocess_factory.get_stat_preprocessor("unprocessed image")
    value_model.predict_classes.assert_called_once_with(["scaled digit"], verbose=0)
