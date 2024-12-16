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
    def __init__(self, serial, enable=False):
        self.serial = serial
        self.enable = enable
        self.connected = False
        self.is_open = False


    def connect(self):
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
                self.state()

        except Exception as e:
            pass
        return self.connected

    def disconnect(self):
        if self.connected:
            self.close()
            self.shutter.StopPolling()
            self.shutter.Disconnect()
            self.connected = False
        return self.connected

    def open(self):
        if self.connected:
            self.shutter.SetOperatingState(SolenoidStatus.OperatingStates.Active)
            self.is_open = True
        return self.state()

    def close(self):
        if self.connected:
            self.shutter.SetOperatingState(SolenoidStatus.OperatingStates.Inactive)
            self.is_open = False
        return self.state()

    def state(self):
        if not self.connected: return False
        if self.shutter.GetSolenoidState() == "Open":
            self.is_open = True
        elif self.shutter.GetSolenoidState() == "Closed":
            self.is_open = False

        return self.is_open