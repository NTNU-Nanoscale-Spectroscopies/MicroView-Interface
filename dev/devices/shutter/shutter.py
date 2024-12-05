from .ksc101_shutter import *
from .kst201_shutter import *


class MyShutter():
    def __init__(self, name, serial, enable=False, model=None):
        self.name = name
        self.serial = serial
        self.enable = enable
        self.model = model
        self.connected = False
        self.is_open = False

        if self.model == "KSC101":
            self.shutter = KSC101_Shutter(self.serial, self.enable)
        elif self.model == "KST201":
            self.shutter = KST201_Shutter(self.serial, self.enable)

    def connect(self):
        self.connected = self.shutter.connect()
        return self.connected

    def disconnect(self):
        self.connected = self.shutter.disconnect()
        return self.connected

    def open(self):
        self.is_open = self.shutter.open()
        return self.is_open

    def close(self):
        self.is_open = self.shutter.close()
        return self.is_open

    def state(self):
        self.is_open = self.shutter.state()
        return self.is_open

    def __repr__(self):
        return f"{self.name}, serial : {self.serial}"