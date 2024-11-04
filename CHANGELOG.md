# Changelog

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