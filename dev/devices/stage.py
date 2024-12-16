class MyStage():
    def __init__(self, name, serial, enable=False):
        self.name = name
        self.serial = serial
        self.enable = enable
        self.connected = False
        self.is_running = False

    def connect(self):
        pass

    def disconnect(self):
        pass

    def __repr__(self):
        return f"{self.name}, serial : {self.serial}"
