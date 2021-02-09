

class Screen:
  X_STAT_OFFSET = 59.6
  Y_STAT_OFFSET = 87

  X_GEAR_OFFSET = 174
  Y_GEAR_OFFSET = 177

  START_X = 437.5
  START_Y = 385

  X_CORNER_OFFSET = 5
  Y_CORNER_OFFSET = -7

  #black
  HERO_BODY_COLOR = [] #[0, 0, 0]

  HERO_OFFENSE_COLOR = [] #[58, 173, 242]
  HERO_DEFENSE_COLOR = [] #[120, 255, 77]
  X_HERO_MAIN_OFFSET = -27
  Y_HERO_MAIN_OFFSET = -5

  #blue
  DEFENSE_RANGE_COLOR = []
  DEFENSE_DAMAGE_COLOR = [] #[0, 94, 156]
  DEFENSE_HP_COLOR = []

  BORDER_COLOR = []#[133, 148, 158]

  #hero sample
  HP_COLOR = []#[14, 10, 137]
  #green
  HERO_RATE_COLOR = []#[22, 214, 44]

  DEFENSE_RATE_COLOR = []#[16, 106, 33]

  #yellow/orange
  DMG_COLOR = []#[5, 190, 247]

 #brown/tan
  BASE_COLOR = []
  #green
  POISON_COLOR = []#[99, 227, 150]
  #blue
  ELECTRIC_COLOR = []#[255, 255, 115]
  #red
  FIRE_COLOR = []#[49, 162, 250]

  X_HERO_SECONDARY_OFFSET = -20
  Y_HERO_SECONDARY_OFFSET = -15

  ALLOWED_DEVIATION = 45

  X_HERO_SPEED_OFFSET = -11
  Y_HERO_SPEED_OFFSET = 6
  sampled = []

  WIDTH = 0
  HEIGHT = 0

  #not gear, but stat coordinates, i.e x:1-5, y:1-3
  def interpret_gear(self, img, x, y):
    x_coord = Screen.START_X + (x-1) * Screen.X_GEAR_OFFSET
    y_coord = Screen.START_Y + (y-1) * Screen.Y_GEAR_OFFSET
    stats = ['base']
    orig_x = x_coord
    #base resistance is guaranteed
    print("looking at position 2")
    x_coord += Screen.X_STAT_OFFSET
    stats += self.interpret_armor(img, x_coord, y_coord)

    x_coord += Screen.X_STAT_OFFSET
    for i in range(2):
      if self.has_border(img, x_coord, y_coord):
        stats += self.interpret_armor(img, x_coord, y_coord)
        x_coord += Screen.X_STAT_OFFSET

    print("moving on to 2nd row")
    #Does a hero row exist?
    x_coord = orig_x
    y_coord += Screen.Y_STAT_OFFSET

    #FOR STATS IN EXCESS OF 4, WE CAN MORE RELIABLY CHECK THE BORDER
    if self.get_hero_stat(img, x_coord, y_coord):
      for i in range(6):
        self.sampled += [[x_coord, y_coord]]
        stat = self.get_hero_stat(img, x_coord, y_coord)
        if stat:
          stats += stat
        else:
          break
        x_coord += Screen.X_STAT_OFFSET

    x_coord = orig_x
    y_coord += Screen.Y_STAT_OFFSET
    print("moving on to tower stats")
    if self.get_tower_stat(img, x_coord, y_coord):
      for i in range(4):
        stat = self.get_tower_stat(img, x_coord, y_coord)
        if stat:
          stats += stat
        else:
          break
        x_coord += Screen.X_STAT_OFFSET
    print(self.sampled)
    return self.sampled
    #return stats

  def get_tower_stat(self, img, x, y):
    if self.has_border(img, x, y):
      if self.within_color(img, x, y, Screen.HP_COLOR):
        return 'tower_hp'
      elif self.within_color(img, x, y, Screen.RATE_COLOR):
        return 'tower_rate'
      elif self.within_color(img, x, y, Screen.DMG_COLOR):
        return 'tower_dmg'
      elif self.within_color(img, x, y, Screen.TOWER_RANGE_COLOR):
        return 'tower_range'
      else:
        print("Could not tower hero stat")
        exit()
    else:
      return False

  def get_hero_stat(self, img, x, y):
    if self.has_border(img, x, y):
      if self.within_color(img, x + Screen.X_HERO_SPEED_OFFSET,  y + Screen.Y_HERO_SPEED_OFFSET, Screen.HERO_BODY_COLOR):
        return 'hero_speed'
      elif self.within_color(img, x + Screen.X_HERO_SECONDARY_OFFSET, y + Screen.Y_HERO_SECONDARY_OFFSET, Screen.HERO_BODY_COLOR):
        if self.within_color(img, x, y, Screen.HERO_OFFENSE_COLOR):
          return 'hero_offense'
        elif self.within_color(img, x, y, Screen.HERO_DEFENSE_COLOR):
          return 'hero_defense'
        else:
          print("could not interpret hero offense/defense color")
          exit()
      elif self.within_color(img, x + X_HERO_MAIN_OFFSET, y + Y_HERO_MAIN_OFFSET, HERO_BODY_COLOR):
        if self.within_color(img, x, y, Screen.HP_COLOR):
          return 'hero_hp'
        elif self.within_value(img, x, y, Screen.RATE_COLOR):
          return 'hero_rate'
        elif self.within_value(img, x, y, Screen.DMG_COLOR):
          return 'hero_dmg'
        else:
          print("Could not interpret hero stat")
          exit()
    else:
      return False

  def interpret_armor(self, img, x, y):
    if self.within_color(img, x, y, Screen.POISON_COLOR):
      return 'poision'
    elif self.within_color(img, x, y, Screen.ELECTRIC_COLOR):
      return 'electric'
    elif self.within_color(img, x, y, Screen.FIRE_COLOR):
      return 'fire'
    else:
      print("failed to recognize armor color")
      exit()

  def has_border(self, img, x, y):
    return self.within_color(img, x + Screen.X_CORNER_OFFSET, y + Screen.Y_CORNER_OFFSET, Screen.BORDER_COLOR)

  def within_color(self, img, x, y, expected):
    pixel = img[round(y), round(x)]
    if expected == []:
      print("no value expected, saw: " + str(pixel) + " at: " + str(x) + ", " + str(y))
      self.sampled += [[x, y]]
      return True
    self.within_value(img[round(y), round(x)], expected)


  def within_value(self, pixel, expected):
    so_far = True
    for i in range(3):
      so_far = so_far and abs(pixel[i] - expected[i]) <= Screen.ALLOWED_DEVIATION
    return so_far
