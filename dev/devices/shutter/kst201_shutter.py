import time
import clr
import os

try:
    clr.AddReference(os.path.abspath("dev/devices/shutter/dlls/Thorlabs.MotionControl.DeviceManagerCLI.dll"))
    clr.AddReference(os.path.abspath("dev/devices/shutter/dlls/Thorlabs.MotionControl.GenericMotorCLI.dll"))
    clr.AddReference(os.path.abspath("dev/devices/shutter/dlls/Thorlabs.MotionControl.KCube.StepperMotorCLI.dll"))
    from Thorlabs.MotionControl.DeviceManagerCLI import *
    from Thorlabs.MotionControl.GenericMotorCLI import *
    from Thorlabs.MotionControl.KCube.StepperMotorCLI import *
    from System import Decimal
except:
    pass


class KST201_Shutter():
    def __init__(self, serial, enable=False):
        self.serial = serial
        self.enable = enable
        self.connected = False
        self.is_open = False
        self.shutter = None


    def connect(self):
        self.connected = False
        try:
            DeviceManagerCLI.BuildDeviceList()
            self.shutter =  KCubeStepper.CreateKCubeStepper(self.serial)
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

            use_file_settings = DeviceConfiguration.DeviceSettingsUseOptionType.UseFileSettings
            device_config = self.shutter.LoadMotorConfiguration(self.shutter.DeviceID, use_file_settings)
            home_params = self.shutter.GetHomingParams()
            print(f'Homing Velocity: {home_params.Velocity}')
            self.close()
            device_vel_params = self.shutter.GetVelocityParams()
            print(f'Acceleration: {device_vel_params.Acceleration}', f'Velocity: {device_vel_params.MaxVelocity}')

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
            new_pos = Decimal(5.0)
            self.shutter.MoveTo(new_pos, 1000)
            self.is_open = True
        return self.state()

    def close(self):
        if self.connected:
            self.shutter.Home(1000)
            self.is_open = False
        return self.state()

    def state(self):
        return self.is_open