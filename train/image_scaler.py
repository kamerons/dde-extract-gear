import numpy as np

from extract_gear.image_splitter import ImageSplitter

class ImageScaler:

  def prepare_for_classification(self, data):
    x = []
    y = []
    for item in data:
      feature, label = self.safe_unpack(item)
      x.append(feature)
      y.append(label)

    x = np.array(x) / 255
    x.reshape(-1, ImageSplitter.STAT_DATA.size[0], ImageSplitter.STAT_DATA.size[1], 1)
    y = np.array(y)
    return (x, y)


  def safe_unpack(self, maybe_list):
    if type(maybe_list) != list:
      return maybe_list, None
    else:
      return maybe_list
