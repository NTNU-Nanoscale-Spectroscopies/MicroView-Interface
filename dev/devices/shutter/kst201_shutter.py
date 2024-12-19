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
    """Class for creating an object that communicates with and controls a KST201 shutter device"""

    def __init__(self, serial, enable=False):
        """Create a new KST201 Shutter object for easy communication with the device concerned

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
        self.shutter = None


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
            new_pos = Decimal(5.0)
            self.shutter.MoveTo(new_pos, 1000)
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
            self.shutter.Home(1000)
            self.is_open = False
        return self.state()


    def state(self):
        """Returns the shutter state

        Retruns
        ------------
        state : `bool`
            Whether the shutter is open
        """
        return self.is_open