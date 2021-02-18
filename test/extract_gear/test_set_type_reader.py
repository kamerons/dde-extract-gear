import unittest
from unittest.mock import Mock, call

from extract_gear.set_type_reader import SetTypeReader
from test.util.test_util import TestUtil

class TestSetTypeReader(unittest.TestCase):

  @classmethod
  def setUpClass(cls):
    TestSetTypeReader.ORIGINAL_SETTYPEREADER_ATTRIBUTES = TestUtil.get_class_attributes(SetTypeReader)


  @classmethod
  def tearDownClass(cls):
    TestUtil.restore_class_attributes(SetTypeReader, TestSetTypeReader.ORIGINAL_SETTYPEREADER_ATTRIBUTES)


  def test_getArmorType_callsInitializeOnce(self):
    mock_pytesseract = Mock()
    mock_fuzzywuzzy = Mock()
    mock_fuzzywuzzy.ratio.return_value = 0
    set_type_reader = SetTypeReader(Mock(), mock_fuzzywuzzy, mock_pytesseract)

    set_type_reader.get_armor_type("Unprocessed Set Image")

    mock_pytesseract.initialize_pytesseract.assert_called_once()
    set_type_reader.get_armor_type("Unprocessed Set Image")
    mock_pytesseract.initialize_pytesseract.assert_called_once()


  def test_getArmorType_picksHighestGuess(self):
    SetTypeReader.SET_TYPES = ["A", "B", "C", "D"]
    SetTypeReader.MIN_LEVENSHTEIN = 50

    mock_pytesseract = Mock()
    mock_pytesseract.image_to_string.return_value = "CCC  "
    mock_fuzzywuzzy = Mock()
    mock_fuzzywuzzy.ratio.side_effect = [20, 30, 80, 20]
    set_type_reader = SetTypeReader(Mock(), mock_fuzzywuzzy, mock_pytesseract)

    guess = set_type_reader.get_armor_type("Unprocessed Set Image")

    self.assertEqual(guess, "C")
    expected_calls = [call("a", "ccc"), call("b", "ccc"), call("c", "ccc"), call("d", "ccc")]
    mock_fuzzywuzzy.ratio.assert_has_calls(expected_calls)


  def test_getArmorType_returnsNoneWhenNoValueIsGood(self):
    SetTypeReader.SET_TYPES = ["A"]
    SetTypeReader.MIN_LEVENSHTEIN = 50

    mock_pytesseract = Mock()
    mock_pytesseract.image_to_string.return_value = "c"
    mock_fuzzywuzzy = Mock()
    mock_fuzzywuzzy.ratio.return_value = 30
    set_type_reader = SetTypeReader(Mock(), mock_fuzzywuzzy, mock_pytesseract)

    guess = set_type_reader.get_armor_type("Unprocessed Set Image")

    self.assertEqual(guess, None)
    mock_fuzzywuzzy.ratio.assert_called_once_with("a", "c")


  def test_getArmorType_correctPreprocessorCalls(self):
    SetTypeReader.SET_TYPES = ["A"]

    original_img = "Unprocessed Set Image"
    mock_factory = Mock()
    mock_preprocessor = Mock()
    mock_factory.get_set_preprocessor.return_value = mock_preprocessor
    mock_preprocessor.process_set.return_value = "Processed Image"

    mock_pytesseract = Mock()
    mock_pytesseract.image_to_string.return_value = "Original Guess"

    mock_fuzzywuzzy = Mock()
    mock_fuzzywuzzy.ratio.return_value = 30
    set_type_reader = SetTypeReader(mock_factory, mock_fuzzywuzzy, mock_pytesseract)

    set_type_reader.get_armor_type(original_img)

    mock_factory.get_set_preprocessor.assert_called_once_with(original_img)
    mock_preprocessor.process_set.assert_called_once()
    mock_pytesseract.image_to_string.assert_called_once_with("Processed Image")
    mock_fuzzywuzzy.ratio.assert_called_once_with("a", "original guess")
