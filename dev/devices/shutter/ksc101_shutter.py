import time
import clr
import os

try:
    clr.AddReference(os.path.abspath("dev/devices/shutter/dlls/Thorlabs.MotionControl.DeviceManagerCLI.dll"))
    clr.AddReference(os.path.abspath("dev/devices/shutter/dlls/Thorlabs.MotionControl.GenericMotorCLI.dll"))
    clr.AddReference(os.path.abspath("dev/devices/shutter/dlls/Thorlabs.MotionControl.KCube.SolenoidCLI.dll"))
    from Thorlabs.MotionControl.DeviceManagerCLI import *
    from Thorlabs.MotionControl.GenericMotorCLI import *
    from Thorlabs.MotionControl.KCube.SolenoidCLI import *
except:
    pass


class KSC101_Shutter():
    """Class for creating an object that communicates with and controls a KSC101 shutter device"""

    def __init__(self, serial, enable=False):
        """Create a new KSC101 Shutter object for easy communication with the device concerned

        Parameters
        ------------
        serial : `str`
            The unique device serial number enabling communication
        enable : `bool`, optional
            Allows or prevents the device from starting once it is connected. False by default
        """
        self.serial = serial
        self.enable = enable
        self.connected = False
        self.is_open = False


    def connect(self):
        """Try to establish communication with the device

        Retruns
        ------------
        connect : `bool`
            Whether communication is established
        """
        self.connected = False
        try:
            DeviceManagerCLI.BuildDeviceList()
            self.shutter = KCubeSolenoid.CreateKCubeSolenoid(self.serial)
            self.shutter.Connect(self.serial)
            if not self.shutter.IsSettingsInitialized():
                self.shutter.WaitForSettingsInitialized(3000)
                if not self.shutter.IsSettingsInitialized():
                    self.connected = False
                    return self.connected
                
            self.shutter.StartPolling(250)
            time.sleep(0.25)
            self.shutter.EnableDevice()
            time.sleep(0.5)
            self.shutter.SetOperatingMode(SolenoidStatus.OperatingModes.Manual)
            self.connected = True
            if self.enable:
                self.open()
            else:
                self.close()
            self.state()

        except Exception as e:
            pass
        return self.connected


    def disconnect(self):
        """Try to cleanly terminate communication with the device

        Retruns
        ------------
        disconnect : `bool`
            Whether communication is stopped
        """
        if self.connected:
            self.close()
            self.shutter.StopPolling()
            self.shutter.Disconnect()
            self.connected = False
        return self.connected


    def open(self):
        """Try to open the shutter

        Retruns
        ------------
        open : `bool`
            Whether the shutter is open
        """
        if self.connected:
            self.shutter.SetOperatingState(SolenoidStatus.OperatingStates.Active)
            self.is_open = True
        return self.state()


    def close(self):
        """Try to close the shutter

        Retruns
        ------------
        close : `bool`
            Whether the shutter is close
        """
        if self.connected:
            self.shutter.SetOperatingState(SolenoidStatus.OperatingStates.Inactive)
            self.is_open = False
        return self.state()


    def state(self):
        """Returns the shutter state

        Retruns
        ------------
        state : `bool`
            Whether the shutter is open
        """
        if not self.connected: return False
        if self.shutter.GetSolenoidState() == "Open":
            self.is_open = True
        elif self.shutter.GetSolenoidState() == "Closed":
            self.is_open = False

        return self.is_open