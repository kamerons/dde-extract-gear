#!/usr/bin/env python3

import argparse
import sys

from extract_gear.image_splitter import ImageSplitter
from extract_gear.class_repository import Configs, TaskProvider

from folder.folder import Folder

GEAR_COLLECT = "gearcollect"
MODEL_EVALUATION = "evaluate"
SPLIT = "split"
INDEX = "index"
TRAIN = "train"
REAL = "real"

command_options = [GEAR_COLLECT, MODEL_EVALUATION, SPLIT, TRAIN, REAL]

parser = argparse.ArgumentParser(description='Delegate to corresponding commands')
parser.add_argument('-s', '--safe', action='store_true', default=False,
  help="Determines if the output of the command should write to disc")
parser.add_argument('-q', '--quiet', action='store_true', default=False,
  help="If on, images will not be displayed to the user")
parser.add_argument('-f', '--file', type=str, nargs=1,
  help="The name of the file that should be passed to a different command")
parser.add_argument('command', type=str, nargs='+',
  help="The command to be delegated to. Valid options are %s" % str(command_options))
arg = parser.parse_args(sys.argv[1:])

command = arg.command[0]
Configs.config.override(arg)
if command == GEAR_COLLECT:
  if arg.safe:
    print("Starting screenshot collection in safe mode.")
  else:
    print("Starting screenshot collection.  This operation will change data on the disc")
    input("Press enter to confirm")
  task = TaskProvider.collect_gear_task()
  task.run()

elif command == MODEL_EVALUATION:
  if arg.safe:
    print("Starting model evaluation in safe mode.")
  else:
    print("Model evaluation can only be run in safe mode.  Starting...")
  task = TaskProvider.model_evaluator_task()
  task.run()

elif command == SPLIT:
  if arg.safe:
    print("Starting data extraction in safe mode.")
  else:
    print("""Starting data extraction.  This operation will change data on the disc.  This operation may overwite indexed
    data Making such data invalid""")
    print("Model splitting cannot be run in quiet mode")
    input("Press enter to confirm")
  task = TaskProvider.image_split_task()
  task.run()

elif command == INDEX:
  if arg.safe:
    print("Starting index creation in safe mode.")
    input("Press enter to confirm")
  else:
    print("Starting index.  This operation will change data on the disc.  This operation may overwrite index.json")
    input("Press enter to confirm")
  task = TaskProvider.index_task()
  task.run()

elif command == TRAIN:
  if arg.safe:
    print("Starting training in safe mode.  Nothing will be written to disc")
  else:
    print("Starting training.  Saved model will be overwritten")
  input("Press enter to confirm")

  if arg.command[1] == "type":
    task = TaskProvider.train_stat_type_task()
  else:
    task = TaskProvider.train_stat_value_task()
  task.train()

elif command == REAL:
  if arg.safe:
    print("Real data extraction cannot be started in safe mode")
    exit()
  task = TaskProvider.extract_gear()
  task.run()
