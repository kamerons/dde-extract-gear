class TrainTask:

  def __init__(self, args, api_builtin, train_stat_value, train_stat_type):
    self.sub_task = args.command[1]
    self.train_stat_value = train_stat_value
    self.train_stat_type = train_stat_type
    self.api_builtin = api_builtin


  def run(self):
    self.api_builtin.begin_message("neural network training")
    if self.sub_task == "value":
      self.train_stat_value.train()
    elif self.sub_task == "type":
      self.train_stat_type.train()
    else:
      self.api_builtin.print("Invalid subtask.  Valid values are: [value, type]")
