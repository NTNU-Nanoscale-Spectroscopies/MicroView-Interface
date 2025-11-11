import time
import clr
import os
import traceback

# Use paths relative to this file so AddReference works regardless of CWD
base_dir = os.path.dirname(__file__)
dll_dir = os.path.join(base_dir, "dlls")

try:
    runtime_dlls = [
        os.path.join(dll_dir, "Thorlabs.MotionControl.DeviceManagerCLI.dll"),
        os.path.join(dll_dir, "Thorlabs.MotionControl.GenericMotorCLI.dll"),
        os.path.join(dll_dir, "Thorlabs.MotionControl.KCube.StepperMotorCLI.dll"),
    ]
    for p in runtime_dlls:
        if not os.path.exists(p):
            raise FileNotFoundError(f"Thorlabs DLL not found: {p}")
        clr.AddReference(p)

    from Thorlabs.MotionControl.DeviceManagerCLI import *
    from Thorlabs.MotionControl.GenericMotorCLI import *
    from Thorlabs.MotionControl.KCube.StepperMotorCLI import *
    from System import Decimal
except Exception as e:
    # Surface the real error during development/build time
    print("Failed to load pythonnet or Thorlabs assemblies:", e)
    traceback.print_exc()


class KST201_Shutter():
    """Class for creating an object that communicates with and controls a KST201 shutter device"""

    def __init__(self, serial, enable=False, stage=None):
        """Create a new KST201 Shutter object

        Parameters
        ------------
        serial : `str`
            The unique device serial number enabling communication
        enable : `bool`, optional
            Allows or prevents the device from starting once it is connected. False by default
        stage : `str`, optional
            The mechanical stage mounted on the controller (e.g. "FW103M").
            If provided, the driver will try to apply this stage to the device configuration
            and will use index-style moves for filter-wheels where appropriate.
        """
        self.serial = serial
        self.enable = enable
        self.stage = stage
        self.connected = False
        self.is_open = False
        self.shutter = None
        # Default visible angles for a filter-wheel used as a shutter
        self.open_angle = 60.0    # degrees to move for "open" (visible)
        self.closed_angle = 0.0   # home/closed at 0 degrees


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
            if self.shutter is None:
                raise RuntimeError(f"CreateKCubeStepper returned None for serial {self.serial}")
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

            # Home the device after enabling so controller is at 0 degrees by default
            try:
                if hasattr(self.shutter, "Home"):
                    # allow the home call to complete (best-effort)
                    self.shutter.Home(5000)
                    self.is_open = False
                    print("KST201: Homed after connect (requested).")
            except Exception as e:
                print("KST201: Home after connect failed:", e)

            use_file_settings = DeviceConfiguration.DeviceSettingsUseOptionType.UseFileSettings
            device_config = self.shutter.LoadMotorConfiguration(self.shutter.DeviceID, use_file_settings)
            home_params = self.shutter.GetHomingParams()
            print(f'Homing Velocity: {home_params.Velocity}')
            self.close()
            device_vel_params = self.shutter.GetVelocityParams()
            print(f'Acceleration: {device_vel_params.Acceleration}', f'Velocity: {device_vel_params.MaxVelocity}')

            # Attempt to set stage type if the user provided one (best-effort)
            if self.stage:
                try:
                    # Many Kinesis/Thorlabs objects don't expose an assignable stage field;
                    # try a few reasonable possibilities without risking failure of the whole connect.
                    if hasattr(device_config, 'Stage'):
                        try:
                            device_config.Stage = self.stage
                            print(f"Applied stage to device_config.Stage: {self.stage}")
                        except Exception as e:
                            print("Could not set device_config.Stage:", e)
                    elif hasattr(device_config, 'StageType'):
                        try:
                            device_config.StageType = self.stage
                            print(f"Applied stage to device_config.StageType: {self.stage}")
                        except Exception as e:
                            print("Could not set device_config.StageType:", e)

                    # If controller exposes a helper, try that too.
                    if hasattr(self.shutter, 'SetMotorConfigurationByStage'):
                        try:
                            self.shutter.SetMotorConfigurationByStage(self.shutter.DeviceID, self.stage)
                            print("Called SetMotorConfigurationByStage on controller.")
                        except Exception as e:
                            print("SetMotorConfigurationByStage failed:", e)
                except Exception as e:
                    print("Stage selection attempt failed:", e)

            self.connected = True
            if self.enable:
                self.open()
            else:
                self.close()
            self.state()

        except Exception as e:
            print("KST201 connect error:", e)
            import traceback; traceback.print_exc()
        return self.connected

    # <-- Added back: disconnect method required by MyShutter wrapper
    def disconnect(self):
        """Try to cleanly terminate communication with the device"""
        if self.connected and self.shutter is not None:
            try:
                # attempt graceful stop/home then polling/disconnect
                try:
                    self.close()
                except Exception:
                    pass
                try:
                    self.shutter.StopPolling()
                except Exception:
                    pass
                try:
                    self.shutter.Disconnect()
                except Exception:
                    pass
            finally:
                self.connected = False
        return self.connected

    # helper to try multiple possible move APIs (safe best-effort)
    def _move_to(self, target, timeout=1000):
        """Try several possible movement methods which different Thorlabs objects may expose.
        Returns True on success, False otherwise.
        """
        # If the controller expects a Decimal for absolute positions, try that
        try:
            dec_target = Decimal(float(target))
        except Exception:
            dec_target = target

        candidates = [
            ('MoveTo', (dec_target, timeout)),
            ('MoveTo', (dec_target,)),  # sometimes only target
            ('MoveToPosition', (int(target),)),  # index-based
            ('MoveToPositionAsynchronous', (int(target),)),
            ('MoveToPositionIndex', (int(target),)),
            ('MoveToPositionByIndex', (int(target),))
        ]

        for name, args in candidates:
            if hasattr(self.shutter, name):
                try:
                    func = getattr(self.shutter, name)
                    func(*args)
                    # small wait to allow device to start and be visible;
                    # increase slightly so filter wheel motion is perceptible
                    time.sleep(0.5)
                    return True
                except TypeError:
                    # signature mismatch, try next
                    continue
                except Exception as e:
                    print(f"Attempt to call {name} failed: {e}")
                    continue
        # as fallback, try Home for "close" scenarios if available
        if hasattr(self.shutter, 'Home'):
            try:
                self.shutter.Home(timeout)
                return True
            except Exception:
                pass
        return False


    def open(self):
        """Try to open the shutter

        Retruns
        ------------
        open : `bool`
            Whether the shutter is open
        """
        if self.connected:
            # If the device is actually a filter-wheel (FW103/M family), prefer degree-based moves.
            if self.stage and 'FW103' in self.stage.upper():
                ok = self._move_to(self.open_angle, 2000)
                if ok:
                    self.is_open = True
            else:
                new_pos = Decimal(5.0)
                if self._move_to(new_pos, 1000):
                    self.is_open = True
                else:
                    try:
                        self.shutter.MoveTo(new_pos, 1000)
                        # allow visible motion when MoveTo completes or starts
                        time.sleep(0.5)
                        self.is_open = True
                    except Exception as e:
                        print("MoveTo failed:", e)
                        self.is_open = False
        return self.state()


    def close(self):
        """Try to close the shutter

        Retruns
        ------------
        close : `bool`
            Whether the shutter is close
        """
        if self.connected:
            if self.stage and 'FW103' in self.stage.upper():
                if self._move_to(self.closed_angle, 2000):
                    self.is_open = False
                else:
                    try:
                        self.shutter.Home(2000)
                        time.sleep(0.5)
                        self.is_open = False
                    except Exception as e:
                        print("Home failed for close:", e)
            else:
                try:
                    self.shutter.Home(1000)
                    time.sleep(0.25)
                    self.is_open = False
                except Exception as e:
                    print("Home failed:", e)
        return self.state()


    def state(self):
        """Returns the shutter state

        Retruns
        ------------
        state : `bool`
            Whether the shutter is open
        """
        return self.is_open