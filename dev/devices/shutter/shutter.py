from .ksc101_shutter import *
from .kst201_shutter import *


class MyShutter():
    """Class for creating an object that communicates with and controls a shutter-type device"""

    def __init__(self, name, serial, enable=False, model=None):
        """Create a new Shutter object for easy communication with the device concerned

        Parameters
        ------------
        name : `str`
            Visible name of this device in the graphical interface
        serial : `str`
            The unique device serial number enabling communication
        enable : `bool`, optional
            Allows or prevents the device from starting once it is connected. False by default
        model : `str`
            The model name of the shutter.
            This affects communication, so be careful to use the correct model. 
            Current supported models : “KSC101” and “KST201”
        """
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