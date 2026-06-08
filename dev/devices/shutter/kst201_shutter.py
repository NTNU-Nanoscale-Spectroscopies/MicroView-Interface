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
        """
        self.serial = serial
        self.enable = enable
        self.stage = stage
        self.connected = False
        self.is_open = False
        self.shutter = None
        self.open_angle = 60.0
        self.closed_angle = 0.0

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
            self.shutter = KCubeStepper.CreateKCubeStepper(self.serial)
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

            # Load motor configuration and APPLY the stage profile.
            #
            # The previous version assigned `device_config.Stage = ...` and
            # never called UpdateCurrentConfiguration(). `Stage` is read-only
            # on MotorConfiguration, so the assignment silently no-op'd; and
            # without UpdateCurrentConfiguration() the device kept whatever
            # profile was last written to the local Kinesis XML by some other
            # device's setup -- which is why MoveTo(60) was spinning many
            # revolutions: 60 was being interpreted as raw stepper units, not
            # degrees on the FW103.
            use_file_settings = DeviceConfiguration.DeviceSettingsUseOptionType.UseFileSettings
            device_config = self.shutter.LoadMotorConfiguration(self.shutter.DeviceID, use_file_settings)

            if self.stage and device_config is not None:
                applied_attr = None
                for attr in ("DeviceSettingsName", "StageType", "Stage"):
                    if hasattr(device_config, attr):
                        try:
                            setattr(device_config, attr, self.stage)
                            applied_attr = attr
                            break
                        except Exception as e:
                            print(f"KST201: setting {attr} failed:", e)
                if applied_attr:
                    print(f"KST201: set {applied_attr} = {self.stage}")
                    try:
                        device_config.UpdateCurrentConfiguration()
                        print("KST201: stage profile committed to device.")
                    except Exception as e:
                        print("KST201: UpdateCurrentConfiguration failed:", e)
                    time.sleep(0.5)
                else:
                    print(f"KST201: no settable stage property found on device_config for {self.stage!r}")

            # Pin homing/velocity/acceleration to the FW103M Kinesis profile
            # defaults so we never depend on whatever the K-cube currently has
            # persisted in its flash (which is what originally drifted and
            # caused homing to time out + open/close to take multiple revs).
            try:
                home_params = self.shutter.GetHomingParams()
                print(f"KST201: existing HomingVelocity = {home_params.Velocity}")
                home_params.Velocity = Decimal(200.0)
                self.shutter.SetHomingParams(home_params)
                print("KST201: HomingVelocity set to 200 deg/s")
            except Exception as e:
                print("KST201: SetHomingParams failed:", e)

            try:
                vel_params = self.shutter.GetVelocityParams()
                print(f"KST201: existing MaxVelocity = {vel_params.MaxVelocity}, Acceleration = {vel_params.Acceleration}")
                vel_params.MaxVelocity = Decimal(1260.0)
                vel_params.Acceleration = Decimal(25000.0)
                self.shutter.SetVelocityParams(vel_params)
                print("KST201: MaxVelocity set to 1260 deg/s, Acceleration to 25000 deg/s^2")
            except Exception as e:
                print("KST201: SetVelocityParams failed:", e)

            try:
                if hasattr(self.shutter, "Home"):
                    self.shutter.Home(60000)
                    self.is_open = False
                    try:
                        print(f"KST201: Homed after connect. Position = {self.shutter.Position}")
                    except Exception:
                        print("KST201: Homed after connect.")
            except Exception as e:
                print("KST201: Home after connect failed:", e)

            self.connected = True
            if self.enable:
                self.open()
            else:
                self.close()
            self.state()

        except Exception as e:
            print("KST201 connect error:", e)
            traceback.print_exc()
            self.connected = False
        return self.connected

    def disconnect(self):
        """Try to cleanly terminate communication with the device"""
        if self.connected and self.shutter is not None:
            try:
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

    def _is_fw103(self):
        return self.stage and "FW103" in self.stage.upper().replace("/", "")

    def _safe_fw103_target(self, target):
        try:
            target = float(target)
        except Exception:
            return None
        if 0.0 <= target <= 360.0:
            return target
        print(f"KST201: refusing FW103 target outside 0..360 degrees: {target}")
        return None

    def _move_to(self, target, timeout=1000):
        """Move to an absolute position using the stable KCube MoveTo API."""
        if self.shutter is None:
            return False

        if self._is_fw103():
            target = self._safe_fw103_target(target)
            if target is None:
                return False

        try:
            dec_target = Decimal(float(target))
        except Exception:
            dec_target = target

        try:
            self.shutter.MoveTo(dec_target, timeout)
            time.sleep(0.25)
            try:
                print(f"KST201: MoveTo({float(target):.3f}) -> Position = {self.shutter.Position}")
            except Exception:
                pass
            return True
        except Exception as e:
            print("KST201 MoveTo failed:", e)
            return False

    def open(self):
        """Try to open the shutter

        Retruns
        ------------
        open : `bool`
            Whether the shutter is open
        """
        if self.connected:
            if self._is_fw103():
                ok = self._move_to(self.open_angle, 30000)
            else:
                ok = self._move_to(5.0, 5000)
            self.is_open = bool(ok)
        return self.state()

    def close(self):
        """Try to close the shutter

        Retruns
        ------------
        close : `bool`
            Whether the shutter is close
        """
        if self.connected:
            if self._is_fw103():
                if self._move_to(self.closed_angle, 30000):
                    self.is_open = False
            else:
                try:
                    self.shutter.Home(30000)
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
