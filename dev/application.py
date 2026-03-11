from functools import partial
from tkinter import Canvas, PhotoImage
from dev.devices.camera.dlls.import_lib import import_thorlab_lib
from dev.file_system import FileSystem
from dev.user_profile import UserProfile
from .widgets.microscope_frame import *
from .widgets.camera_frame import *
from .widgets.spectrometer_frame import *
from .widgets.power_meter_frame import PowerMeterFrame
from .widgets.directory_frame import *
from .widgets.setup_frame import *
from .widgets.notification import *
from .debugHelp import *

# device class for power meter
from dev.devices.power_meter.power_meter import MyPowerMeter
import ctypes
import os
import sys
import subprocess
import time
from .images.images import img_open_folder


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
        # ensure the safety move is executed even if the window is closed non‑interactively
        import atexit
        atexit.register(self._safety_on_exit)

        # Reduce minimize / restore lag: pause expensive update loops
        # while the window is iconic and resume with a short delay after
        # restore so CTk finishes its own redraws first.
        self.bind("<Unmap>", self._on_unmap)
        self.bind("<Map>", self._on_map)
        self._map_resume_id = None

        self.menu()

    def menu(self):
        """Displays the application's main menu
        """
        self.selected_microscope = None
        for widget in self.winfo_children():
            widget.destroy()
        self.title(f"MicroView - {self.backup_directory}")
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
        
        try:
            module = import_thorlab_lib("thorlabs_setup", r"dev\devices\camera\dlls\thorlabs_setup.pyc")
            module.ThorlabsSetup(self)
        except Exception as e:
            debugp("","")
        
        #Auto connect via connected camera serial
        #self.autoConnect()


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

    def autoConnect(self):
        for m in self.microscopes:
            for d in m.devices:
                if isinstance(d, MyCamera) and d.isPluggedIn():
                    self.go_to_microscope(m)  
                    return    
        
        debugp("AutoConnect", "No Device Detected")              

    def go_to_microscope(self, microscope):
        """Displays the microscope config panel

        Parameters
        ------------
        microscope, `MyMicroscope`
            Contains all information about the selected microscope
        """
        self.selected_microscope = microscope

        # ---- Show a loading screen as a separate borderless Toplevel ----
        # A Toplevel sits above the main window in the OS window stack so
        # nothing that happens in the main window (widget creation, grid
        # layout, internal update_idletasks calls) can ever flicker through.
        import tkinter as tk
        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty()
        w = self.winfo_width()
        h = self.winfo_height()

        self._loading_top = tk.Toplevel()
        self._loading_top.overrideredirect(True)      # no title bar / borders
        self._loading_top.attributes("-topmost", True) # stay above everything
        self._loading_top.geometry(f"{w}x{h}+{x}+{y}")

        bg = "#1a1a2e"
        self._loading_top.configure(bg=bg)
        tk.Label(self._loading_top, text="Loading…",
                 font=("Arial", 28, "bold"), fg="white", bg=bg
                 ).place(relx=0.5, rely=0.42, anchor="center")
        tk.Label(self._loading_top, text=f"Initialising {microscope.name}",
                 font=("Arial", 14), fg="gray", bg=bg
                 ).place(relx=0.5, rely=0.52, anchor="center")

        self._loading_top.lift()
        self._loading_top.update()                    # paint the loading screen

        # Now safe to tear down the menu – the Toplevel hides everything
        for widget in self.winfo_children():
            if widget is not self._loading_top:
                widget.destroy()

        # defer the heavy build to the next event-loop cycle
        self.after(50, lambda: self._build_microscope_view(microscope))

    def _build_microscope_view(self, microscope):
        """Build the full microscope config panel (called after the loading overlay is visible)."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        # add extra columns for the top-right buttons so they don't overlap
        self.grid_columnconfigure(2, weight=0)
        self.grid_columnconfigure(3, weight=0)
        self.grid_rowconfigure((1,2), weight=2)
        self.grid_rowconfigure((3,4), weight=4)
 
        self.label = CTkLabel(self, text=f"{microscope.name} - Config panel", font=("Arial", 25))
        # expand title across the extra columns so the right-side buttons have their own space
        self.label.grid(row=0, column=0, padx=5, pady=5, sticky="ew", columnspan=4)

        self.back_button = CTkButton(self, text="Back", width=90, fg_color="transparent", border_width=2, border_color="#1F6AA5", command=self.stop_devices)
        self.back_button.grid(row=0, column=0, padx=(20, 0), pady=10, sticky="w")

        # Top-right button container: place it so it does not affect grid column sizing
        top_right_frame = CTkFrame(self, fg_color="transparent")
        # place at the top-right corner of the window (anchor northeast)
        top_right_frame.place(relx=1.0, rely=0.0, anchor="ne", x=-10, y=8)

        self.settings_button = CTkButton(top_right_frame, text="", width=35, height=35, image=img_cogwheel, fg_color="transparent", border_width=2, border_color="#1F6AA5", command=self.settings_popup)
        self.open_folder_button = CTkButton(top_right_frame, text="", width=35, height=35, image=img_open_folder, fg_color="transparent", border_width=2, border_color="#1F6AA5")
        self.user_button = CTkButton(top_right_frame, text="DEFAULT", width=35, height=35, fg_color="transparent", border_width=2, border_color="#1F6AA5", font=CTkFont(family="Arial", size=14, weight="bold"), command=self.user_popup)
        # Pack right-to-left so user button is furthest right
        self.user_button.pack(side="right", padx=(5,0))
        self.open_folder_button.pack(side="right", padx=5)
        self.settings_button.pack(side="right", padx=5)

        # (toggle button moved below into the main frame area)
        # disable if no power meter devices present for this microscope
        # we will create the button later after frame creation

        self.directory_frame = DirectoryFrame(self, self.backup_directory)
        self.directory_frame.grid(row=1, column=0, padx=(20, 10), pady=10, sticky="nsew")
        
        self.file_system = FileSystem(self, self.backup_directory, self.directory_frame)
        # wire the open-folder button to the FileSystem implementation
        self.open_folder_button.configure(command=lambda: self.file_system.open_backup_directory())
        
        self.camera_frame = CameraFrame(self, self.find_device_by_type(microscope, MyCamera))
        self.camera_frame.grid(row=1, column=1, padx=(10, 20), pady=10, sticky="nsew", rowspan=2)

        # we use a dedicated container for the spectrometer / power‑meter area
        self.spec_pwr_container = CTkFrame(self, fg_color="transparent")
        self.spec_pwr_container.grid(row=3, column=1, padx=(10, 20), pady=(10, 20), sticky="nsew", rowspan=2)
        # layout: row0 for toggle button, row1 for frames
        self.spec_pwr_container.grid_rowconfigure(0, weight=0)
        self.spec_pwr_container.grid_rowconfigure(1, weight=1)
        self.spec_pwr_container.grid_columnconfigure(0, weight=1)
        self.spec_pwr_container.grid_columnconfigure(1, weight=0)

        # Toggle button to switch between spectrometer and power-meter views.
        # Created when both device types are declared; starts hidden and is
        # shown/hidden dynamically by update_spec_pwr_toggle_state() whenever
        # device connectivity changes.
        if self.find_devices_by_type(microscope, MyPowerMeter) and self.find_devices_by_type(microscope, MySpectrometer):
            self.spec_power_toggle_button = CTkButton(
                self.spec_pwr_container,
                text="Show Pwr",
                width=60,
                height=35,
                fg_color="transparent",
                border_width=2,
                border_color="#1F6AA5",
                command=self.toggle_spectrometer_power,
            )
            # place it in the grid but keep it hidden until both sides connect
            self.spec_power_toggle_button.grid(row=0, column=1, sticky="ne", padx=5, pady=5)
            self.spec_power_toggle_button.grid_remove()
        else:
            self.spec_power_toggle_button = None

        # now create the two stackable frames; use self as master so they
        # have access to attributes like file_system.  Both live in the
        # same grid cell — we use tkraise() to swap the visible one,
        # avoiding the expensive grid_forget/grid cycle.
        self.spectrometer_frame = SpectrometerFrame(self, self.find_devices_by_type(microscope, MySpectrometer))
        self.spectrometer_frame.grid(in_=self.spec_pwr_container, row=1, column=0, columnspan=2, sticky="nsew")

        self.power_meter_frame = PowerMeterFrame(self, self.find_devices_by_type(microscope, MyPowerMeter))
        self.power_meter_frame.grid(in_=self.spec_pwr_container, row=1, column=0, columnspan=2, sticky="nsew")

        # If spectrometers are present, default to spectrometer view;
        # otherwise show power meter (useful for setups like Raman that have
        # no spectrometer but do have a power meter).
        has_spectrometers = bool(self.find_devices_by_type(microscope, MySpectrometer))
        has_power_meter   = bool(self.find_devices_by_type(microscope, MyPowerMeter))
        if has_spectrometers:
            self.spectrometer_frame.tkraise()
            self._spec_visible = True
        elif has_power_meter:
            self.power_meter_frame.tkraise()
            self._spec_visible = False
            if self.spec_power_toggle_button:
                self.spec_power_toggle_button.configure(text="Show Spec")
        else:
            self.spectrometer_frame.tkraise()
            self._spec_visible = True

        # instantiate both left-side panels (devices and routines) but do not grid both simultaneously
        self.quick_setup_frame = QuickSetupFrame(self, microscope)
        self.routines_frame = RoutinesFrame(self, microscope)  # new secondary menu

        # small toggle bar placed above the left panel area (keeps same spot and doesn't affect other widgets)
        self.left_toggle_frame = CTkFrame(self, fg_color="transparent")
        # reduce vertical padding so toggle buttons sit closer to the panels
        # anchor to the bottom-left of the middle row so toggles sit just above the left panels and align to their left edge
        self.left_toggle_frame.grid(row=2, column=0, padx=(20, 10), pady=(0, 0), sticky="sw")
 
        self.devices_toggle_btn = CTkButton(self.left_toggle_frame, text="Devices", width=100, fg_color="transparent",
                                            border_width=2, border_color="#1F6AA5",
                                            command=lambda: self.show_left_panel("devices"))
        self.routines_toggle_btn = CTkButton(self.left_toggle_frame, text="Routines", width=100, fg_color="transparent",
                                             border_width=2, border_color="#1F6AA5",
                                             command=lambda: self.show_left_panel("routines"))
        # ensure buttons are anchored to the left inside the toggle frame
        self.devices_toggle_btn.pack(side="left", padx=(0, 8), anchor="w")
        self.routines_toggle_btn.pack(side="left", anchor="w")

        # show devices panel by default
        self.show_left_panel("devices")
 
        for rotation_mount in self.find_devices_by_type(microscope, MyRotationMount):
                        
            spectrometer_serial = rotation_mount.associated_spectrometer
            if not spectrometer_serial:
                continue
        
            spectrometer = self.find_device_by_serial(microscope, spectrometer_serial)
            if not spectrometer:
                continue
        
            rotation_mount.setup_auto_calibration(spectrometer, self.spectrometer_frame, self.spectrometer_frame.set_unavailable, self.spectrometer_frame.set_available)
        
        #Can't find why this line creates a deiconify bug :\
        #self.notification(f"Associated {rotation_mount.name} with {spectrometer.name}", color="#1a8300")

        
        self.is_menu = False
        
        debugp("connecting", "Check connected devices")
        self.quick_setup_frame.check_connected_devices()
        # ensure spectrometer/power toggle reflects current connection state
        self.update_spec_pwr_toggle_state()

        # ---- Tear-down of loading screen ----
        # Everything is built.  Force the main window to complete its full
        # render cycle while the Toplevel still covers it, then destroy
        # the Toplevel to reveal the fully-rendered microscope GUI.
        self.update()                       # render all widgets behind the Toplevel
        try:
            self._loading_top.destroy()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Minimize / restore handlers
    # ------------------------------------------------------------------

    def _on_unmap(self, event):
        """Pause heavy update loops when the window is minimized."""
        if event.widget is not self:
            return
        if hasattr(self, "power_meter_frame"):
            self.power_meter_frame._stop_update()

    def _on_map(self, event):
        """Resume update loops after the window is restored.

        A short delay lets customtkinter finish its own canvas redraws
        before we start pushing matplotlib frames again.
        """
        if event.widget is not self:
            return
        if self._map_resume_id:
            self.after_cancel(self._map_resume_id)
        self._map_resume_id = self.after(200, self._resume_after_map)

    def _resume_after_map(self):
        self._map_resume_id = None
        if not hasattr(self, "power_meter_frame"):
            return
        # only resume if power meter view is active and device connected
        if not getattr(self, "_spec_visible", True):
            if self.power_meter_frame.connected_device:
                self.power_meter_frame._reset_and_start()

    def toggle_spectrometer_power(self):
        """Switch between spectrometer and power meter display frames.

        The two frames occupy the same grid location inside a shared container;
        this method hides the currently visible one and shows the other.  If the
        corresponding device type is not present the button does nothing.  The
        button text is updated to indicate which view will be shown next ("Spec"
        means press to view spectrometer, etc.).
        """
        # if there is no power meter, do nothing
        if not hasattr(self, 'power_meter_frame') or self.power_meter_frame is None:
            return
        if self._spec_visible:
            # bring power meter to front (zero-cost layer swap)
            self.power_meter_frame.tkraise()
            self._spec_visible = False
            # reset & resume live graph when power meter becomes visible
            if self.power_meter_frame.connected_device:
                self.power_meter_frame._reset_and_start()
            self.spec_power_toggle_button.configure(text="Show Spec")
        else:
            # pause live graph when power meter goes behind
            self.power_meter_frame._stop_update()
            self.spectrometer_frame.tkraise()
            self._spec_visible = True
            self.spec_power_toggle_button.configure(text="Show Pwr")

    def update_spec_pwr_toggle_state(self):
        """Show or hide the spec/pwr toggle button.

        The button is only visible when **both** at least one spectrometer
        **and** at least one power meter are currently connected.  Called by
        :class:`QuickSetupFrame` whenever device connectivity changes.
        """
        # guard against early calls or microscopes without both device types
        if not hasattr(self, 'spec_power_toggle_button') or not self.spec_power_toggle_button:
            return

        specs  = self.find_devices_by_type(self.selected_microscope, MySpectrometer) if self.selected_microscope else None
        meters = self.find_devices_by_type(self.selected_microscope, MyPowerMeter)   if self.selected_microscope else None

        spec_connected  = any(s.connected for s in specs)  if specs  else False
        meter_connected = any(m.connected for m in meters) if meters else False

        debugp("powermeter", f"update_spec_pwr_toggle_state: spec_connected={spec_connected}, meter_connected={meter_connected}")

        if spec_connected and meter_connected:
            self.spec_power_toggle_button.grid()          # make visible
            self.spec_power_toggle_button.configure(state="normal")
        else:
            self.spec_power_toggle_button.grid_remove()   # hide completely

    def settings_popup(self):
        """Displays the setings popup.
        Allows users to modify certain application parameters
        """
        if not self.popup:
            self.popup = CTkToplevel(self)
            self.popup.title("Settings")
            self.popup.minsize(405, 200)
            self.center_popup(600, 250)
            self.popup.grid_rowconfigure(1, weight=1)
            self.popup.grid_columnconfigure(0, weight=1)
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
            self.backup_name_entry = CTkEntry(frame, placeholder_text=self.file_system.get_backup_directory(), textvariable=StringVar(value=self.file_system.get_backup_directory()))
            self.backup_name_entry.pack(side="left", fill="x", expand=True, padx=(20,40))

            CTkButton(self.popup, text="Cancel", fg_color="transparent", border_width=2, border_color="#1F6AA5", command=self.close_popup).grid(row=3, column=0, padx=(40,20), pady=20, sticky="ew")
            CTkButton(self.popup, text="Save", command=self.save_settings).grid(row=3, column=1, padx=(20,40), pady=20, sticky="ew")
        
        self.popup.focus_force()


    def user_popup(self):
        """Displays the user popup.
        Allows users to choose their profile.
        """
        if not self.popup:
            self.popup = CTkToplevel(self)
            self.popup.title("Profile")
            self.popup.minsize(405, 200)
            self.center_popup(600, 300) 

            self.popup.grid_rowconfigure(2, weight=1)
            self.popup.grid_columnconfigure(0, weight=1)

            self.popup.protocol("WM_DELETE_WINDOW", self.close_popup)
            self.popup.attributes("-topmost", True)
            self.after(50, lambda: self.popup.attributes("-topmost", False))

            title = CTkLabel(self.popup, text="Choose profile :", font=("Arial", 20))
            title.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w", columnspan=2)

            input_frame = CTkFrame(self.popup, fg_color="transparent")
            input_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew", columnspan=2)
            input_frame.grid_columnconfigure(0, weight=1)

            entry = CTkEntry(input_frame, placeholder_text="Username")
            entry.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")

            add = CTkButton(input_frame, text="Add", command=lambda: self.selected_user(entry.get()), width=80)
            add.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="ew")

            scrollable_frame = CTkScrollableFrame(self.popup, fg_color="transparent")
            scrollable_frame.grid(row=2, column=0, padx=20, pady=10, sticky="nsew", columnspan=2)
            
            scrollable_frame.grid_columnconfigure(0, weight=1)
            scrollable_frame.grid_columnconfigure(1, weight=1)

            profile_buttons = self.file_system.get_user_names()
            for i, name in enumerate(profile_buttons):
                row, col = divmod(i, 2)  # Converts index to (row, column) in a 2-column layout
                button = UserProfile(scrollable_frame, name, self.close_popup, self.selected_user)
                button.grid(row=row, column=col, padx=10, pady=10, sticky="ew")

            self.popup.focus_force()

        
    def selected_user(self, username):
        """Sets directory path to selected user"""
        self.file_system.change_user(username)
        self.close_popup()

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
        self.file_system.set_backup_directory(self.backup_name_entry.get())
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
        find_device_by_type : `class`
            Returns the object corresponding to the requested class
        """
        for device in microscope.devices:
            if isinstance(device, device_type):
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

    def find_device_by_serial(self, microscope, serial):
        """Returns element of the requested serial number according to the microscope selected

        Parameters
        ------------
        microscope, `MyMicroscope`
            Contains the selected microscope for which we are looking for elements
        serial, `string`
            Contains the serial number to be checked

        Returns
        ------------
        find_device_by_type : `class`
            Returns the object corresponding to the requested serial number
        """
        for device in microscope.devices:
            if device.serial == serial:
                return device
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

    def show_left_panel(self, name):
        """Show either 'devices' (QuickSetupFrame) or 'routines' (RoutinesFrame) in the left area.
        Both frames occupy the exact same grid area so they don't interfere with other widgets.
        """
        # hide both
        try:
            self.quick_setup_frame.grid_forget()
        except Exception:
            pass
        try:
            self.routines_frame.grid_forget()
        except Exception:
            pass

        # grid the requested panel into the same location
        if name == "routines":
            self.routines_frame.grid(row=3, column=0, padx=(20, 10), pady=(0, 20), sticky="nsew", rowspan=2)
        else:
            self.quick_setup_frame.grid(row=3, column=0, padx=(20, 10), pady=(0, 20), sticky="nsew", rowspan=2)

        # Visuals: keep border present for both, only swap fill (fg_color).
        # Choose an appropriate unselected fill depending on current theme.
        selected_fill = "#1F6AA5"         # blue when selected
        selected_hover = "#145b84"
        border_col = "#1F6AA5"
        # pick a light/dark neutral fill for unselected based on current appearance
        if getattr(self, "apparence_color_theme", "light") == "dark":
            unselected_fill = "#2F3336"  # dark gray background for unselected in dark mode
            unselected_hover = "#3b3f41"
            unselected_text = "#DCE4EE"
        else:
            unselected_fill = "#ECEFF1"  # light gray for unselected in light mode
            unselected_hover = "#e0e4e8"
            unselected_text = "gray10"

        # Configure both buttons explicitly (border always visible).
        common_unselected_cfg = dict(fg_color=unselected_fill, hover_color=unselected_hover,
                                     text_color=unselected_text, border_width=2, border_color=border_col)
        common_selected_cfg = dict(fg_color=selected_fill, hover_color=selected_hover,
                                   text_color="white", border_width=2, border_color=border_col)

        if name == "routines":
            self.routines_toggle_btn.configure(**common_selected_cfg)
            self.devices_toggle_btn.configure(**common_unselected_cfg)
        else:
            self.devices_toggle_btn.configure(**common_selected_cfg)
            self.routines_toggle_btn.configure(**common_unselected_cfg)

        # Force immediate repaint: generate a Leave event and update; schedule a tiny delayed refresh
        try:
            for btn in (self.devices_toggle_btn, self.routines_toggle_btn):
                btn.event_generate("<Leave>")
            self.update_idletasks()
            # one more short delayed update to ensure CTk internal hover state is cleared
            self.after(10, lambda: (self.devices_toggle_btn.event_generate("<Leave>"),
                                    self.routines_toggle_btn.event_generate("<Leave>"),
                                    self.update_idletasks()))
        except Exception:
            pass
    def notification(self, head_message=None, message=None, color=None, path=""):
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
        notification = Notification(head_message, message, color, time_before_delete=self.visible_notif_time, path = path)
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


    def _safety_on_exit(self):
        """Internal helper invoked during shutdown to park filter wheels.

        This is used both from :meth:`close` and an :mod:`atexit` callback,
        so it must be safe to call multiple times (it just quietly ignores
        disconnected wheels).
        """
        try:
            if self.selected_microscope:
                for dev in self.selected_microscope.devices:
                    if dev.__class__.__name__ == 'MyFilterWheel' and getattr(dev, 'connected', False):
                        try:
                            dev.set_position(12)
                        except Exception as e:
                            print(f"[shutdown] failed to move filter wheel to safety position: {e}")
                        else:
                            time.sleep(0.2)
        except Exception as e:
            print("[shutdown] exception during safety move", e)

    def close(self):
        """This method allows threads to be stopped cleanly before devices are disconnected
        """
        # run the parking routine first (also called by atexit)
        self._safety_on_exit()

        if not self.is_menu:
            self.spectrometer_frame.on_closing()
            self.camera_frame.on_closing()
            if hasattr(self, 'power_meter_frame') and self.power_meter_frame:
                self.power_meter_frame.on_closing()
        self.stop_devices()
        self.destroy()

    def __repr__(self):
        return f"Microscopes in this application - {self.version} :\n\t" + "\n\t".join([f"{microscope.name}" for microscope in self.microscopes]) + "\n"



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














