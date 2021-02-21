from extract_gear.class_repository import TaskProvider


class CommandDelegate:

  delegate_map = {
    "collect": TaskProvider.collect_gear_task,
    "evaluate": TaskProvider.model_evaluator_task,
    "split": TaskProvider.image_split_task,
    "index": TaskProvider.index_task,
    "train": TaskProvider.train_task,
    "gear": TaskProvider.extract_gear,
    "fast-index": TaskProvider.create_fast_index_task
  }


  def delegate(command):
    if command in CommandDelegate.delegate_map:
      task = CommandDelegate.delegate_map[command]()
      task.run()
    else:
      print("Invalid command. Valid commands are: %s" % CommandDelegate.delegate_map.keys())
