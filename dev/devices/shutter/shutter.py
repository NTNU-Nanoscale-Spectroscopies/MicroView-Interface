from .ksc101_shutter import *
from .kst201_shutter import *


class MyShutter():
    """Class for creating an object that communicates with and controls a shutter-type device"""

    def __init__(self, name, serial, enable=False, model=None, stage=None):
        """Create a new Shutter object

        New parameter:
        stage : `str`, optional
            The specific mechanical stage mounted to the controller (e.g. "FW103M").
            Passed through to the underlying driver to allow index-based control.
        """
        self.name = name
        self.serial = serial
        self.enable = enable
        self.model = model
        self.stage = stage
        self.connected = False
        self.is_open = False

        if self.model == "KSC101":
            self.shutter = KSC101_Shutter(self.serial, self.enable)
        elif self.model == "KST201":
            # pass stage through to the KST201 driver (may be None)
            self.shutter = KST201_Shutter(self.serial, self.enable, stage=self.stage)


    def connect(self):
        """Try to establish communication with the device

        Retruns
        ------------
        connect : `bool`
            Whether communication is established
        """
        self.connected = self.shutter.connect()
        return self.connected


    def disconnect(self):
        """Try to cleanly terminate communication with the device

        Retruns
        ------------
        disconnect : `bool`
            Whether communication is stopped
        """
        self.connected = self.shutter.disconnect()
        return self.connected


    def open(self):
        """Try to open the shutter

        Retruns
        ------------
        open : `bool`
            Whether the shutter is open
        """
        self.is_open = self.shutter.open()
        return self.is_open


    def close(self):
        """Try to close the shutter

        Retruns
        ------------
        close : `bool`
            Whether the shutter is close
        """
        self.is_open = self.shutter.close()
        return self.is_open


    def state(self):
        """Returns the shutter state

        Retruns
        ------------
        state : `bool`
            Whether the shutter is open
        """
        self.is_open = self.shutter.state()
        return self.is_open


    def __repr__(self):
        return f"{self.name}, serial : {self.serial}"