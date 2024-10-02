from devices.camera import *
from devices.devices import *
from wigdets import *


class MyApp(ctk.CTk):
    def __init__(self, version, *microscopes):
        super().__init__(fg_color=["gray92","gray14"])
        self.version = version
        self.microscopes = list(microscopes)
        self.apparence_color_theme = "light"
        self.centerWindow([1200, 700])
        set_default_color_theme("theme/MyTheme.json")
        self.menu()

    def menu(self):
        for widget in self.winfo_children():
            widget.destroy()
        self.title(f"Microscope Selector - {self.version}")
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 3, 4), weight=0)
        self.grid_rowconfigure(2, weight=1)

        self.label = ctk.CTkLabel(self, text="Welcome back !", font=("Arial", 45))
        self.label.grid(row=0, column=0, padx=(50, 0), pady=(50, 0), sticky="w")
        self.label = ctk.CTkLabel(self, text="Please choose your microscope", font=("Arial", 30))
        self.label.grid(row=1, column=0, padx=(50, 0), pady=(20, 0), sticky="w")

        self.microscopes_frame = MicroscopeFrame(self, [microscope for microscope in self.microscopes])
        self.microscopes_frame.grid(row=2, column=0, padx=50, pady=10, sticky="nsew")

        self.button = ctk.CTkButton(self, text=None, width=50, height=50, image=img_manager_01.get_image('apparence_color_theme'), command=self.swicthThemeMode)
        self.button.grid(row=0, column=0, padx=(0, 20), sticky="e")


    def swicthThemeMode(self):
        self.apparence_color_theme = "light" if self.apparence_color_theme == "dark" else "dark"
        ctk.set_appearance_mode(self.apparence_color_theme)


    def centerWindow(self, size):
        x = int((self.winfo_screenwidth()/2) - (size[0]/2))
        y = int((self.winfo_screenheight()/2) - (size[1]/2))
        self.geometry(f"{size[0]}x{size[1]}+{x}+{y}")


    def goToMicroscope(self, microscope):
        for widget in self.winfo_children():
            widget.destroy()
        
        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure((1, 2, 3, 4), weight=1)

        self.label = ctk.CTkLabel(self, text=f"{microscope.name} - Config panel", font=("Arial", 25))
        self.label.grid(row=0, column=0, padx=5, pady=5, sticky="ew", columnspan=2)
        self.button = ctk.CTkButton(self, text="< Back", command=self.menu)
        self.button.grid(row=0, column=0, padx=(20, 0), pady=10, sticky="w")

        self.camera_frame = CameraFrame(self, self.find_device_by_type(microscope, MyCamera))
        self.camera_frame.grid(row=1, column=1, padx=(10, 20), pady=(20, 10), sticky="nsew", rowspan=2)
        # self.spectrometer_frame = SpectrometerFrame(self, self.find_device_by_type(microscope, MySpectrometer))
        # self.spectrometer_frame.grid(row=3, column=1, padx=(10, 20), pady=(10, 20), sticky="nsew", rowspan=2)

        self.camera_frame = SpectrometerFrame(self)
        self.camera_frame.grid(row=3, column=1, padx=(10, 20), pady=(10, 20), sticky="nsew", rowspan=2)
        self.camera_frame = SpectrometerFrame(self)
        self.camera_frame.grid(row=1, column=0, padx=(20, 10), pady=(20, 10), sticky="nsew")
        self.camera_frame = SpectrometerFrame(self)
        self.camera_frame.grid(row=2, column=0, padx=(20, 10), pady=(10, 20), sticky="nsew", rowspan=3)

    def find_device_by_type(self, microscope, device_type):
        """Cherche le premier appareil du type spécifié dans le microscope."""
        for device in microscope.devices.values():
            if isinstance(device, device_type):
                return device
        return None

    def __repr__(self):
        return f"Microscopes in this application - {self.version} :\n\t" + "\n\t".join([f"{microscope.name}" for microscope in self.microscopes]) + "\n"



class MyMicroscope:
    def __init__(self, name, **devices):
        self.name = name
        self.devices = devices

    def __repr__(self):
        return f"Devices in the {self.name} microscope :\n\t" + "\n\t".join([f"{device}" for key, device in self.devices.items()]) + "\n"
