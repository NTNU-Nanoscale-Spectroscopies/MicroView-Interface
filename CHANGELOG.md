# Changelog

## [1.1.1] - 2024-12-16
### <span style="color:green"> Added </span>
- Dev : Added a button to resize the camera
- Dev : Added a popup to configure specific application variables
### <span style="color:#006bd2"> Fixed </span>
- Dev : Improved styling management for the `open/close` shutters button
- Dev : Updated the `start/stop` buttons upon connection
- Dev : When a popup opens, it is now displayed in the foreground
### <span style="color:#d6a600"> Changed </span>
- Dev : Standardized image sizes in the `images` folder (64x64 for icons).
- Dev : Updated the "backup name" label in the `directory_frame`
- Dev : Improved the item listing system in the `setup_frame` file
- Dev : Renamed the `MyPlatform` class to `MyStage`

## [1.1.0] - 2024-12-05
### <span style="color:green"> Added </span>
- Dev : Added the `__repr__` method to missing device classes
- Dev : Reorganized shutter functionalities
- Dev : Automatic opening of shutters at startup and closing at script termination
- Dev : Simplified configuration in the `main.py` file
- Dev : Restructured the `setup_frame.py` file for better organization
- Dev : Linked the `MyShutter` class with the `MyLaser` class
- Dev : Added required Kinesis DLLs
### <span style="color:#d6a600"> Changed </span>
- Dev : Tools are now connected only after all graphical elements are fully initialized
- Dev : Improved the build system to generate only the executable without including unnecessary files
### <span style="color:purple"> Issues </span>
- Dev : The `enable` parameter allows tools to start as soon as they are connected, but certain graphical elements do not update accordingly
- Dev : The `open/close` button for shutters does not update automatically when tools are connected or disconnected
- Dev : If multiple spectrometers are present and the first one is not connected, no attempt is made to connect the others
### <span style="color:#bf2a2a"> Removed </span>
- Dev : Removed the `whitelight.py` file and its associated class
- Dev : Removed the `devices.py` file and its associated class

## [1.0.4] - 2024-12-03
### <span style="color:green"> Added </span>
- Dev : Adds a connection to the shutter device
- Dev : White light shutter control now possible

## [1.0.3] - 2024-11-29
### <span style="color:green"> Added </span>
- Dev : It is now possible to display reflectance or transmittance
- Dev : It is now possible to save reflectance or transmittance data

## [1.0.2] - 2024-11-29
### <span style="color:green"> Added </span>
- Dev : Adds the ability to save light and dark references
### <span style="color:#bf2a2a"> Removed </span>
- Dev : Remove white calibration button from the camera
- Dev : Remove software close notification

## [1.0.1] - 2024-11-28
### <span style="color:green"> Added </span>
- Dev : It is now possible to change spectrometer during runtime
- Dev : Added a variable to adjust black correction based on the spectrometer used
- Dev : Updating switches based on the connection status of the devices
- Dev : When closing, the software transitions to hidden mode and continues running in the background until fully closed

## [0.3.4] - 2024-11-27
### <span style="color:green"> Added </span>
- Dev : You can now easily create an executable with the :
    ````bash
    pyinstaller microview.spec
    ````
### <span style="color:#006bd2"> Fixed </span>
- Dev : Troubleshooting when closing a program if a certain element does not exist

## [0.3.3] - 2024-11-20
### <span style="color:green"> Added </span>
- Dev : Add static white balance
- Dev : The connection with the devices is now properly terminated before the program fully closes
- Dev : Devices can now be connected/disconnected by the setup frame
### <span style="color:#006bd2"> Fixed </span>
- Dev : Camera finally closes properly
- Dev : The end-of-execution bug has been resolved by replacing the pyplot library with the figure library
- Dev : Fix a ghost print for the spectrometer acquisition
- Dev : Fix the second notification shift

## [0.3.2] - 2024-11-19
### <span style="color:green"> Added </span>
- Dev : Adding optimisation, spectrometer data can now be saved at maximum speed
- Dev : In the advanced save section, entries are retained
- Dev : Adding a delay before starting up devices to smooth window creation
### <span style="color:#006bd2"> Fixed </span>
- Dev : Spectrometer dark correction activated to remove 1500 counts offset
### <span style="color:#d6a600"> Changed </span>
- Dev : In the advanced save section, save interval is replaced by number of scans

## [0.3.1] - 2024-11-08
### <span style="color:green"> Added </span>
- Dev : Multiple files can be selected at the same time for overlay graphics
- Dev : Adding some optimisation (cam: 10Hz, spectro: 50Hz, save: 50Hz)

## [0.3.0] - 2024-11-06
### <span style="color:green"> Added </span>
- Dev : Add legend to chart
- Dev : Spectrometer starts when advanced save is called
- Dev : Spectrometer stops when overlaid chart is called
### <span style="color:#d6a600"> Changed </span>
- Dev : Advanced save function is now asynchronous
- Dev : Backup files names now contain the time and iteration number
- Dev : The data queue is now clear when the integration time changes

## [0.2.4] - 2024-11-04
### <span style="color:green"> Added </span>
- Dev : Spectrometer data can now be overlaid by previous data
- Dev : Advanced save popup
- Dev : Synchronous advanced save function

## [0.2.3] - 2024-10-31
### <span style="color:green"> Added </span>
- Dev : Notification size now resized according to content
### <span style="color:#006bd2"> Fixed </span>
- Dev : Notification positioning now takes screen scale into account
### <span style="color:#d6a600"> Changed </span>
- Dev : File incrementation is replaced by hours
- Dev : The management of integration time by the user is now in milliseconds
### <span style="color:purple"> Issues </span>
- Dev : Notifications are not attached to the main window
### <span style="color:#bf2a2a"> Removed </span>
- Dev : The smart placeholder system has been removed, as file increment has been replaced by time.

## [0.2.2] - 2024-10-23
### <span style="color:green"> Added </span>
- Dev : Adding autofill to the quick setup frame
- Dev : Adding auto hide and show the scrollbar of the quick setup frame
- Dev : Adding a check on the validity of the spectrometer acquisition time entry
- Dev : Adding disable of quick setup widgets if the switch is not selected
### <span style="color:#d6a600"> Changed </span>
- Dev : Ingrement number in backup filename has been replaced by hour, minutes, seconds

## [0.2.1] - 2024-10-18
### <span style="color:#d6a600"> Changed </span>
- Design : Reorganization of devices folder
- Design : Rename frame folder to widget
- Dev : General clean-up
- Dev : Updating smart placeholder to predict next filename

## [0.2.0] - 2024-10-18
### <span style="color:green"> Added </span>
- Dev : Adding backup notification system
- Dev : Adding smart placeholder

## [0.1.4] - 2024-10-14
### <span style="color:green"> Added </span>
- Design : Implementation of the backup directory nomenclature
- Dev : Camera and spectrometer backup system
### <span style="color:#006bd2"> Fixed </span>
- Dev : Entry color and ploceholder until selection
### <span style="color:#d6a600"> Changed </span>
- Dev : Redesign of spectrometer acquisition to make it generic
### <span style="color:purple"> Issues </span>
- Dev : Phantom programming line, print needed for spectrometer aquisition

## [0.1.3] - 2024-10-08
### <span style="color:green"> Added </span>
- Dev : Adding spectrometer connection
- Dev : Spectrometer measurement display added
### <span style="color:#d6a600"> Changed </span>
- Design : Reorganization of dev folders and files
### <span style="color:purple"> Issues </span>
- Dev : Impossible to return to menu (cause devices must be stopped)

## [0.1.2] - 2024-10-07
### <span style="color:green"> Added </span>
- Design : New classes for frames
- Dev : Adding directory items
- Dev : Redesign of MyCamera class to return an image object and no more a canvas
- Dev : Refactored CameraFrame class to create a canvas in this frame
- Dev : Added methods to make images resizable
### <span style="color:#006bd2"> Fixed </span>
- Dev : The words on the label are not cut on the nanolab laptop
- Dev : Camera images can now be resized
### <span style="color:purple"> Issues </span>
- Dev : There are sometimes a few steps involved in rescaling camera images.
### <span style="color:#bf2a2a"> Removed </span>
- Dev : The MyImageManager class has been deleted, but the load_image method has been retained.

## [0.1.1] - 2024-10-01
### <span style="color:green"> Added </span>
- Dev : Choice of microscope for dashbord access
- Dev : Selected microscope screen 
- Dev : Connection with camera device
- Dev : Live camera view in the camera frame
### <span style="color:purple"> Issues </span>
- Dev : The words on the label are cut off at the bottom.
- Dev : Need to resize the camera view

## [0.1.0] - 2024-09-27
### <span style="color:green"> Added </span>
- Design : Fields for selecting directory and file name
- Design : Main parameters for each device
- Design : First model of project class
- Dev : Creating the environment
- Dev : Implementing the application and microscope classes
- Dev : Makeing the menu screen with easy microscopes adding and responsive screen
- Dev : Image class added to make things easier
- Dev : Dark and light mode added

## [0.0.2] - 2024-09-24
### <span style="color:green"> Added </span>
- Design : Open windows to access the control panel of the selected device
### <span style="color:#d6a600"> Changed </span>
- Design : Config table has changed to a dashboard

## [0.0.1] - 2024-09-23
### <span style="color:green"> Added </span>
- Design : First application design
- Design : Config table for each device

## [0.0.0] - 2024-09-16
### <span style="color:gray"> Descovering </span>