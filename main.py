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
# - Oliver MINEAU  
# - Eirik LU                                                                  #
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
#    - `MyRotationMount(name, serial, linked_spectrometer_serial, enable)`
#
#   Some components have their own simulator to assist with development or 
#    debugging when not in the lab :
#    - `MySimCamera(name, serial, enable)`
#    - `MySimSpectrometer(name, serial, enable, dark_correction, integration_time)`
#    - `MySimRotationMount(name, serial, linked_spectrometer_serial, enable)`
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
from dev.devices.filter_wheel.filterwheel import MyFilterWheel
from dev.devices.filter_wheel.sim_filterwheel import MySimFilterWheel
from dev.devices.Stage.stage import MyStage
from dev.devices.Stage.sim_stage import MySimStage
from dev.devices.Stage.mcm301_stage import MyMCM301Stage
# power meter
from dev.devices.power_meter.power_meter import MyPowerMeter
from dev.devices.power_meter.sim_power_meter import MySimPowerMeter


# Define the application version
version = "V3.5.0"

# Set the size of the application's main window (width, height)
size = (2560,1440)

# Set the duration for which notifications will remain visible (in seconds)
visible_notif_time = 3

# Specify the directory where data backups will be saved
backup_directory = r"C:\Users\A068\Documents\Data\Default"
#backup_directory = r"C:\Users\el-ei\Documents\Masterproject\Backup data"

# Create an instance of a microscope setup 28939
# Remove 'Sim' from the class names to connect to real devices 
gm_microscope = MyMicroscope("Maria Goeppert Mayer",
    #MySpectrometer("Spectrometer", "xxxx", enable=True), #Need to implement Kymera spectrometer
    #MySpectrometer("Spectrometer-VIS", "QEP06226", enable=True, dark_correction=True, integration_time=100),
    #MySpectrometer("Spectrometer-NIR", "NQ51B1981", integration_time=50),
    MyCamera("Camera", "28939", enable=True),
    MyRotationMount("White-Light-Plzr", "11401261", "QEP06226", enable=False),
    MyRotationMount("Laser-Plzr", "11401263", "QEP06226", enable=False),
    MyRotationMount("Half Wave Plate", "11401317", "QEP06226", enable=False),
    MyShutter("White light - shutter", "26006167", enable=True, model="KST201", stage="FW103M"),
    MyShutter("Laser 750nm - shutter", "68801094", enable=False, model="KSC101"),
    MyShutter("Laser 550nm - shutter", "68800970", enable=False, model="KSC101"),
    MyFilterWheel("Filter wheel", "TP03125974-28787", enable=True),
    #MySimFilterWheel("Filter wheel (sim)", "SIM-000", enable=True),
    MyPowerMeter("Power meter", "PM16-401", enable=False, model="PM16-401"),
    #MySimPowerMeter("Power meter (sim)", "SIM-PM-000", enable=True, model="PM16-401"),
    MyMCM301Stage("Stage", "TP03349640-693520", slot=1, safety_limit_mm=3.0) #Different from LM stage
)


# Create an instance of a microscope setup
"""LM uses Thorlabs CCD camera 8051, serial number : 11499 - Connexion is different from GM camera
    Avaspec 3648 spectrometer - Connexion is different from Oceanview spectrometers
"""
lm_microscope = MyMicroscope("Lise Meitner",
    MySpectrometer("Spectrometer-VIS", "QEP06226", enable=True, dark_correction=True, integration_time=100),
    MySpectrometer("Spectrometer-NIR", "NQ51B1981", integration_time=50),
    MyCamera("Camera", "11499", enable=True),
    MyRotationMount("White-Light-Plzr", "11401818", "QEP06226", enable=False),
    #MyShutter("White light - shutter", "26006167", enable=True, model="KST201", stage="FW103M"),
    #MyShutter("Laser 750nm - shutter", "68801094", enable=False, model="KSC101"),
    #MyFilter("Filter 12", "xxxx"),
    #MySimStage("Sim Stage", "SIM-000"),
    MyStage("Stage", "5", stage_type="ZFM2020", channel=2, safety_limit_mm=3.0),
)

raman_microscope = MyMicroscope("Raman Microscopy",
    MyCamera("Camera", "28939", enable=True),
    MyRotationMount("White-Light-Plzr", "11401261", "QEP06226", enable=False),
    MyRotationMount("Laser-Plzr", "11401263", "QEP06226", enable=False),
    MyRotationMount("Half Wave Plate", "11401317", "QEP06226", enable=False),
    MyShutter("White light - shutter", "26006167", enable=True, model="KST201", stage="FW103M"),
    MyShutter("Laser 750nm - shutter", "68801094", enable=False, model="KSC101"),
    MyShutter("Laser 550nm - shutter", "68800970", enable=False, model="KSC101"),
    MyFilterWheel("Filter wheel", "TP03125974-28787", enable=True),
    #MySimFilterWheel("Filter wheel (sim)", "SIM-000", enable=True),
    MyPowerMeter("Power meter", "PM16-401", enable=False, model="PM16-401"),
    #MySimPowerMeter("Power meter (sim)", "SIM-PM-000", enable=True, model="PM16-401"),
    MyMCM301Stage("Stage", "TP03349640-693520", slot=1, safety_limit_mm=3.0) #Different from LM stage
)

# Create the main application instance
app = MyApp(version, size, visible_notif_time, backup_directory, gm_microscope, lm_microscope, raman_microscope)

# Close the PyInstaller splash screen now that the GUI is ready
try:
    import pyi_splash          # only available in frozen (PyInstaller) builds
    pyi_splash.close()
except ImportError:
    pass

# Start the application loop
app.mainloop()