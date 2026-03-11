from datetime import *
import threading
import time
from tkinter import Toplevel
# elliptec is an optional hardware library; allow the module to be imported
# even when the library isn't installed (e.g. during development).
try:
    import elliptec
except ImportError:
    elliptec = None
from CTkToolTip import *
import numpy as np
from dev.devices.rotation_mounts.auto_calibration import AutoCalibrate
import os


class MyRotationMount():
    """Class for creating an object that communicates with and controls a stage-type device"""

    def __init__(self, name, serial, associated_spectrometer=None, enable=False):
        """Initialize a new rotation mount object with communication parameters.

        Parameters
        ------------
        name : `str`
            Visible name of this device in the graphical interface.
        serial : `str`
            The unique device serial number enabling communication check the windows device manager to find corresponding COM ports .
        associated_spectrometer : optional
            A spectrometer that may be linked to this device to allow auto calibration.
        enable : `bool`, optional
            Allows or prevents the device from starting once it is connected. False by default.
        """
        self.name = name
        self.serial = serial
        self.enable = enable
        self.connected = False
        self.is_running = False
        self.controller = None
        self.rotation_mount = None
        self.spectrometer = None
        self.associated_spectrometer = associated_spectrometer
        self.spectrometer_frame = None
        self.is_auto_calibrate = False
        self.auto_calibrate = None
        self.corrected_angle = 0
        self.sweep_folder_name = "Sweep"
        

    def connect(self):
        """
        Establish communication with the rotation mount device.

        Returns
        ------------
        `bool`
            Whether communication is successfully established.
        """

        if self.connected == False:
            try:
                self.controller = elliptec.Controller(self.serial)
                self.rotation_mount = elliptec.Rotator(self.controller)
                self.home()
                self.connected = True
            except:
                return False
        
        return self.connected

    def disconnect(self):
        """Terminate communication with the device cleanly."""
        if self.connected:
            self.controller.close_connection()
            self.connected = False

    def set_absolute_angle(self, angle):
        """Set the rotation mount to a specified absolute angle after correction."""
        self.rotation_mount.set_angle(self.get_corrected_angle(angle))
        
    def set_relative_angle(self, angle):
        """Shift the rotation mount by a relative angle after correction."""
        self.rotation_mount.shift_angle(self.get_corrected_angle(angle))
        
    def home(self):
        """Move the rotation mount to its home position."""
        self.rotation_mount.home()
        
    def setup_auto_calibration(self, spectrometer, spectrometer_frame, set_unavailable, set_available):
        """
        Configure auto-calibration with a spectrometer and status update functions.

        Parameters
        ------------
        spectrometer : object
            The spectrometer associated with the rotation mount.
        set_unavailable : function
            Function to set the device as unavailable during calibration.
        set_available : function
            Function to set the device as available after calibration.
        """
        self.spectrometer = spectrometer
        self.spectrometer_frame = spectrometer_frame
        self.is_auto_calibrate = True
        
        self.auto_calibrate = AutoCalibrate(self, spectrometer, spectrometer_frame)
        self.set_unavailable = set_unavailable
        self.set_available = set_available
        
    def start_auto_calibration(self):
        """Start the auto-calibration process in a separate thread."""
        if not self.is_auto_calibrate:
            #TODO Notification
            print("No associated spectrometer")
            return
        
        self.corrected_angle = 0
        self.spectrometer.acquire_save_data = 1
        thread = threading.Thread(target=self.threaded_auto_calibration, daemon=True)
        thread.start()
        self.set_unavailable("Autocalibrating...")
        
    def threaded_auto_calibration(self):
        """Execute the auto-calibration routine in a separate thread."""
        self.auto_calibrate.start(self.set_unavailable)
        self.set_available()
        self.corrected_angle = self.auto_calibrate.get_zero_angle()
        self.spectrometer.acquire_save_data = 0
        
    def get_corrected_angle(self, angle):
        """Calculate the corrected angle based on calibration adjustments."""
        
        return (angle + self.corrected_angle) % 360

    def set_settings(self, folder_name, wavelength):
        self.auto_calibrate.set_settings(folder_name, wavelength)


    # New input variables
    def start_sweep(self, step_angle, sweep_folder=None, start_angle=0, stop_angle=360):
        """
        Start a sweep from start_angle to stop_angle using given step_angle.

        Parameters
        -----------
        step_angle : int
            Step increment in degrees (must be > 0)
        sweep_folder : str or None
            Optional folder name for saving
        start_angle : int
            Start angle in degrees (0-359). Default 0.
        stop_angle : int
            Stop angle in degrees (1-360). Default 360 means full circle.
        """
        # We'll perform explicit saves inside the sweep; disable the spectrometer's automatic
        # save_queue-based saving to avoid duplicated files ("relative sweep").
        try:
            self.spectrometer.auto_save_enabled = False
        except Exception:
            pass
        self.spectrometer.acquire_save_data = 1
        thread = threading.Thread(target=lambda: self.start_threaded_sweep(step_angle, sweep_folder, start_angle, stop_angle), daemon=True)
        thread.start()
        self.set_unavailable(f"Sweeping...")        

    # New input variables    
    def start_threaded_sweep(self, step_angle, sweep_folder=None, start_angle=0, stop_angle=360):

        if sweep_folder is not None:
            self.sweep_folder_name = sweep_folder

        # Normalize inputs
        try:
            step = int(step_angle)
            if step <= 0:
                raise ValueError("Step angle must be > 0")
        except Exception:
            # Restore spectrometer save behavior on error
            try:
                self.spectrometer.auto_save_enabled = True
            except Exception:
                pass
            self.set_available()
            self.spectrometer.acquire_save_data = 0
            return

        start = int(start_angle) % 360
        # Treat stop_angle == 360 as full-circle sentinel
        stop_raw = int(stop_angle)
        stop = 360 if stop_raw == 360 else (stop_raw % 360)

        # Build list of angles to visit (inclusive of stop when stop==360)
        angles = []
        if stop == 360:
            # full circle: go from start to start+360-step
            total_steps = (360 + (step - 1)) // step
            for i in range(total_steps):
                angles.append((start + i * step) % 360)
        else:
            # Non-wrap case
            if start <= stop:
                current = start
                while current <= stop:
                    angles.append(current % 360)
                    current += step
            else:
                # Wrap-around case: start > stop
                current = start
                # go from start up to 359
                while current < 360:
                    angles.append(current % 360)
                    current += step
                # then from 0 up to stop
                current = 0
                while current <= stop:
                    angles.append(current % 360)
                    current += step

        date = f"{datetime.now():%H.%M.%S}"

        total = len(angles)
        for idx, angle in enumerate(angles):
            real_angle = angle % 360
            self.set_absolute_angle(real_angle)
            # Wait for spectrometer integration time (integration_time is in microseconds previously used?)
            time.sleep((self.spectrometer.integration_time / 1_000_000) + 0.3)
            # Get measurement
            try:
                wavelengths, intensities = self.spectrometer.chart_queue.get(timeout=5)
            except Exception:
                # If no data, skip this angle
                continue

            self.set_unavailable(f"Measuring {idx+1}/{total}\nAngle :{angle}°")

            file_path = self.spectrometer_frame.file_system.get_spectrometer_directory(self.spectrometer.integration_time, self.spectrometer.name, self.sweep_folder_name)
            file_path = file_path.replace("#", f"{idx}_{angle}deg_").replace("@", date).replace("$", self.spectrometer.name.split("-")[-1])

            self.spectrometer_frame.single_save(
                f"{file_path}", wavelengths, intensities,
                True, False, self.spectrometer_frame.split - 1, False
            )
 
        # Notify user where sweep files were saved (folder)
        try:
            directory = os.path.dirname(file_path) if 'file_path' in locals() and file_path else None
            if directory:
                # Use spectrometer_frame.notification to show the standard notification UI
                self.spectrometer_frame.notification("Sweep completed", f"Saved to {directory}", "#1a8300", path=directory)
        except Exception:
            # fail silently to avoid breaking sweep completion
            pass

        # Restore spectrometer auto-save behavior and clear acquire flag
        try:
            self.spectrometer.auto_save_enabled = True
        except Exception:
            pass
        self.set_available()
        self.spectrometer.acquire_save_data = 0


    def __repr__(self):
        return f"{self.name}, serial : {self.serial}"
