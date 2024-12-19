class MyStage():
    """Class for creating an object that communicates with and controls a stage-type device"""

    def __init__(self, name, serial, enable=False):
        """Create a new Stage object for easy communication with the device concerned

        Parameters
        ------------
        name : `str`
            Visible name of this device in the graphical interface
        serial : `str`
            The unique device serial number enabling communication
        enable : `bool`, optional
            Allows or prevents the device from starting once it is connected. False by default
        """
        self.name = name
        self.serial = serial
        self.enable = enable
        self.connected = False
        self.is_running = False


    def connect(self):
        """Not available.
        The purpose of this method is to initiate communication with the device

        Retruns
        ------------
        connect : `bool`
            Whether communication is established
        """
        pass


    def disconnect(self):
        """Not available.
        The purpose of this method is to cleanly terminate communication with the device
        """
        pass


    def __repr__(self):
        return f"{self.name}, serial : {self.serial}"
