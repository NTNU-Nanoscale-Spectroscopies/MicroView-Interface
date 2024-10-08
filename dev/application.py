from dev.devices.camera.camera import *
from dev.devices.spectrometer.spectrometer import *
from dev.devices.whitelight.whitelight import *
from dev.devices.laser.laser import *
from dev.devices.filter.filter import *
from dev.devices.platform.platform import *

from dev.frames.microscope_frame import *
from dev.frames.camera_frame import *
from dev.frames.spectrometer_frame import *
from dev.frames.directory_frame import *

from dev.images.images import *


class MyApp(ctk.CTk):
    def __init__(self, version, size, *microscopes):
        super().__init__(fg_color=["gray92","gray14"])
        self.version = version
        self.microscopes = list(microscopes)
        self.apparence_color_theme = "light"
        self.centerWindow(size)
        set_default_color_theme("dev/themes/MyTheme.json")
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

        self.button = ctk.CTkButton(self, text=None, width=50, height=50, image=img_apparence_color_theme, command=self.swicthThemeMode)
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
        
        self.title(f"{microscope.name} - Config panel")
        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure((1, 2, 3, 4), weight=1)

        self.label = ctk.CTkLabel(self, text=f"{microscope.name} - Config panel", font=("Arial", 25))
        self.label.grid(row=0, column=0, padx=5, pady=5, sticky="ew", columnspan=2)
        self.button = ctk.CTkButton(self, text="< Back", command = lambda m=microscope: self.stopDevices(m))
        self.button.grid(row=0, column=0, padx=(20, 0), pady=10, sticky="w")

        self.camera_frame = CameraFrame(self, self.findDeviceByType(microscope, MyCamera))
        self.camera_frame.grid(row=1, column=1, padx=(10, 20), pady=(20, 10), sticky="nsew", rowspan=2)
        self.spectrometer_frame = SpectrometerFrame(self, self.findDeviceByType(microscope, MySpectrometer))
        self.spectrometer_frame.grid(row=3, column=1, padx=(10, 20), pady=(10, 20), sticky="nsew", rowspan=2)

        self.directory_frame = DirectoryFrame(self)
        self.directory_frame.grid(row=1, column=0, padx=(20, 10), pady=(20, 10), sticky="nsew")
        self.quick_setup_frame = QuickSetupFrame(self)
        self.quick_setup_frame.grid(row=2, column=0, padx=(20, 10), pady=(10, 20), sticky="nsew", rowspan=3)

    def findDeviceByType(self, microscope, device_type):
        for device in microscope.devices.values():
            if isinstance(device, device_type):
                return device
        return None

    def stopDevices(self, microscope):
        for device in microscope.devices.values():
            device.stop()
        self.menu()

    def __repr__(self):
        return f"Microscopes in this application - {self.version} :\n\t" + "\n\t".join([f"{microscope.name}" for microscope in self.microscopes]) + "\n"



class MyMicroscope:
    def __init__(self, name, **devices):
        self.name = name
        self.devices = devices

    def __repr__(self):
        return f"Devices in the {self.name} microscope :\n\t" + "\n\t".join([f"{device}" for key, device in self.devices.items()]) + "\n"
