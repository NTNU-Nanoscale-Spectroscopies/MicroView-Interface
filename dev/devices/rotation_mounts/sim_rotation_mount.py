import threading
import elliptec

from dev.debugHelp import debugp
from dev.devices.rotation_mounts.auto_calibration import AutoCalibrate
from dev.devices.rotation_mounts.rotation_mount import MyRotationMount


class MySimRotationMount(MyRotationMount):
    """Class for creating an object that communicates with and controls a stage-type device"""

    def __init__(self, name, serial, associated_spectrometer=None, enable=False):
        """Create a new Stage object for easy communication with the device concerned

        Parameters
        ------------
        name : `str`
            Visible name of this device in the graphical interface
        serial : `str`
            The unique device serial number enabling communication
        enable : `bool`, optional
            Allows or prevents the device from starting once it is connected. False by default
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
        self.is_auto_calibrate = False
        self.auto_calibrate = None
        self.corrected_angle = 0
        
    def connect(self):
        """
        The purpose of this method is to initiate communication with the rotation mount device

        Returns
        ------------
        connect : `bool`
            Whether communication is established
        """

        if self.connected == False:
            self.connected = True
            self.home()

        return self.connected

    def disconnect(self):
        """Not available.
        The purpose of this method is to cleanly terminate communication with the device
        """
        if self.connected:
            self.connected = False

    def set_absolute_angle(self, angle):
        debugp("Rotation Mount", f"Set absolute angle {angle} - real:{self.get_corrected_angle(angle)}")
        
    def set_relative_angle(self, angle):
        debugp("Rotation Mount", f"Set relative angle {angle} - real:{self.get_corrected_angle(angle)}")
        
    def home(self):
        debugp("Rotation Mount", f"Homed")

    def setup_auto_calibration(self, spectrometer, set_unavailable, set_available):
        self.spectrometer = spectrometer
        self.is_auto_calibrate = True
        
        self.auto_calibrate = AutoCalibrate(self, spectrometer)
        self.set_unavailable = set_unavailable
        self.set_available = set_available
        
    def start_auto_calibration(self):
        
        if not self.is_auto_calibrate:
            #TODO Notification
            print("No associated spectrometer")
            return
        
        thread = threading.Thread(target=self.threaded_auto_calibration, daemon=True)
        thread.start()
        self.set_unavailable()
        
    def threaded_auto_calibration(self):
        self.auto_calibrate.start()
        self.set_available()
        self.corrected_angle = self.auto_calibrate.get_zero_angle()
        self.auto_calibrate.get_ninety_angle()
    
    def get_corrected_angle(self, angle):
        return (angle - self.corrected_angle) % 360
        
    def __repr__(self):
        return f"{self.name}, serial : {self.serial}"