class ImageTypeData:

  def __init__(self, size, rel_start_offset, rows=None, columns=None, pass_fn=None, next_offset=None):
    self.size = size
    self.rel_start_offset = rel_start_offset
    self.rows = rows
    self.columns = columns
    self.pass_fn = pass_fn
    self.next_offset = next_offset
