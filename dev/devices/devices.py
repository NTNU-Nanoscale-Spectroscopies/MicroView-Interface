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
