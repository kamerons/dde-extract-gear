#!/usr/bin/env python3

import argparse
import sys

from api.api_builtin import ApiBuiltIn
from api.api_cv2 import ApiCv2
from api.api_json import ApiJson
from api.api_pyautogui import ApiPyAutoGui
from api.api_time import ApiTime

from api.safe_builtin import SafeBuiltIn
from api.safe_cv2 import SafeCv2
from api.safe_json import SafeJson
from api.safe_pyautogui import SafePyAutoGui

from extract_gear.gear_collect import GearCollecter
from extract_gear.image_split_collector import ImageSplitCollector
from extract_gear.image_splitter import ImageSplitter
from extract_gear.index import Index
from extract_gear.model_evaluator import ModelEvaluator

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

if command == GEAR_COLLECT:
  if arg.safe:
    print("Starting screenshot collection in safe mode.")
    gear_collector = GearCollecter(SafeBuiltIn(), SafePyAutoGui())
  else:
    print("Starting screenshot collection.  This operation will change data on the disc")
    gear_collector = GearCollecter(ApiBuiltIn(), ApiPyAutoGui())
    input("Press enter to confirm")
  gear_collector.run()

elif command == MODEL_EVALUATION:
  if arg.safe:
    print("Starting model evaluation in safe mode.")
  else:
    print("Model evaluation can only be run in safe mode.  Starting...")
  model_evaluator = ModelEvaluator(api_cv2=SafeCv2(arg.quiet))
  model_evaluator.run(arg.command[1])

elif command == SPLIT:
  if arg.safe:
    print("Starting data extraction in safe mode.")
    image_split_collector = ImageSplitCollector(SafeCv2(arg.quiet))
  else:
    print("""Starting data extraction.  This operation will change data on the disc.  This operation may overwite indexed
    data Making such data invalid""")
    print("Model splitting cannot be run in quiet mode")
    input("Press enter to confirm")
    image_split_collector = ImageSplitCollector()
  image_split_collector.run(arg.command[1])

elif command == INDEX:
  if arg.safe:
    print("Starting index creation in safe mode.")
    input("Press enter to confirm")
    index = Index(arg.file, api_builtin=SafeBuiltIn(), api_cv2=SafeCv2(), api_json=SafeJson())
  else:
    print("Starting index.  This operation will change data on the disc.  This operation may overwrite index.json")
    input("Press enter to confirm")
    index = Index(arg.file, api_builtin=ApiBuiltIn(), api_cv2=ApiCv2() ,api_json=ApiJson())
  index.run_index_creation()

elif command == TRAIN:
  if arg.safe:
    print("Starting training in safe mode.  Nothing will be written to disc")
  else:
    print("Starting training.  Saved model will be overwritten")
  input("Press enter to confirm")

  #put down here to save on startup time
  from train.train_stat_type import TrainStatType
  from train.train_stat_value import TrainStatValue

  if arg.command[1] == "type":
    train_stat_type = TrainStatType(arg.safe)
    train_stat_type.train()
  else:
    train_stat_value = TrainStatValue(arg.safe)
    train_stat_value.train()

elif command == REAL:
  if arg.safe:
    print("Real data extraction cannot be started in safe mode")
    exit()

  #put down here to save on startup time
  input("Beginning extraction of real data.  Press enter to confirm")
  from extract_gear.extract_gear import ExtractGear
  extract_gear = ExtractGear(ApiBuiltIn(), api_cv2=ApiCv2(arg.quiet), api_pyautogui=ApiPyAutoGui(),
    api_json=ApiJson(), api_time=ApiTime())
  extract_gear.run()
