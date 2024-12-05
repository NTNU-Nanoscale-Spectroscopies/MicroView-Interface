from .shutter.shutter import *

class MyLaser():
    def __init__(self, name, serial, enable=False, shutter_model=None, shutter_serial=None):
        self.name = name
        self.serial = serial
        self.enable = enable
        self.connected = False
        self.is_running = False
        self.shutter = None
        if shutter_model and shutter_serial:
            self.shutter = MyShutter(f"{name} shutter", shutter_serial, enable, shutter_model)

    def connect(self):
        self.connected = True # Replace with real laser connection system
        if self.shutter:
            self.connected = self.connected and self.shutter.connect()
        return self.connected

    def disconnect(self):
        self.connected = False # Replace with real laser deconnection system
        if self.shutter:
            self.shutter.disconnect()

    def __repr__(self):
        if self.shutter:
            return f"{self.name}, serial : {self.serial}\n\t{self.shutter}"
        else:
            return f"{self.name}, serial : {self.serial}"
