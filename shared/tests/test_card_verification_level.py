"""Unit tests for level interpretation in card_verification (_interpret_level_digits)."""

import unittest

from shared.card_verification import _interpret_level_digits


class TestInterpretLevelDigits(unittest.TestCase):
    """Digit indices: 0-9 = digit, 10 = none (slash)."""

    def test_three_clusters_1_slash_6(self):
        # "1 / 6" -> indices [1, 10, 6]
        current, max_level = _interpret_level_digits([1, 10, 6])
        self.assertEqual(current, 1)
        self.assertEqual(max_level, 6)

    def test_three_clusters_y_zero_invalid(self):
        # Y must be in 1-16; 0 is invalid
        current, max_level = _interpret_level_digits([9, 10, 0])
        self.assertIsNone(current)
        self.assertIsNone(max_level)

    def test_three_clusters_max_single_digit_valid(self):
        # With 3 clusters Y is one digit (1-9)
        current, max_level = _interpret_level_digits([1, 10, 9])
        self.assertEqual(current, 1)
        self.assertEqual(max_level, 9)

    def test_four_clusters_x_one_digit_y_two(self):
        # "1 / 16" -> [1, 10, 1, 6]
        current, max_level = _interpret_level_digits([1, 10, 1, 6])
        self.assertEqual(current, 1)
        self.assertEqual(max_level, 16)

    def test_four_clusters_single_digit_max(self):
        current, max_level = _interpret_level_digits([5, 10, 0, 9])
        self.assertEqual(current, 5)
        self.assertEqual(max_level, 9)

    def test_five_clusters_both_two_digits(self):
        # "10 / 16" -> [1, 0, 10, 1, 6]
        current, max_level = _interpret_level_digits([1, 0, 10, 1, 6])
        self.assertEqual(current, 10)
        self.assertEqual(max_level, 16)

    def test_five_clusters_01_slash_12(self):
        current, max_level = _interpret_level_digits([0, 1, 10, 1, 2])
        self.assertEqual(current, 1)
        self.assertEqual(max_level, 12)

    def test_validation_x_le_y(self):
        # "5 / 3" invalid
        current, max_level = _interpret_level_digits([5, 10, 3])
        self.assertIsNone(current)
        self.assertIsNone(max_level)

    def test_validation_y_in_1_16(self):
        # Y=0 invalid
        current, max_level = _interpret_level_digits([0, 10, 0])
        self.assertIsNone(current)
        self.assertIsNone(max_level)
        # Y=17 invalid (two digits)
        current, max_level = _interpret_level_digits([1, 10, 1, 7])
        self.assertIsNone(current)
        self.assertIsNone(max_level)

    def test_wrong_count_returns_none(self):
        self.assertEqual(_interpret_level_digits([]), (None, None))
        self.assertEqual(_interpret_level_digits([1, 10]), (None, None))
        self.assertEqual(_interpret_level_digits([1, 10, 6, 1, 6, 10]), (None, None))

    def test_slash_position_digit_at_slash_treated_as_invalid_digit(self):
        # If middle cluster predicted as digit (e.g. 1) instead of 10, we still use position: 3 clusters -> indices 0,2 are digits
        # [1, 1, 6] would mean we interpret as X=1, Y=6 (we ignore index 1 for value; but we use position)
        current, max_level = _interpret_level_digits([1, 1, 6])
        self.assertEqual(current, 1)
        self.assertEqual(max_level, 6)
