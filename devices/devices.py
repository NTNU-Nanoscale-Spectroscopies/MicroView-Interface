class MyDevice:
    def __init__(self, name, serial, type = None, feature = None, enabled = True):
        self.name = name
        self.serial = serial
        self.type = type
        self.feature = feature
        self.enable = enabled
        self.connected = False
    def __repr__(self):
        return f"{self.name}, serial : {self.serial}"


class MySpectrometer(MyDevice):
    def __init__(self, name, serial, enabled = True):
        super().__init__(name, serial, "OceanSepctrometer", "edtiable", enabled)


class MyWhiteLight(MyDevice):
    def __init__(self, name, serial, enabled = False):
        super().__init__(name, serial, "ThorWhiteLight", None, enabled)


class MyLaser(MyDevice):
    def __init__(self, name, serial, enabled = False):
        super().__init__(name, serial, "ThorLaser", "info", enabled)


class MyFilter(MyDevice):
    def __init__(self, name, serial, enabled = True):
        super().__init__(name, serial, "ThorFilter", None, enabled)


class MyPlatform(MyDevice):
    def __init__(self, name, serial, enabled = True):
        super().__init__(name, serial, "ThorPlatform", "edtiable", enabled)