v3.0.3

    Added:
        Open folder button
        White light shutter
    
    Removed:

    Bugs:
        Sweep data duplication

v3.0.2

    Added:
        Advanced save brought back
        Start/stop angle input added for sweep
    
    Removed:

    Bugs:
        No fixes yet

v3.0.0

    Added :
        Automatic sweep 
        Automatic calibration routine (First pass every 10degrees > Moving average > Get angle of Max intensity > Second pass every 1 degree around the max > Moving average > Calibrated)

    Removed :

    Bugs : 
        Random crash hasn't been fixed but never seems to appear...

v2.1.7

    Added :
        Automatic calibration
        Calibration data is saved in the current experiment folder
        Light,dark references are automatically saved 

    Removed :
        Advanced save

    Bugs : 
        Random crash hasn't been fixed

v2.0.6

    Added :
        All spectrometer related features work:
        Clicking saved notification opens the folder where the file was saved
        Import chart opens the correct folder
        Light and Dark references are saved for all connected spetrometers at the same time

    Removed :

    Bugs :
        

v2.0.4

    Added :
        Can disconnect/connect spectrometers

    Removed :

    Bugs :
        Disconnecting both spectrometers doesnt allow you to reconnect them (working on that)
        All file saving system doesnt work (work on that next)

v2.0.3

    Added :
        Can swap spectrometer view

    Removed :
        Side by side spectrometer view because of lag (need to optimise threads somehow)

    Bugs :
        Disconnecting spectrometers doesnt work
        All file saving system doesnt work
    