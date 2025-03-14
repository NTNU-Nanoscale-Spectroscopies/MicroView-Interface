import elliptec

from dev.debugHelp import debugp
from dev.devices.rotation_mounts.rotation_mount import MyRotationMount


class MySimRotationMount(MyRotationMount):
    """Class for creating an object that communicates with and controls a stage-type device"""

    def __init__(self, name, serial, enable=False):
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
        debugp("Rotation Mount", f"Set absolute angle {angle}")
        
    def set_relative_angle(self, angle):
        debugp("Rotation Mount", f"Set relative angle {angle}")
        
    def home(self):
        debugp("Rotation Mount", f"Homed")

    def __repr__(self):
        return f"{self.name}, serial : {self.serial}"


"""

import elliptec

# Initialize the controller and rotation mount (Replace 'COM3' with your actual port)
controller = elliptec.Controller('COM3')
rot_mount = elliptec.Rotator(controller)

# Retrieve device information
print("Device Info:", rot_mount.get('info'))

# Home the rotation mount (required before any movement)
rot_mount.home()
print("Homing completed.")

# Move to an absolute position (e.g., 90 degrees)
rot_mount.move_absolute(90)
print("Moved to 90 degrees.")

# Move relative by a certain angle (e.g., +45 degrees)
rot_mount.move_relative(45)
print("Moved 45 degrees forward.")

# Move counterclockwise (-30 degrees)
rot_mount.move_relative(-30)
print("Moved 30 degrees backward.")

# Query the current position
current_pos = rot_mount.get('position')
print(f"Current Position: {current_pos} degrees")

# Get device status
status = rot_mount.get('status')
print("Device Status:", status)

# Stop any movement (if needed)
rot_mount.stop()
print("Rotation stopped.")

# Set velocity (if adjustable)
rot_mount.set('velocity', 5)
print("Velocity set to 5.")

# Reset the device
rot_mount.reset()
print("Device reset.")

# Disconnect the controller
controller.close()
print("Controller closed.")


"""