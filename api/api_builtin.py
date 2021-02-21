class ApiBuiltIn:

  def __init__(self, args):
    self.safe = args.safe


  def open(self, path, mode):
    if mode == 'r' or not self.safe:
      return open(path, mode)
    else:
      return EmptyContextManger()


  def print(self, msg):
    return print(msg)


  def input(self, prompt):
    return input(prompt)


  def input_safe_int(self, prompt):
    user_input = input(prompt)
    while not user_input.isnumeric():
      user_input = input("Enter a valid integer\n> ")
    return int(user_input)


  def exit(self):
    exit()


  def begin_message(self, task_name):
    mode = "safe" if self.safe else "unsafe"
    self.print("Beginning %s in %s mode." % (task_name, mode))
    self.input("Press enter to confirm")


# We need this so we can use the with as syntax.  It doesn't need to do anything since we don't actually
# open the file
class EmptyContextManger:
  def __enter__(self):
    return self

  def __exit__(self, exception_type, exception_value, trace_back):
    pass
