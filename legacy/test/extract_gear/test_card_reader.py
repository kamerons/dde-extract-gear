import unittest
from unittest.mock import Mock

from extract_gear.card_reader import CardReader

class TestCardReader(unittest.TestCase):

  def test_getImgData(self):
    mock_image_splitter = Mock()
    mock_image_splitter.extract_set_image.return_value = "set image"

    mock_set_type_reader = Mock()
    mock_set_type_reader.get_armor_type.return_value = "armor set"

    mock_image_splitter.extract_stat_images.return_value = "stat images"
    mock_stat_group_reader = Mock()
    mock_stat_group_reader.get_stat_types_and_values.return_value = {"stat1": 1, "stat2": 2}

    card_reader = CardReader(None, None, mock_image_splitter, mock_stat_group_reader,
      mock_set_type_reader)
    data = card_reader.get_img_data("original", (2, 3), True)

    expected_data = {'armor_set': 'armor set', 'current_level': 1, 'max_level': 16, 'stat1': 1, 'stat2': 2}
    self.assertEqual(expected_data, data)
    mock_image_splitter.extract_set_image.assert_called_once_with("original", (2, 3), is_blueprint=True)
    mock_set_type_reader.get_armor_type.assert_called_once_with("set image")
    mock_image_splitter.extract_stat_images.assert_called_once_with("original", (2, 3), is_blueprint=True)
    mock_stat_group_reader.get_stat_types_and_values.assert_called_once_with("stat images")
