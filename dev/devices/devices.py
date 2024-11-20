class MyDevice:
    def __init__(self, name, serial, type = None, feature = None, enabled = True):
        self.name = name
        self.serial = serial
        self.type = type
        self.feature = feature
        self.enable = enabled
        self.connected = False
        self.is_running = False

    def connect(self):
        pass

    def disconnect(self):
        pass

    def __repr__(self):
        return f"{self.name}, serial : {self.serial}"
