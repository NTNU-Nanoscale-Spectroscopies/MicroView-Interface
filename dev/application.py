from .widgets.microscope_frame import *
from .widgets.camera_frame import *
from .widgets.spectrometer_frame import *
from .widgets.directory_frame import *
from .widgets.setup_frame import *
from .widgets.notification import *
import ctypes


class MyApp(CTk):
    """MicroView's main class creates the entire application"""

    def __init__(self, version, size, visible_notif_time, backup_directory, *microscopes):
        """Create the MicroView's main window

        Parameters
        ------------
        version : `str`
            Defines current version
        size : `tuple(width, height)`
            Sets window dimensions at startup
        visible_notif_time : `int`
            Sets the visible time of notifications, in seconds
        backup_directory : `str`
            Sets the root directory where backups will be made
        microscopes : `MyMicroscope`
            Is a variadic parameter that contains all the information related to a microscope
        """
        super().__init__()
        self.version = version
        self.microscopes = list(microscopes)
        self.visible_notif_time = visible_notif_time
        self.backup_directory = backup_directory
        self.notif_list = []
        self.apparence_color_theme = "light"
        self.is_menu = True
        self.popup = None
        self.swicth_theme_mode()
        self.set_windows_scale()
        self.center_window(size[0], size[1])
        set_default_color_theme("dev/themes/MyTheme.json")
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.menu()


    def menu(self):
        """Displays the application's main menu
        """
        self.selected_microscope = None
        for widget in self.winfo_children():
            widget.destroy()
        self.title(f"MicroView")
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure((0, 1, 3, 4), weight=0)
        self.grid_rowconfigure(2, weight=1)

        self.label = CTkLabel(self, text="Welcome back !", font=("Arial", 45))
        self.label.grid(row=0, column=0, padx=(50, 0), pady=(50, 0), sticky="w")
        self.label = CTkLabel(self, text="Please choose your microscope", font=("Arial", 30))
        self.label.grid(row=1, column=0, padx=(50, 0), pady=(20, 0), sticky="w")
        self.label = CTkLabel(self, text=self.version, font=("Arial", 15), text_color="grey")
        self.label.grid(row=3, column=0, padx=10, pady=5, sticky="se")

        self.microscopes_frame = MicroscopeFrame(self, [microscope for microscope in self.microscopes])
        self.microscopes_frame.grid(row=2, column=0, padx=50, pady=10, sticky="nsew")

        self.button = CTkButton(self, text=None, width=50, height=50, image=img_apparence_color_theme, command=self.swicth_theme_mode)
        self.button.grid(row=0, column=0, padx=(0, 20), sticky="e")
        self.update_idletasks()


    def swicth_theme_mode(self):
        """Toggles the application's graphics mode, 
        from day mode to night mode and vice-versa
        """
        self.apparence_color_theme = "light" if self.apparence_color_theme == "dark" else "dark"
        set_appearance_mode(self.apparence_color_theme)


    def center_window(self, width, height):
        """Centers the main window in the screen

        Parameters
        ------------
        width : `int`
            Window width
        height : `int`
            Window height
        """
        x = int((self.winfo_screenwidth()/2) - (width/2))
        y = int((self.winfo_screenheight()/2) - (height/2))
        self.geometry(f"{width}x{height}+{x}+{y}")


    def center_popup(self, width, height):
        """Centers the popup window in the main window

        Parameters
        ------------
        width : `int`
            Popup width
        height : `int`
            Popup height
        """
        x = int((self.winfo_width()/2) + self.winfo_x() - (width/2))
        y = int((self.winfo_height()/2) + self.winfo_y() - (height/2))
        self.popup.geometry(f"{width}x{height}+{x}+{y}")


    def go_to_microscope(self, microscope):
        """Displays the microscope config panel

        Parameters
        ------------
        microscope, `MyMicroscope`
            Contains all information about the selected microscope
        """
        self.selected_microscope = microscope
        for widget in self.winfo_children():
            widget.destroy()
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure((1,2), weight=2)
        self.grid_rowconfigure((3,4), weight=4)

        self.label = CTkLabel(self, text=f"{microscope.name} - Config panel", font=("Arial", 25))
        self.label.grid(row=0, column=0, padx=5, pady=5, sticky="ew", columnspan=2)
        self.back_button = CTkButton(self, text="Back", width=90, fg_color="transparent", border_width=2, border_color="#1F6AA5", command=self.stop_devices)
        self.back_button.grid(row=0, column=0, padx=(20, 0), pady=10, sticky="w")
        self.settings_button = CTkButton(self, text="", width=35, height=35, image=img_cogwheel, fg_color="transparent", border_width=2, border_color="#1F6AA5", command=self.settings_popup)
        self.settings_button.grid(row=0, column=1, padx=(0, 20), pady=10, sticky="e")

        self.directory_frame = DirectoryFrame(self, self.backup_directory)
        self.directory_frame.grid(row=1, column=0, padx=(20, 10), pady=10, sticky="nsew")
        self.camera_frame = CameraFrame(self, self.find_device_by_type(microscope, MyCamera))
        self.camera_frame.grid(row=1, column=1, padx=(10, 20), pady=10, sticky="nsew", rowspan=2)
        self.spectrometer_frame = SpectrometerFrame(self, self.find_devices_by_type(microscope, MySpectrometer))
        self.spectrometer_frame.grid(row=3, column=1, padx=(10, 20), pady=(10, 20), sticky="nsew", rowspan=2)
        self.quick_setup_frame = QuickSetupFrame(self, microscope)
        self.quick_setup_frame.grid(row=2, column=0, padx=(20, 10), pady=(10, 20), sticky="nsew", rowspan=3)

        self.is_menu = False
        self.quick_setup_frame.check_connected_devices()


    def settings_popup(self):
        """Displays the setings popup.
        Allows users to modify certain application parameters
        """
        if not self.popup:
            self.popup = CTkToplevel(self)
            self.popup.title("Settings")
            self.popup.minsize(405, 200)
            self.center_popup(600, 250)
            self.popup.grid_rowconfigure((1,2), weight=1)
            self.popup.grid_columnconfigure((0,1), weight=1)
            self.popup.protocol("WM_DELETE_WINDOW", self.close_popup)
            self.popup.attributes("-topmost", True)
            self.after(50, lambda: self.popup.attributes("-topmost", False))

            title = CTkLabel(self.popup, text="Please configure the following :", font=("Arial", 20))
            title.grid(row=0, column=0, padx=(40,0), pady=(30,20), sticky="w", columnspan=2)

            frame = CTkFrame(self.popup, fg_color="transparent")
            frame.grid(row=1, column=0, sticky="nsew", columnspan=2)
            CTkLabel(frame, text="Visible notification time :").pack(side="left", padx=(40,20))
            self.visible_notif_time_entry = CTkEntry(frame, placeholder_text="3.0", width=80, textvariable=StringVar(value=self.visible_notif_time/1))
            self.visible_notif_time_entry.pack(side="left")
            CTkLabel(frame, text="s").pack(side="left", padx=5)

            frame = CTkFrame(self.popup, fg_color="transparent")
            frame.grid(row=2, column=0, sticky="nsew", columnspan=2)
            CTkLabel(frame, text="Backup directory :").pack(side="left", padx=(40,0))
            self.backup_name_entry = CTkEntry(frame, placeholder_text=self.backup_directory, textvariable=StringVar(value=self.backup_directory))
            self.backup_name_entry.pack(side="left", fill="x", expand=True, padx=(20,40))

            CTkButton(self.popup, text="Cancel", fg_color="transparent", border_width=2, border_color="#1F6AA5", command=self.close_popup).grid(row=3, column=0, padx=(40,20), pady=20, sticky="ew")
            CTkButton(self.popup, text="Save", command=self.save_settings).grid(row=3, column=1, padx=(20,40), pady=20, sticky="ew")
        
        self.popup.focus_force()


    def close_popup(self):
        """Closes the settings popup cleanly
        """
        if self.popup:
            self.popup.destroy()
            self.popup = None


    def save_settings(self):
        """Saves changes made in the settings popup
        """
        try:
            if float(self.visible_notif_time_entry.get()) <= 0:
                self.notification(f"Visible notification time must be positive", color="#8e0101")
                return
        except:
            self.notification(f"Visible notification time must be a number", color="#8e0101")
            return

        self.visible_notif_time = float(self.visible_notif_time_entry.get())
        self.backup_directory = self.backup_name_entry.get()
        self.close_popup()
        

    def find_device_by_type(self, microscope, device_type):
        """Returns element of the requested type according to the microscope selected

        Parameters
        ------------
        microscope, `MyMicroscope`
            Contains the selected microscope for which we are looking for elements
        device_type, `class`
            Contains the class to be checked

        Returns
        ------------
        find_device_by_type : `list(class)`
            Returns the list of objects corresponding to the requested class
        """
        for device in microscope.devices:
            if isinstance(device, device_type):
                print(device)
                return device
        return None
    
    def find_devices_by_type(self, microscope, device_type):
        """Returns all elements of the requested type according to the microscope selected

        Parameters
        ------------
        microscope, `MyMicroscope`
            Contains the selected microscope for which we are looking for elements
        device_type, `class`
            Contains the class to be checked

        Returns
        ------------
        find_devices_by_type : `list(class)`
            Returns the list of objects corresponding to the requested class
        """
        all_devices = []
        for device in microscope.devices:
            if isinstance(device, device_type):
                all_devices.append(device)
        
        if all_devices != []:
            return all_devices
        
        return None


    def stop_devices(self):
        """Stops and disconnects all devices currently in use, 
        then returns to the main menu
        """
        if not self.selected_microscope: return
        for device in self.selected_microscope.devices:
            device.disconnect()
        self.notif_list = []
        self.menu()


    def notification(self, head_message=None, message=None, color=None):
        """Creates notifications attached to the main window. 
        Also supports visual stacking of notifications

        Parameters
        ------------
        head_message : `str`, optional
            Main content. None by default
        message : `str`, optional
            Sub-content used to display the path of the last saved file. None by default
        color : `str`, optional
            Notification border color. Grey by default
        """
        notification = Notification(head_message, message, color, time_before_delete=self.visible_notif_time)
        self.notif_list.insert(0, notification)
        shift = notification.height * self.scale + 8
        for notif in self.notif_list[1:]:
            notif.draw(shift)
            shift += notif.winfo_height() + 10


    def set_windows_scale(self):
        """Determines the zoom value of the window screen. 
        The aim is to maintain consistency with the size and position of the elements
        """
        self.scale = 1
        if sys.platform.startswith("win"):
            user32 = ctypes.windll.user32
            hdc = user32.GetDC(0)
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
            user32.ReleaseDC(0, hdc)
            self.scale = dpi / 96


    def on_closing(self):
        """This method is called when the application is closed, 
        and its purpose is to hide the application until it closes cleanly
        """
        self.withdraw()
        self.after(300, self.close)


    def close(self):
        """This method allows threads to be stopped cleanly before devices are disconnected
        """
        if not self.is_menu:
            self.spectrometer_frame.on_closing()
            self.camera_frame.on_closing()
        self.stop_devices()
        self.destroy()


    def __repr__(self):
        return f"Microscopes in this application - {self.version} :\n\t" + "\n\t".join([f"{microscope.name}" for microscope in self.microscopes]) + "\n"



class MyMicroscope:
    """Class for creating microscopes"""

    def __init__(self, name, *devices):
        """Create a new microscope, with its own devices

        Parameters
        ------------
        name : `str`
            Micrsoscope name
        devices : `class`
            Is a variadic parameter that contains all the information related to a device
        """
        self.name = name
        self.devices = list(devices)


    def __repr__(self):
        return f"Devices in the {self.name} microscope :\n\t" + "\n\t".join([f"{device}" for device in self.devices]) + "\n"
