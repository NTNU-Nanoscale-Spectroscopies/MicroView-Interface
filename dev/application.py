from .widgets.microscope_frame import *
from .widgets.camera_frame import *
from .widgets.spectrometer_frame import *
from .widgets.directory_frame import *
from .widgets.setup_frame import *
from .widgets.notification import *
import ctypes


class MyApp(CTk):
    def __init__(self, version, size, *microscopes):
        super().__init__()
        self.version = version
        self.microscopes = list(microscopes)
        self.notif_list = []
        self.apparence_color_theme = "light"
        self.swicthThemeMode()
        self.set_windows_scale()
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

        self.label = CTkLabel(self, text="Welcome back !", font=("Arial", 45))
        self.label.grid(row=0, column=0, padx=(50, 0), pady=(50, 0), sticky="w")
        self.label = CTkLabel(self, text="Please choose your microscope", font=("Arial", 30))
        self.label.grid(row=1, column=0, padx=(50, 0), pady=(20, 0), sticky="w")

        self.microscopes_frame = MicroscopeFrame(self, [microscope for microscope in self.microscopes])
        self.microscopes_frame.grid(row=2, column=0, padx=50, pady=10, sticky="nsew")

        self.button = CTkButton(self, text=None, width=50, height=50, image=img_apparence_color_theme, command=self.swicthThemeMode)
        self.button.grid(row=0, column=0, padx=(0, 20), sticky="e")
        self.update_idletasks()


    def swicthThemeMode(self):
        self.apparence_color_theme = "light" if self.apparence_color_theme == "dark" else "dark"
        set_appearance_mode(self.apparence_color_theme)


    def centerWindow(self, size):
        x = int((self.winfo_screenwidth()/2) - (size[0]/2))
        y = int((self.winfo_screenheight()/2) - (size[1]/2))
        self.geometry(f"{size[0]}x{size[1]}+{x}+{y}")


    def goToMicroscope(self, microscope):
        for widget in self.winfo_children():
            widget.destroy()
        
        self.title(f"{microscope.name} - Config panel")
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure((1,2), weight=2)
        self.grid_rowconfigure((3,4), weight=4)

        self.label = CTkLabel(self, text=f"{microscope.name} - Config panel", font=("Arial", 25))
        self.label.grid(row=0, column=0, padx=5, pady=5, sticky="ew", columnspan=2)
        self.button = CTkButton(self, text="Back", width=90, fg_color="transparent", border_width=2, border_color="#1F6AA5", command = lambda m=microscope: self.stopDevices(m))
        self.button.grid(row=0, column=0, padx=(20, 0), pady=10, sticky="w")

        self.camera_frame = CameraFrame(self, self.findDeviceByType(microscope, MyCamera))
        self.camera_frame.grid(row=1, column=1, padx=(10, 20), pady=10, sticky="nsew", rowspan=2)
        self.spectrometer_frame = SpectrometerFrame(self, self.findDeviceByType(microscope, MySpectrometer))
        self.spectrometer_frame.grid(row=3, column=1, padx=(10, 20), pady=(10, 20), sticky="nsew", rowspan=2)

        self.update_idletasks()
        self.directory_frame = DirectoryFrame(self)
        self.directory_frame.grid(row=1, column=0, padx=(20, 10), pady=10, sticky="nsew")
        self.quick_setup_frame = QuickSetupFrame(self, microscope)
        self.quick_setup_frame.grid(row=2, column=0, padx=(20, 10), pady=(10, 20), sticky="nsew", rowspan=3)

    def findDeviceByType(self, microscope, device_type):
        for device in microscope.devices.values():
            if isinstance(device, device_type):
                return device
        return None

    def stopDevices(self, microscope):
        for device in microscope.devices.values():
            device.disconnect()
        self.notif_list = []
        self.menu()

    def notification(self, head_message=None, message=None, color=None):
        notif = Notification(head_message, message, color)
        self.notif_list.insert(0, notif)
        shift = notif.winfo_height() + 8
        for notif in self.notif_list[1:]:
            notif.draw(shift)
            shift += notif.winfo_height() + 10

    def __repr__(self):
        return f"Microscopes in this application - {self.version} :\n\t" + "\n\t".join([f"{microscope.name}" for microscope in self.microscopes]) + "\n"

    def set_windows_scale(self):
        self.scale = 1
        if sys.platform.startswith("win"):
            user32 = ctypes.windll.user32
            hdc = user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
            user32.ReleaseDC(0, hdc)
            self.scale = dpi / 96


class MyMicroscope:
    def __init__(self, name, **devices):
        self.name = name
        self.devices = devices

    def __repr__(self):
        return f"Devices in the {self.name} microscope :\n\t" + "\n\t".join([f"{device}" for key, device in self.devices.items()]) + "\n"
