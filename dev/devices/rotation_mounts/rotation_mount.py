from datetime import *
import threading
import time
from tkinter import Toplevel
import elliptec
from CTkToolTip import *
import numpy as np
from dev.devices.rotation_mounts.auto_calibration import AutoCalibrate


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
        
        return (angle - self.corrected_angle) % 360

    def set_settings(self, folder_name, wavelength):
        self.auto_calibrate.set_settings(folder_name, wavelength)
            
    def start_sweep(self, step_angle, sweep_folder=None):
        self.spectrometer.acquire_save_data = 1
        thread = threading.Thread(target=lambda: self.start_threaded_sweep(step_angle, sweep_folder), daemon=True)
        thread.start()
        self.set_unavailable(f"Sweeping...")        
        
    def start_threaded_sweep(self, step_angle, sweep_folder=None):

        if sweep_folder != None:
            self.sweep_folder_name = sweep_folder
        
        date = f"{datetime.now():%H.%M.%S}"
        for angle in range(0, 360, step_angle):
            print(angle)
            real_angle = angle % 360
            self.set_absolute_angle(real_angle)
            time.sleep((self.spectrometer.integration_time / 1_000_000) + 0.5)
            wavelengths, intensities = self.spectrometer.chart_queue.get()
            
            self.set_unavailable(f"Measuring {int(angle/step_angle)}/{round(360/step_angle)}\nAngle :{angle}°")
            
            file_path = self.spectrometer_frame.file_system.get_spectrometer_directory(self.spectrometer.integration_time, self.spectrometer.name, self.sweep_folder_name)
            file_path = file_path.replace("#", f"{int(angle/step_angle)}_{angle}deg_").replace("@", date).replace("$", self.spectrometer.name.split("-")[-1])

            self.spectrometer_frame.single_save(
                f"{file_path}", wavelengths, intensities,
                True, False, self.spectrometer_frame.split - 1, False
            )
            print(f"Saved to {file_path}")

        self.set_available()

    def __repr__(self):
        return f"{self.name}, serial : {self.serial}"
    