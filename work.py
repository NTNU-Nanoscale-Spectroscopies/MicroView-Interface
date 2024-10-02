from customtkinter import *
import customtkinter as ctk 
from PIL import Image

Path="V0.1.0"
img_microscope_data = Image.open(Path + "/img/microscope_black.png")
img_microscope = CTkImage(dark_image=img_microscope_data, light_image=img_microscope_data, size=(150, 150))



class MyApp(ctk.CTk):
    def __init__(self, version, *microscopes):
        super().__init__()
        self.version = version
        self.microscopes = list(microscopes)

        self.title(f"Microscope Selector - {self.version}")
        self.geometry("1200x700")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)


        self.label = ctk.CTkLabel(self, text="Welcome back !", font=("Arial", 45))
        self.label.grid(row=0, column=0, padx=(50, 0), pady=(50, 0), sticky="w")
        self.label = ctk.CTkLabel(self, text="Please choose your microscope", font=("Arial", 30))
        self.label.grid(row=1, column=0, padx=(50, 0), pady=20, sticky="w")

        self.checkbox_frame = MicroscopeFrame(self, [microscope.name for microscope in self.microscopes])
        self.checkbox_frame.grid(row=2, column=0, padx=50, pady=10, sticky="nsew")
#----

        # self.microscope_combobox = ctk.CTkComboBox(self, values=[microscope.name for microscope in self.microscopes],
        #                                            command=self.display_microscope_info)
        # self.microscope_combobox.pack(pady=10)

        # self.info_text = ctk.CTkTextbox(self, height=200, width=400)
        # self.info_text.pack(pady=10)

        # for microscope in self.microscopes:
        #     self.button = ctk.CTkButton(self, text=microscope.name, command=self.display_microscope_info(microscope))
        #     self.button.pack(pady=10)
            
        # self.quit_button = ctk.CTkButton(self, text="Quit", command=self.quit)
        # self.quit_button.pack(pady=10)

    def display_microscope_info(self, selected_microscope):
        self.info_text.delete(1.0, "end")
        self.info_text.insert("end", repr(selected_microscope))

    def __repr__(self):
        return f"Microscopes in this application - {self.version} :\n\t" + "\n\t".join([f"{microscope.name}" for microscope in self.microscopes]) + "\n"

class MicroscopeFrame(ctk.CTkFrame):
    def __init__(self, master, values):
        super().__init__(master)
        self.grid_rowconfigure(0, weight=1)
        self.values = values
        self.buttons = []

        for i, value in enumerate(self.values):
            button = ctk.CTkButton(self, text=value, width=300, height=300, image=img_microscope)
            button.grid(row=0, column=i, padx=10, pady=10)
            self.grid_columnconfigure(i, weight=1)
            self.buttons.append(button)

class MyMicroscope:
    def __init__(self, name, **devices):
        self.name = name
        self.devices = devices

    def __repr__(self):
        return f"Devices in the {self.name} microscope :\n\t" + "\n\t".join([f"{device}" for key, device in self.devices.items()]) + "\n"

class MyDevice:
    def __init__(self, name, serial, type=None, feature=None, enabled=True):
        self.name = name
        self.serial = serial
        self.type = type
        self.feature = feature
        self.enable = enabled
        self.connected = False

    def __repr__(self):
        return f"{self.name}, serial : {self.serial}"

class MyCamera(MyDevice):
    def __init__(self, name, serial, enabled=True):
        super().__init__(name, serial, "ThorCam", "editable", enabled)

class MySpectrometer(MyDevice):
    def __init__(self, name, serial, enabled=True):
        super().__init__(name, serial, "OceanSpectrometer", "editable", enabled)

class MyWhiteLight(MyDevice):
    def __init__(self, name, serial, enabled=False):
        super().__init__(name, serial, "ThorWhiteLight", None, enabled)

class MyLaser(MyDevice):
    def __init__(self, name, serial, enabled=False):
        super().__init__(name, serial, "ThorLaser", "info", enabled)

class MyFilter(MyDevice):
    def __init__(self, name, serial, enabled=True):
        super().__init__(name, serial, "ThorFilter", None, enabled)

class MyPlatform(MyDevice):
    def __init__(self, name, serial, enabled=True):
        super().__init__(name, serial, "ThorPlatform", "editable", enabled)


gm_microscope = MyMicroscope("Goeppert Mayer",
    gm_camera=MyCamera("Camera CS165MU", "28939"),
    gm_spectrometer=MySpectrometer("Spectrometer", "QEP06226"),
    gm_white_light=MyWhiteLight("White light", "xxxx"),
    gm_laser_750=MyLaser("Laser 750nm", "xxxx"),
    gm_laser_550=MyLaser("Laser 550nm", "xxxx"),
    gm_filter_12=MyFilter("Filter 12", "xxxx"),
    gm_platform=MyPlatform("Platform", "xxxx"))

lm_microscope = MyMicroscope("Lisa Meitner",
    lm_spectrometer=MySpectrometer("Spectrometer", "xxxx"),
    lm_camera=MyCamera("Camera xxxx", "xxxx"),
    lm_white_light=MyWhiteLight("White light", "xxxx"),
    lm_laser_750=MyLaser("Laser 750nm", "xxxx"),
    lm_filter_12=MyFilter("Filter 12", "xxxx"),
    lm_platform=MyPlatform("Platform", "xxxx"))

app = MyApp("V0.1.0", gm_microscope, lm_microscope, lm_microscope)
app.mainloop()
