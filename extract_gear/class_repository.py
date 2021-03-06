from dependency_injector import providers, containers

from api.api_builtin import ApiBuiltIn
from api.api_curses import ApiCurses
from api.api_cv2 import ApiCv2
from api.api_fuzzywuzzy import ApiFuzzyWuzzy
from api.api_json import ApiJson
from api.api_keyboard import ApiKeyboard
from api.api_pyautogui import ApiPyAutoGui
from api.api_pytesseract import ApiPyTesseract
from api.api_random import ApiRandom
from api.api_tensorflow import ApiTensorflow
from api.api_time import ApiTime

from extract_gear.card_reader import CardReader
from extract_gear.collect_gear_task import CollectGearTask
from extract_gear.create_index_task import CreateIndexTask
from extract_gear.extract_gear import ExtractGear
from extract_gear.image_split_collector import ImageSplitCollector
from extract_gear.image_splitter import ImageSplitter
from extract_gear.index import Index
from extract_gear.model_evaluator import ModelEvaluator
from extract_gear.page_detector import PageDetector
from extract_gear.preprocess_factory import PreprocessFactory
from extract_gear.set_type_reader import SetTypeReader
from extract_gear.stat_group_reader import StatGroupReader

from train.image_scaler import ImageScaler
from train.train_task import TrainTask
from train.train_stat_type import TrainStatType
from train.train_stat_value import TrainStatValue

class Configs(containers.DeclarativeContainer):
  config = providers.Configuration('config')


class Api1(containers.DeclarativeContainer):
  api_builtin = providers.Singleton(ApiBuiltIn, Configs.config)
  api_fuzzywuzzy = providers.Singleton(ApiFuzzyWuzzy)
  api_curses = providers.Singleton(ApiCurses)
  api_keyboard = providers.Singleton(ApiKeyboard)
  api_pytesseract = providers.Singleton(ApiPyTesseract)
  api_random = providers.Singleton(ApiRandom)
  api_tensorflow = providers.Singleton(ApiTensorflow, Configs.config)
  api_time = providers.Singleton(ApiTime)


class Api2(containers.DeclarativeContainer):
  api_cv2 = providers.Singleton(ApiCv2, Configs.config, Api1.api_builtin)
  api_json = providers.Singleton(ApiJson, Configs.config)
  api_pyautogui = providers.Singleton(ApiPyAutoGui, Configs.config, Api1.api_builtin)


class Internal1(containers.DeclarativeContainer):
  image_splitter = providers.Singleton(ImageSplitter)
  preprocess_factory = providers.Singleton(PreprocessFactory)
  image_scaler = providers.Singleton(ImageScaler)


class Internal2(containers.DeclarativeContainer):
  page_detector = providers.Singleton(PageDetector, Api2.api_cv2, Internal1.image_splitter)
  set_type_reader = providers.Singleton(SetTypeReader, Internal1.preprocess_factory,
    Api1.api_fuzzywuzzy, Api1.api_pytesseract)
  stat_group_reader = providers.Singleton(StatGroupReader, Internal1.preprocess_factory,
    Api1.api_tensorflow, Internal1.image_scaler)


class Internal3(containers.DeclarativeContainer):
  card_reader = providers.Singleton(CardReader, Api1.api_builtin, Api2.api_cv2, Internal1.image_splitter,
    Internal2.stat_group_reader, Internal2.set_type_reader)


class Trainers(containers.DeclarativeContainer):
  train_stat_value = providers.Singleton(TrainStatValue, Configs.config, Api1.api_builtin,
    Api2.api_cv2, Api2.api_json, Api1.api_random, Api1.api_tensorflow, Internal1.image_scaler)
  train_stat_type = providers.Singleton(TrainStatType, Configs.config, Api1.api_builtin,
    Api2.api_cv2, Api2.api_json, Api1.api_random, Api1.api_tensorflow, Internal1.image_scaler)


class TaskProvider(containers.DeclarativeContainer):
  image_split_task = providers.Singleton(ImageSplitCollector, Configs.config, Api1.api_builtin,
    Api2.api_cv2, Internal1.image_splitter)
  model_evaluator_task = providers.Singleton(ModelEvaluator, Configs.config, Api1.api_builtin, Api2.api_cv2,
    Api2.api_json, Internal3.card_reader, Internal1.image_splitter, Internal2.page_detector)
  collect_gear_task = providers.Singleton(CollectGearTask, Configs.config, Api1.api_builtin,
    Api1.api_keyboard, Api2.api_pyautogui, Api1.api_time)
  index_task = providers.Singleton(Index, Configs.config, Api1.api_builtin, Api1.api_curses,
    Api2.api_cv2, Api2.api_json, Api1.api_time)
  create_fast_index_task = providers.Singleton(CreateIndexTask, Api1.api_builtin, Api2.api_cv2,
    Api2.api_json, Internal1.image_splitter, Internal1.preprocess_factory)

  extract_gear = providers.Singleton(ExtractGear, Api1.api_builtin, Api2.api_cv2,
    Api2.api_pyautogui, Api2.api_json, Api1.api_time, Api1.api_keyboard, Internal3.card_reader)

  train_task = providers.Singleton(TrainTask, Configs.config, Api1.api_builtin,
    Trainers.train_stat_value, Trainers.train_stat_type)
