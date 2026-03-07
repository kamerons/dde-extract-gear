class ArmorVisitor:

  def __init__(self, num_pages, first_page_col_start, first_page_row_start,
    last_page_row_start, last_page_col_end, last_page_row_end, num_col_page=5, num_row_page=3):
    self.num_pages = num_pages
    self.first_page_col_start = first_page_col_start
    self.first_page_row_start = first_page_row_start
    self.last_page_row_start = last_page_row_start
    self.last_page_col_end = last_page_col_end
    self.last_page_row_end = last_page_row_end
    self.num_col_page = num_col_page
    self.num_row_page = num_row_page


  def iterate(self, callback):
    for page_num in range(1, self.num_pages + 1):
      page = self.create_page(page_num)
      i = 0
      for coord in page:
        callback(coord, page_num, i)
        i += 1


  def create_page(self, page_num):
    if page_num == 1:
      last_col = self.num_col_page if self.num_pages > 1 else self.last_page_col_end
      last_row = self.num_row_page if self.num_pages > 1 else self.last_page_row_end
      page = Page(self.first_page_col_start, self.first_page_row_start, last_col, last_row, self.num_col_page)
    elif page_num == self.num_pages:
      page = Page(1, self.last_page_row_start,
        self.last_page_col_end, self.last_page_row_end, self.num_col_page)
    else:
      page = Page(1, 1, self.num_col_page, self.num_row_page, self.num_col_page)
    return page


class Page:

  def __init__(self, start_col, start_row, last_col, last_row, num_col_page=5):
    self.start_col = start_col
    self.start_row = start_row
    self.last_col = last_col
    self.last_row = last_row
    self.num_col_page = num_col_page


  def __iter__(self):
    self.cur_row = self.start_row
    self.cur_col = self.start_col
    return self


  def __next__(self):
    position = (self.cur_row, self.cur_col)
    if self.cur_row > self.last_row or (self.cur_col > self.last_col and self.cur_row == self.last_row):
      raise StopIteration
    elif self.cur_col == self.num_col_page:
      self.cur_col = 1
      self.cur_row += 1
    else:
      self.cur_col += 1
    return position
