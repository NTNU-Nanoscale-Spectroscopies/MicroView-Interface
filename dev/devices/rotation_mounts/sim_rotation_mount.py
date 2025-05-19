import threading
from datetime import *
from dev.debugHelp import debugp
from dev.devices.rotation_mounts.auto_calibration import AutoCalibrate
from dev.devices.rotation_mounts.rotation_mount import MyRotationMount
import time

class MySimRotationMount(MyRotationMount):
    """Class for creating an object that communicates with and controls a stage-type device"""

    def __init__(self, name, serial, associated_spectrometer=None, enable=False):
        """Initialize a new rotation mount object with communication parameters.

        Parameters
        ------------
        name : `str`
            Visible name of this device in the graphical interface.
        serial : `str`
            The unique device serial number enabling communication.
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
            self.connected = True
            self.home()

        return self.connected

    def disconnect(self):
        """Terminate communication with the device cleanly."""
        if self.connected:
            self.connected = False

    def set_absolute_angle(self, angle):
        """Set the rotation mount to a specified absolute angle after correction."""
        debugp("Rotation Mount", f"Set absolute angle {angle} - real:{self.get_corrected_angle(angle)}")
        
    def set_relative_angle(self, angle):
        """Shift the rotation mount by a relative angle after correction."""
        debugp("Rotation Mount", f"Set relative angle {angle} - real:{self.get_corrected_angle(angle)}")
        
    def home(self):
        """Move the rotation mount to its home position."""
        debugp("Rotation Mount", f"Homed")

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
            #self.notification(f"No associated spectrometer", color="#8e0101")
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
        self.auto_calibrate.get_ninety_angle()
        self.spectrometer.acquire_save_data = 0
    
    def get_corrected_angle(self, angle):
        """Calculate the corrected angle based on calibration adjustments."""
        return (angle - self.corrected_angle) % 360
    
    
        
    def __repr__(self):
        return f"{self.name}, serial : {self.serial}"