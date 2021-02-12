import timeout_decorator
import unittest
from unittest.mock import Mock, call

from extract_gear.cli import Cli

class TestCli(unittest.TestCase):

  def test_print(self):
    mock_screen = Mock()
    cli = Cli(mock_screen, [], Mock())

    cli.print("hello")

    mock_screen.addstr.assert_called_once_with("hello")


  def test_print_color(self):
    mock_screen = Mock()
    mock_api_curses = Mock()
    mock_api_curses.color_pair.return_value = "RED_TRANSFORM"
    cli = Cli(mock_screen, [], mock_api_curses)

    cli.print("hello", Cli.RED)

    mock_screen.addstr.assert_called_once_with("hello", "RED_TRANSFORM")


  @timeout_decorator.timeout(1)
  def test_input(self):
    mock_screen = Mock()
    mock_screen.getch.side_effect = self.get_character_input("hello\n")

    cli = Cli(mock_screen, [], Mock())

    actual = cli.input("prompt")
    self.assertEqual("hello", actual)
    calls = [call("prompt"), call("h"), call("e"), call("l"), call("l"), call("o"), call("\n")]
    mock_screen.addstr.assert_has_calls(calls)


  @timeout_decorator.timeout(1)
  def test_input_autocomplete(self):
    mock_screen = Mock()
    mock_screen.getch.side_effect = self.get_character_input("he\t\n")

    cli = Cli(mock_screen, ["hello"], Mock())

    actual = cli.input("prompt")
    self.assertEqual("hello", actual)
    calls = [call("prompt"), call("h"), call("e"), call("llo"), call("\n")]
    mock_screen.addstr.assert_has_calls(calls)


  @timeout_decorator.timeout(1)
  def test_input_autocomplete_multipleChoices(self):
    mock_screen = Mock()
    mock_screen.getch.side_effect = self.get_character_input("g\tm\t\n")

    cli = Cli(mock_screen, ["goodman", "goodbye"], Mock())

    actual = cli.input("prompt")
    self.assertEqual("goodman", actual)
    calls = [call("prompt"), call("g"), call("ood"), call("m"), call("an"), call("\n")]
    mock_screen.addstr.assert_has_calls(calls)


  def get_character_input(self, string):
    chars = []
    for char in string:
      chars.append(ord(char))
    return chars
