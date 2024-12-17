from dev.application import *

version = "V1.1.2"
size = (1200,700)
visible_notif_time = 3
backup_directory = "C:/Users/A068/Desktop/Data"

gm_microscope = MyMicroscope("Maria Goeppert Mayer",
    MyCamera("Camera", "28939", enable=True),
    MySpectrometer("Spectrometer-VIS", "QEP06226", enable=True, dark_correction=True, integration_time=100),
    MySpectrometer("Spectrometer-NIR", "NQ51B1981", integration_time=50),
    MyShutter("White light - shutter", "26006167", enable=True, model="KST201"),
    MyShutter("Laser 750nm - shutter", "68801094", enable=False, model="KSC101"),
    MyShutter("Laser 550nm - shutter", "68800970", enable=False, model="KSC101"),
    MyFilter("Filter 12", "xxxx"),
    MyStage("Stage", "xxxx"))

lm_microscope = MyMicroscope("Lise Meitner",
    MySpectrometer("Spectrometer", "xxxx", enable=True),
    MyCamera("Camera", "xxxx", enable=True),
    MyShutter("White light - shutter", "26006167", enable=True, model="KST201"),
    MyShutter("Laser 750nm - shutter", "68801094", enable=False, model="KSC101"),
    MyFilter("Filter 12", "xxxx"),
    MyStage("Stage", "xxxx"))


app = MyApp(version, size, visible_notif_time, backup_directory, gm_microscope, lm_microscope)
app.mainloop()