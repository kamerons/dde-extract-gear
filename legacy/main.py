#!/usr/bin/env python3

import argparse
import sys

from extract_gear.image_splitter import ImageSplitter
from extract_gear.class_repository import Configs, TaskProvider
from extract_gear.command_delegate import CommandDelegate

from folder.folder import Folder

parser = argparse.ArgumentParser(description='Delegate to corresponding commands')
parser.add_argument('-s', '--safe', action='store_true', default=False,
  help="Determines if the output of the command should write to disc")
parser.add_argument('-q', '--quiet', action='store_true', default=False,
  help="If on, images will not be displayed to the user")
parser.add_argument('-f', '--file', type=str, nargs=1,
  help="The name of the file that should be passed to a different command")
parser.add_argument('command', type=str, nargs='+',
  help="The command to be delegated to.")
arg = parser.parse_args(sys.argv[1:])

Configs.config.override(arg)
command = arg.command[0]
CommandDelegate.delegate(command)
