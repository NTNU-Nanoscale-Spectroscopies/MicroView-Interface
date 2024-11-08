from dev.application import *

gm_microscope = MyMicroscope("Maria Goeppert Mayer",
    gm_camera = MyCamera("Camera CS165MU", "28939"),
    gm_spectrometer = MySpectrometer("Spectrometer", "QEP06226"),
    gm_white_light = MyWhiteLight("White light", "xxxx"),
    gm_laser_750 = MyLaser("Laser 750nm", "xxxx"),
    gm_laser_550 = MyLaser("Laser 550nm", "xxxx"),
    gm_filter_12 = MyFilter("Filter 12", "xxxx"),
    gm_platform = MyPlatform("Platform", "xxxx"))

lm_microscope = MyMicroscope("Lise Meitner",
    lm_spectrometer = MySpectrometer("Spectrometer", "xxxx"),
    lm_camera = MyCamera("Camera xxxx", "xxxx"),
    lm_white_light = MyWhiteLight("White light", "xxxx"),
    lm_laser_750 = MyLaser("Laser 750nm", "xxxx"),
    lm_filter_12 = MyFilter("Filter 12", "xxxx"),
    lm_platform = MyPlatform("Platform", "xxxx"))

app = MyApp("V0.3.1", (1200, 700), gm_microscope, lm_microscope)
app.mainloop()