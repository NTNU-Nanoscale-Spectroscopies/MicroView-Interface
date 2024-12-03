from .devices import MyDevice
import time
import clr

try:
    clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.DeviceManagerCLI.dll")
    clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.GenericMotorCLI.dll")
    clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\ThorLabs.MotionControl.KCube.SolenoidCLI.dll")
    from Thorlabs.MotionControl.DeviceManagerCLI import *
    from Thorlabs.MotionControl.GenericMotorCLI import *
    from Thorlabs.MotionControl.KCube.SolenoidCLI import *
except:
    pass

class MyWhiteLight(MyDevice):
    def __init__(self, name, serial, enabled = False):
        super().__init__(name, serial, "ThorWhiteLight", None, enabled)
        self.is_open = False

    def connect(self):
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
            self.state()

        except Exception as e:
            print(f"Unable to connect to “{self.name}” device with serial number “{self.serial}” : {e}")
            self.connected = False
        return self.connected

    def disconnect(self):
        if self.connected:
            self.shutter.StopPolling()
            self.shutter.Disconnect()

    def open(self):
        if self.connected:
            self.shutter.SetOperatingState(SolenoidStatus.OperatingStates.Active)
            self.is_open = True

    def close(self):
        if self.connected:
            self.shutter.SetOperatingState(SolenoidStatus.OperatingStates.Inactive)
            self.is_open = False

    def state(self):
        if self.shutter.GetSolenoidState() == "Open":
            self.is_open = True
        elif self.shutter.GetSolenoidState() == "Closed":
            self.is_open = False

        return self.is_open