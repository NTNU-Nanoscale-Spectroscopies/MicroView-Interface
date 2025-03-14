###############################################################################
#                                                                             #
#                             MicroView - interface                           #
#                                                                             #
###############################################################################
#                                                                             #
# Description:                                                                #
# This project aims to centralize microscope devices and functionalities      #
# within a single software platform. The aim is to simplify their management, #
# while improving the efficiency and productivity of research activities.     #
#                                                                             #
# Supervised by :                                                             #
# - Angelos XOMALIS                                                           #
# - Julia LÖVGREN                                                             #
#                                                                             #
# Developpers :                                                               #
# - Noah JACOB                                                                #
# - Oliver MINEAU                                                             #
#                                                                             #
###############################################################################

# -------------------------------------------------------------------------
# How to create a microscope:
#
# 1. Use the `MyMicroscope` class, providing:
#    - A name for the microscope (str).
#    - A list of components: `MyCamera`, `MySpectrometer`, `MyShutter`, 
#      `MyFilter` or `MyStage`.
#
# 2. Each component has its own constructor and specific parameters, for example:
#    - `MyCamera(name, serial, enable)`
#    - `MySpectrometer(name, serial, enable, dark_correction, integration_time)`
#    - `MyShutter(name, serial, enable, model)`
#    - `MyFilter(name, serial, enable)`
#    - `MyStage(name, serial, enable)`
#
#   Some components have their own simulator to assist with development or 
#    debugging when not in the lab :
#    - `MySimCamera(name, serial, enable)`
#    - `MySimSpectrometer(name, serial, enable, dark_correction, integration_time)`
#
#   Parameter definition :
#    - `name` (str): The name of the device.
#    - `serial` (str): The unique serial number for the device.
#    - `enable` (bool): Whether the device is activated after connection (True/False).
#    - `dark_correction` (bool): Whether to apply dark correction (True/False).
#    - `integration_time` (int): Default integration time in milliseconds.
#    - `model` (str): The model name of the shutter.
#
# 3. Combine all components into a single `MyMicroscope` instance.
#   If a parameter is not added, then its default value is None or False.
#
#   Example:
#   new_microscope = MyMicroscope(
#       "My new microscope",
#       MyCamera("Camera", "12345", enable=True),
#       MySpectrometer("Spectrometer", "67890", enable=True, integration_time=100),
#       MyShutter("Shutter 1", "09876", enable=False, model="KSC101")
#       MyShutter("Shutter 2", "54321", model="KST201")
#   )
#
# 4. After defining microscopes, they can be passed into `MyApp` to initialize 
#   the main application and start its interface.
#
#   Example:
#   app = MyApp(version, size, visible_notif_time, backup_directory, new_microscope)
#   app.mainloop()
# -------------------------------------------------------------------------



# Import necessary components from the application's module
from dev.application import *
from dev.devices.camera.sim_camera import MySimCamera
from dev.devices.rotation_mounts.rotation_mount import MyRotationMount
from dev.devices.rotation_mounts.sim_rotation_mount import MySimRotationMount
from dev.devices.sim_spectrometer import MySimSpectrometer


# Define the application version
version = "V2.1.2"

# Set the size of the application's main window (width, height)
size = (1200,700)

# Set the duration for which notifications will remain visible (in seconds)
visible_notif_time = 3

# Specify the directory where data backups will be saved
backup_directory = r"C:\Users\A068\Documents\Data\Default"
#backup_directory = r"C:\Users\olive\OneDrive\Documents\Data\Default"

# Create an instance of a microscope setup
gm_microscope = MyMicroscope("Maria Goeppert Mayer",
    MyCamera("Camera", "28939", enable=True),
    MySpectrometer("Spectrometer-VIS", "QEP06226", enable=True, dark_correction=True, integration_time=100),
    MySpectrometer("Spectrometer-NIR", "NQ51B1981", integration_time=50),
    MyRotationMount("Rotation Mount", "COM3", enable=False),
    MyShutter("White light - shutter", "26006167", enable=True, model="KST201"),
    MyShutter("Laser 750nm - shutter", "68801094", enable=False, model="KSC101"),
    MyShutter("Laser 550nm - shutter", "68800970", enable=False, model="KSC101"),
    MyFilter("Filter 12", "xxxx"),
    MyStage("Stage", "xxxx"))

# Create an instance of a microscope setup
lm_microscope = MyMicroscope("Lise Meitner",
    MySpectrometer("Spectrometer", "xxxx", enable=True),
    MyCamera("Camera", "xxxx", enable=True),
    MyShutter("White light - shutter", "26006167", enable=True, model="KST201"),
    MyShutter("Laser 750nm - shutter", "68801094", enable=False, model="KSC101"),
    MyFilter("Filter 12", "xxxx"),
    MyStage("Stage", "xxxx"))


# Create the main application instance
app = MyApp(version, size, visible_notif_time, backup_directory, gm_microscope, lm_microscope)

# Start the application loop
app.mainloop()