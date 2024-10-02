from devices import *
from wigdets import *


class MyApp(ctk.CTk):
    def __init__(self, version, *microscopes):
        super().__init__(fg_color=["gray88","gray14"])
        self.version = version
        self.microscopes = list(microscopes)

        self.title(f"Microscope Selector - {self.version}")
        self.geometry("1200x700")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        set_default_color_theme("theme/MyTheme.json")

        self.label = ctk.CTkLabel(self, text="Welcome back !", font=("Arial", 45))
        self.label.grid(row=0, column=0, padx=(50, 0), pady=(50, 0), sticky="w")
        self.label = ctk.CTkLabel(self, text="Please choose your microscope", font=("Arial", 30))
        self.label.grid(row=1, column=0, padx=(50, 0), pady=20, sticky="w")

        self.microscopes_frame = MicroscopeFrame(self, [microscope.name for microscope in self.microscopes])
        self.microscopes_frame.grid(row=2, column=0, padx=50, pady=10, sticky="nsew")

        self.button = ctk.CTkButton(self, text=None, width=50, height=50, image=img_manager_01.get_image('apparence_color_theme'), command=self.swicthThemeMode)
        self.button.grid(row=0, column=0, padx=(0, 20), sticky="e")
        self.apparence_color_theme = "light"

    def swicthThemeMode(self):
        self.apparence_color_theme = "light" if self.apparence_color_theme == "dark" else "dark"
        ctk.set_appearance_mode(self.apparence_color_theme)

    def __repr__(self):
        return f"Microscopes in this application - {self.version} :\n\t" + "\n\t".join([f"{microscope.name}" for microscope in self.microscopes]) + "\n"


class MyMicroscope:
    def __init__(self, name, **devices):
        self.name = name
        self.devices = devices

    def __repr__(self):
        return f"Devices in the {self.name} microscope :\n\t" + "\n\t".join([f"{device}" for key, device in self.devices.items()]) + "\n"


gm_microscope = MyMicroscope("Goeppert Mayer",
    gm_camera = MyCamera("Camera CS165MU", "28939"),
    gm_spectrometer = MySpectrometer("Spectrometer", "QEP06226"),
    gm_white_light = MyWhiteLight("White light", "xxxx"),
    gm_laser_750 = MyLaser("Laser 750nm", "xxxx"),
    gm_laser_550 = MyLaser("Laser 550nm", "xxxx"),
    gm_filter_12 = MyFilter("Filter 12", "xxxx"),
    gm_platform = MyPlatform("Platform", "xxxx"))

lm_microscope = MyMicroscope("Lisa Meitner",
    lm_spectrometer = MySpectrometer("Spectrometer", "xxxx"),
    lm_camera = MyCamera("Camera xxxx", "xxxx"),
    lm_white_light = MyWhiteLight("White light", "xxxx"),
    lm_laser_750 = MyLaser("Laser 750nm", "xxxx"),
    lm_filter_12 = MyFilter("Filter 12", "xxxx"),
    lm_platform = MyPlatform("Platform", "xxxx"))

app = MyApp("V0.1.0", gm_microscope, lm_microscope)
app.mainloop()

# print(app)
# print(gm_microscope)
# print(lm_microscope)
