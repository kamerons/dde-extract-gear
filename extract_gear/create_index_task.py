from extract_gear.index import Index
from folder.folder import Folder

class CreateIndexTask:

  DIGIT_KEY = 'digit'
  BLOB = 'blob'

  def __init__(self, api_builtin, api_cv2, api_json, image_splitter, preprocess_factory):
    self.api_builtin = api_builtin
    self.api_cv2 = api_cv2
    self.api_json = api_json
    self.image_splitter = image_splitter
    self.preprocess_factory = preprocess_factory
    self.is_blueprint = False
    self.icon_index = []
    self.digit_index = []


  def run(self):
    self.api_builtin.begin_message("programatic index creation")
    self.create_index_programatically()


  def create_index_programatically(self):
    for _ in range(2):
      card_json_file_name = Folder.BLUEPRINT_CARD_FILE if self.is_blueprint else Folder.CARD_FILE
      with self.api_builtin.open(card_json_file_name, "r") as fp:
        card_json = self.api_json.load(fp)
        self.create_index_from_card_json(card_json)
      self.is_blueprint = not self.is_blueprint
    self.write_data()
    self.slideshow()


  def create_index_from_card_json(self, card_json):
    folder = Folder.BLUEPRINT_FOLDER if self.is_blueprint else Folder.PREPROCESS_FOLDER
    i = 0
    for data in card_json:
      file_name = data[Index.FILE_NAME_KEY]
      orig_img = self.api_cv2.imread(folder + file_name)
      gear_coord = (int(file_name[1]), int(file_name[0]))
      images = self.image_splitter.extract_stat_images(orig_img, gear_coord, self.is_blueprint)
      self.write_stat_images(data, images)
      i += 1
      if i % 10 == 0:
        self.api_builtin.print("Complete %d of %d" % (i, len(card_json)))


  def write_stat_images(self, data, images):
    self.write_image_row(data, images, 0, 4)
    if self.has_hero_attributes(data):
      self.write_image_row(data, images, 4, 10)
      self.write_image_row(data, images, 10, 14)
    else:
      self.write_image_row(data, images, 4, 8, 6)
      self.write_none(images, 10, 14)


  def has_hero_attributes(self, data):
    for attribute in Index.STAT_OPTIONS[4:10]:
      if attribute in data:
        return True
    return False


  def write_image_row(self, data, images, start, end, stat_boost=0):
    num_seen = 0
    for i in range(start, end):
      stat_type = Index.STAT_OPTIONS[i + stat_boost]
      if stat_type in data:
        img = images[num_seen + start]
        self.write_stat_icon(img, stat_type)
        self.write_stat_numbers(data[stat_type], img)
        num_seen += 1
    self.write_none(images, num_seen + start, end)


  def write_none(self, images, start, end):
    for i in range(start, end):
      self.write_stat_icon(images[i], Index.NONE)


  def write_stat_icon(self, img, stat_type):
      file_name = "%s_1_%04d.png" % (stat_type, len(self.icon_index))
      icon_data = {Index.FILE_NAME_KEY: file_name, Index.STAT_TYPE_KEY: stat_type}
      self.icon_index.append(icon_data)
      self.api_cv2.imwrite(Folder.ICON_CROP_FOLDER + file_name, img)


  def write_stat_numbers(self, expected_num, img):
    stat_processor = self.preprocess_factory.get_stat_preprocessor(img)
    stat_processor.process_stat()
    expected_digits = self.get_digits(expected_num)
    if len(expected_digits) != len(stat_processor.digits):
      if len(expected_digits) + 2 == len(stat_processor.digits):
        digits = [CreateIndexTask.BLOB] + expected_digits + [CreateIndexTask.BLOB]
      else:
        self.api_builtin.print("expected %d" % expected_num)
        self.api_cv2.show_img(img)
        digits = self.get_user_classification(stat_processor.digits)
    else:
      digits = expected_digits
    for i in range(len(stat_processor.digits)):
      digit_or_blob = str(digits[i])
      file_name = "%s_1_%04d.png" % (digit_or_blob, len(self.digit_index))
      digit_data = {Index.FILE_NAME_KEY: file_name, CreateIndexTask.DIGIT_KEY: digits[i]}
      self.digit_index.append(digit_data)
      self.api_cv2.imwrite(Folder.DIGIT_CROP_FOLDER + file_name, stat_processor.digits[i])


  def get_user_classification(self, images):
    actual_digits = []
    self.api_builtin.print("Encountered some data which could not be automatically computed.")
    for img in images:
      self.api_cv2.show_img(img)
      digit = self.api_builtin.input_safe_int(
        "What is this number.  Enter a number greater than 10 for blobs\n> ")
      if digit >= 10:
        actual_digits.append(CreateIndexTask.BLOB)
      else:
        actual_digits.append(digit)
    return actual_digits


  def write_data(self):
    with self.api_builtin.open(Folder.ICON_INDEX_FILE, "w") as fp:
      self.api_json.dump(self.icon_index, fp)
    with self.api_builtin.open(Folder.DIGIT_INDEX_FILE, "w") as fp:
      self.api_json.dump(self.digit_index, fp)


  def slideshow(self):
    with open(Folder.ICON_INDEX_FILE, "r") as fp:
      all_data = self.api_json.load(fp)
      all_data = sorted(all_data, key=lambda k: k[Index.FILE_NAME_KEY])
    i = 0
    for data in all_data:
      self.api_builtin.print(data[Index.STAT_TYPE_KEY])
      self.api_builtin.print(data)
      img = self.api_cv2.imread(Folder.ICON_CROP_FOLDER + data[Index.FILE_NAME_KEY])
      self.api_builtin.print(data[Index.FILE_NAME_KEY])
      self.api_cv2.show_img(img)
      i += 1
      if i % 10 == 0:
        self.api_builtin.print("\nComplete %d of %d\n" % (i, len(self.icon_index)))

    with open(Folder.DIGIT_INDEX_FILE, "r") as fp:
      all_data = self.api_json.load(fp)
      all_data = sorted(all_data, key=lambda k: k[Index.FILE_NAME_KEY])
    i = 0
    for data in all_data:
      self.api_builtin.print(data[CreateIndexTask.DIGIT_KEY])
      img = self.api_cv2.imread(Folder.DIGIT_CROP_FOLDER + data[Index.FILE_NAME_KEY])
      self.api_builtin.print(data[Index.FILE_NAME_KEY])
      self.api_cv2.show_img(img)
      i += 1
      if i % 10 == 0:
        self.api_builtin.print("\nComplete %d of %d\n" % (i, len(self.digit_index)))


  def get_digits(self, num):
    digits = []
    while num > 0:
      digits.append(num % 10)
      num = int(num / 10)
    digits.reverse()
    return digits
