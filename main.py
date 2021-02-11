#!/usr/bin/env python3

import argparse
import sys

from api.api_pyautogui import ApiPyAutoGui
from api.safe_pyautogui import SafePyAutoGui
from gear_collect import GearCollecter
from slideshow import SlideShow


GEAR_COLLECT = "gearcollect"
SLIDESHOW = "slideshow"

command_options = [GEAR_COLLECT, SLIDESHOW]

parser = argparse.ArgumentParser(description='Delegate to corresponding commands')
parser.add_argument('-s', '--safe', action='store_true', default=False,
  help="Determines if the output of the command should write to disc")
parser.add_argument('-f', '--file', type=str, nargs=1,
  help="The name of the file that should be passed to a different command")
parser.add_argument('command', type=str, nargs='+',
  help="The command to be delegated to. Valid options are %s" % str(command_options))

arg = parser.parse_args(sys.argv[1:])
command = arg.command[0]
if command == GEAR_COLLECT:
  if arg.safe:
    print("Starting screenshot collection in safe mode.")
    api_pyautogui = SafePyAutoGui()
  else:
    print("Starting screenshot collection")
    api_pyautogui = ApiPyAutoGui()
  input("Press enter to confirm")
  gear_collector = GearCollecter(api_pyautogui=api_pyautogui)
  gear_collector.run()

elif command == SLIDESHOW:
  if arg.safe:
    print("Starting slideshow in safe mode.")
    slideshow = SlideShow()
  else:
    print("Starting slideshow.")
    slideshow = SlideShow()
  slideshow.run(arg.command[1])
