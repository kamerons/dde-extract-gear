import os

class ApiTensorflow:

  def __init__(self, args):
    self.quiet = args.quiet

  def initialize_tensorflow(self):
    if self.quiet:
      os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

    import tensorflow as tf
    config = tf.compat.v1.ConfigProto()
    config.gpu_options.allow_growth = True
    tf.compat.v1.keras.backend.set_session(tf.compat.v1.Session(config=config))

    from tensorflow.keras.losses import SparseCategoricalCrossentropy as SCC
    self.SparseCategoricalCrossentropy = SCC

    import tensorflow.keras
    from tensorflow.keras.models import Sequential as S
    self.Sequential = S

    from tensorflow.keras.layers import Dense as D, Conv2D as C2D, MaxPool2D as MP2D, \
      Flatten as F, Dropout as DO
    self.Dense, self.Conv2D, self.MaxPool2D, self.Flatten, self.Dropout = (D, C2D, MP2D, F, DO)

    from tensorflow.keras.preprocessing.image import ImageDataGenerator as IDG
    self.ImageDataGenerator = IDG

    from tensorflow.keras.optimizers import Adam as A
    self.Adam = A

    from sklearn.metrics import classification_report as cr, confusion_matrix as cm
    self.classification_report, self.confusion_matrix = cr, cm

    from tensorflow.keras.losses import SparseCategoricalCrossentropy as SCC
    self.SparseCategoricalCrossentropy = SCC

    from tensorflow.keras.models import load_model as lm
    self.load_model = lm
