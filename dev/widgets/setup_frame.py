from tkinter import messagebox, simpledialog
from customtkinter import Variable as CTkVariable, CTkOptionMenu
from CTkToolTip import *
from dev.debugHelp import debugp
from dev.devices.rotation_mounts.rotation_mount import MyRotationMount
from .notification import *
from ..images.images import *
from ..devices.camera.camera import *
from ..devices.spectrometer import *
from ..devices.shutter.shutter import *
from ..devices.filter import *
from ..devices.power_meter.power_meter import *
# filter wheel device implementation (extends MyFilter)
from ..devices.filter_wheel.filterwheel import MyFilterWheel
from ..devices.stage import *
from ..devices.Stage.sim_stage import MySimStage
from ..devices.Stage.mcm301_stage import MyMCM301Stage
import threading
import time
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from CTkLabel import CTkLabel
from . import preview

# shared headline font for both left panels (slightly larger than other menu text)
HEADLINE_FONT = ("Arial", 24)

class QuickSetupFrame(CTkScrollableFrame):
    """Class for creating a frame to control all devices"""

    def __init__(self, master, microscope):
        """Create a frame in the main window.
        Users can easily control all devices from this panel

        Notes
        ------------
        In the setup frame, a space is created for each device associated with the microscope to enable control.
        Each device is equipped with a switch button to connect or disconnect it, 
        along with specific elements tailored to the device type. 
        Some devices can also be controlled from another, more specific frame

        Each widget can be associated with a keyword, allowing it to be treated differently

        Parameters
        ------------
        master : `CTk`
            Main window
        microscope : `MyMicroscope`
            Object containing all the information related to a microscope
        """
        super().__init__(master)
        # CTkScrollableFrame wraps the real master in internal frames, so
        # self.master does NOT point to the app.  Store a direct reference.
        self._app = master
        self.device_entries = []
        # Headline
        title = CTkLabel(self, text="Devices", font=HEADLINE_FONT)
        title.grid(row=0, column=0, padx=20, pady=(12, 6), sticky="w")
        # enumerate devices, start placing entries at row=1 to leave row 0 for headline
        for i, device in enumerate(microscope.devices):

            widgets = []
            master_frame = None
            frame = CTkFrame(self)
            frame.grid(row=i+1, column=0, sticky="nsew")
            switch = CTkSwitch(frame, text=device.name, font=("Arial", 20))
            switch.pack(side="left", padx=(30,10), pady=20)

            if isinstance(device, MyCamera):
                master_frame = self.master.master.master.camera_frame
                
            elif isinstance(device, MySpectrometer):
                master_frame = self.master.master.master.spectrometer_frame
                entry = CTkEntry(frame, width=100, placeholder_text=device.integration_time/1000)
                button = CTkButton(frame, text="Set", width=30, state="disabled", command=lambda d=device, e=entry: self.check_valid_integ_entry(d,e))
                label = CTkLabel(frame, text="ms")
                button.pack(side="left", padx=(10,5))
                entry.pack(side="left")
                label.pack(side="left", padx=3)
                entry.configure(state="disabled")
                widgets.append((button,""))
                widgets.append((entry,""))
                widgets.append((label,"NonDisableable"))

            elif isinstance(device, MyFilterWheel):
                # build controls for a filter wheel: left/right arrows, position dropdown, settings
                left_btn = CTkButton(frame, text="◀", width=30, state="disabled")
                right_btn = CTkButton(frame, text="▶", width=30, state="disabled")
                # variable to hold selection
                var = CTkVariable(value="")
                dropdown = CTkOptionMenu(frame, values=[], variable=var, width=120, state="disabled")
                settings = CTkButton(frame, text="", width=30, height=30,
                                     image=img_cogwheel, fg_color="transparent",
                                     state="normal", command=lambda d=device: self.open_filter_settings(d))
                CTkToolTip(settings, delay=0.2, message="Settings")

                # attach UI handles to device for later updates
                device._ui_left_btn = left_btn
                device._ui_right_btn = right_btn
                device._ui_dropdown = dropdown
                device._ui_position_var = var
                device._ui_settings_btn = settings


                # callbacks
                def move_delta(delta, dev=device):
                    newpos = dev.step(delta)
                    if newpos is not None:
                        dev.update_ui()
                def dropdown_changed(val, dev=device):
                    try:
                        idx = int(val.split(":")[0])
                    except Exception:
                        return
                    dev.set_position(idx)
                    dev.update_ui()

                left_btn.configure(command=lambda d=device: move_delta(-1))
                right_btn.configure(command=lambda d=device: move_delta(1))
                dropdown.configure(command=dropdown_changed)

                # pack widgets
                left_btn.pack(side="left", padx=5)
                dropdown.pack(side="left")
                right_btn.pack(side="left", padx=5)
                settings.pack(side="left", padx=(0,0))

                widgets.append((left_btn, ""))
                widgets.append((dropdown, ""))
                widgets.append((right_btn, ""))
                widgets.append((settings, "NonDisableable"))

            elif isinstance(device, (MyStage, MySimStage, MyMCM301Stage)):
                settings = CTkButton(frame, text="", width=30, height=30, image=img_cogwheel, fg_color="transparent", state="disabled", command=lambda d=device : self.open_stage_settings(d))
                CTkToolTip(settings, delay=0.2, message="Settings") 
                settings.pack(side="left", padx=(0,0))
                widgets.append((settings,""))

            elif isinstance(device, MyPowerMeter):
                master_frame = self.master.master.master.power_meter_frame

            elif isinstance(device, MyShutter):
                button = CTkButton(frame, text="Close", state="disabled", width=70, fg_color="transparent", border_width=2, border_color="#920000", hover_color="#4b0000")
                button.configure(command=lambda d=device, b=button: self.toggle_shutter(d,b))
                button.pack(side="left")
                widgets.append((button,"Shutter"))
                
            elif isinstance(device, MyRotationMount):
                entry = CTkEntry(frame, width=50, placeholder_text="0")
                home_btn = CTkButton(frame, text="🏠", width=30, state="disabled",     command=lambda d=device, e=entry: (e.delete(0, "end"), e.insert(0, "0"), d.home()))
                CTkToolTip(home_btn, delay=0.2, message="Rotation Mount Home") 
                auto_calibration_btn = CTkButton(frame, image=img_auto_calibration, width=30, text=None, state="disabled",     command=device.start_auto_calibration)
                CTkToolTip(auto_calibration_btn, delay=0.2, message="Auto Calibrate") 
                label = CTkLabel(frame, text="°")
                button = CTkButton(frame, text="Set", width=30, state="disabled", command=lambda d=device, e=entry: self.check_valid_angle_entry(d,e))
                settings = CTkButton(frame, text="⁞", width=1, state="disabled", command=lambda d=device : self.open_rotation_mount_settings(d))
                CTkToolTip(settings, delay=0.2, message="Settings") 

                settings.pack(side="left", padx=(0,0))
                home_btn.pack(side="left", padx=(5,5))
                button.pack(side="left", padx=(5,5))
                entry.pack(side="left")
                label.pack(side="left", padx=3)
                auto_calibration_btn.pack(side="left", padx=(10,5))
                entry.configure(state="disabled")
                widgets.append((settings,""))
                widgets.append((button,""))
                widgets.append((entry,""))
                widgets.append((home_btn,""))
                widgets.append((auto_calibration_btn,""))
                widgets.append((label,"NonDisableable"))

            #Add device to left hand tab and setup its switch
            self.device_entries.append(DeviceEntry(switch, device, widgets, master_frame))
            switch.configure(command=lambda e=self.device_entries[-1]: self.toggle_device(e))

        self.update_idletasks()
        # account for headline row (+1) when computing required height
        num_devices = len(microscope.devices)
        self.required_height_for_scrollbar = (num_devices + 1) * frame.winfo_height()
        self.previous_frame_height = self.master.winfo_height()
        self.master.bind("<Configure>", lambda event: self.update_scrollbar_visibility())
        self.after(200, self.init)


    def init(self):
        """Essaye de connecter tout les élements du microscope

        In the case of spectrometers, if a spectrometer is already connected,
        we move on to the next piece of equipment to avoid display problems
        """
        
        #spectrometer_already_open = False
        for entry in self.device_entries:            
            
            # if isinstance(entry.device, MySpectrometer) and spectrometer_already_open: continue
            
            #Get the frame to establish a connction, or get the device name to display error message
            element = entry.frame or entry.device
            
            #If spectrometer or power meter, pass the device to the frame's connect
            if isinstance(entry.device, (MySpectrometer, MyPowerMeter)):  
                if not element.connect(entry.device):
                    print(f"{entry.frame} , {entry.device}")
                    print(f"Unable to connect to {entry.device.name} {entry.device.serial}")
                    self.notification(f"Unable to connect to {entry.device.name} {entry.device.serial}", color="#8e0101")
            else:
                if not element.connect():
                    print(f"{entry.frame} , {entry.device}")
                    print(f"Unable to connect to {entry.device.name} {entry.device.serial}")
                    self.notification(f"Unable to connect to {entry.device.name} {entry.device.serial}", color="#8e0101")
            
            # elif isinstance(entry.device, MySpectrometer):
            #     spectrometer_already_open = True
                
            debugp("connecting", "Connected device : " + str(element))
              
        debugp("connecting", "checking connected devices")  
        self.check_connected_devices()


    def check_connected_devices(self):
        """For each device, update the element's graphic content to match its actual state
        """
        for entry in self.device_entries:
            #debugp("connecting", "checking device : " + str(entry))
            if entry.is_device_connected():
                entry.activate()
                # allow device to refresh its UI if it defines such method
                if hasattr(entry.device, "post_connect_update"):
                    try:
                        entry.device.post_connect_update()
                    except Exception:
                        pass
            else:
                entry.desactivate()
        # let the application know device connectivity changed so any
        # dependent controls (toggle button) can be updated
        app = self._app
        if hasattr(app, "update_spec_pwr_toggle_state"):
            app.update_spec_pwr_toggle_state()


    def toggle_device(self, entry):
        """Toggles device connection status (connect/disconnect)

        To ensure that the spectrometer is correctly displayed in the `spectrometer frame`,
        before connecting a new spectrometer, the previous one is disconnected to ensure uniform display

        If a device's connection attempt fails, a notification is sent back to users

        Parameters
        ------------
        entry : `DeviceEntry`
            Contains all graphic elements associated with a device
        """
        # element = entry.frame or entry.device
        # if isinstance(entry.device, MySpectrometer):
        #     if element.spectrometer != entry.device:
        #         element.disconnect()
        #         element.spectrometer = entry.device

        element = entry.frame or entry.device
        debugp("connecting", "Toggle device " + str(element))
        
        # if isinstance(entry.device, MySpectrometer):
        #     for spec in element.spectrometers:
        #         if spec != entry.device:
        #             element.disconnect(spec)
        #             #element.spectrometer = entry.device

        # spectrometer and power meter frames need the device passed to their
        # connect() methods so they can update their UI.  the bare device
        # objects however accept no arguments, so handle both cases.
        if isinstance(entry.device, (MySpectrometer, MyPowerMeter)):
            if entry.switch.get():
                try:
                    if element is entry.device:
                        success = element.connect()
                    else:
                        success = element.connect(entry.device)
                except TypeError:
                    # in case the signature doesn't match, try without args
                    success = element.connect()
                debugp("connecting", f"after connect call: device.connected={entry.device.connected}, success={success}")
                if not success:
                    debugp("connecting", "Device Not Connecting Manually" + str(element))
                    entry.switch.deselect()
                    self.notification(
                        f"Unable to connect to {entry.device.name} {entry.device.serial}",
                        color="#8e0101",
                    )
                else:
                    debugp("connecting", "Device Connecting Manually" + str(element))
                    # immediately refresh the top‑level toggle button in case the
                    # generic check_connected_devices later gets skipped for any
                    # reason (it shouldn’t, but this makes the behaviour robust)
                    if hasattr(self._app, "update_spec_pwr_toggle_state"):
                        self._app.update_spec_pwr_toggle_state()
            else:
                debugp("connecting", "Device Disconnecting Manually" + str(element))
                # pass device argument only if frame expects it
                try:
                    if element is entry.device:
                        element.disconnect()
                    else:
                        element.disconnect(entry.device)
                except TypeError:
                    element.disconnect()
        else:
            if entry.switch.get():
                if not element.connect():
                    print("Tried to connect to device, unsuccessful (toggle_device)")
                    self.notification(
                        f"Unable to connect to {entry.device.name} {entry.device.serial}",
                        color="#8e0101",
                    )
                else:
                    debugp("connecting", "Connecting " + str(element))
            else:
                debugp("connecting", "Disconnecting " + str(element))
                element.disconnect()
            
        debugp("connecting", "Check conneced devices")
        self.check_connected_devices()


    def reconnection(self, frame_device):
        """Try reconnecting and updating the graphics elements of the device associated with the frame

        Parameters
        ------------
        frame_device : `CTk`
            Corresponds to a device control frame
        """
        for entry in self.device_entries:
            if entry.device == frame_device:
                entry.switch.select()
                print("Trying to reconnect device (reconnection QuickSetupFrame)")
                self.toggle_device(entry)
                break


    def toggle_shutter(self, device, button):
        """Toggles state of associated shutter (open/closed)

        Parameters
        ------------
        device : `MyShutter`
            Object containing all the information related to a shutter
        button : `CTkButton`
            Graphic element associated with the shutter
        """
        # Determine action and give immediate visual feedback, then run move in background
        action = 'close' if device.state() else 'open'
        # Show moving state and prevent re-entrant clicks
        try:
            button.configure(state="disabled", text="Moving...")
        except Exception:
            pass

        def _worker():
            try:
                if action == 'open':
                    device.open()
                else:
                    device.close()
            except Exception as e:
                print("Shutter toggle error:", e)
            finally:
                # Update GUI from main thread
                def _on_done():
                    update_shutter_button_style(button, device)
                    try:
                        button.configure(state="normal")
                    except Exception:
                        pass
                self.after(0, _on_done)

        threading.Thread(target=_worker, daemon=True).start()


    def check_valid_integ_entry(self, device, entry):
        """Checks the validity of content entered by users before saving it.
        If the content is inappropriate, an error notification is sent to the user

        Note that the input value must be a positive float between 8 and 1600000
        
        Parameters
        ------------
        device : `MySpectrometer`
            Object containing all the information related to a spectrometer
        entry : `CTkEntry`
            Graphic elements associated with the spectrometer
        """
        try:
            value = float(entry.get())
            if 8 <= value <= 1600000:
                device.set_integration_time(value * 1000)
                self.notification(f"Integration time set at {value} ms", "#1a8300")
            else:
                self.notification(f"Integration time must be between 8 ms and 1600000 ms", "#8e0101")
        except:
            self.notification(f"Integration time must be a number", "#8e0101")

    def check_valid_angle_entry(self, device, entry):
        """Checks the validity of content entered by users before saving it.
        If the content is inappropriate, an error notification is sent to the user

        Note that the input value must be a positive float between 8 and 1600000
        
        Parameters
        ------------
        device : `MyRotationMount`
            Object containing all the information related to a rotation mount
        entry : `CTkEntry`
            Graphic elements associated with the rotation mount
        """
        try:
            value = float(entry.get())
            if 0 <= value <= 360:
                device.set_absolute_angle(value)
                self.notification(f"Set angle to {value}°", "#1a8300")
            else:
                self.notification(f"Angle must be between 0° and 360°", "#8e0101")
        except:
            self.notification(f"Integration time must be a number", "#8e0101")

    def update_scrollbar_visibility(self):
        """This method allows to hide/show the scrollbar according to the space available in the `setup frame`.
        To do this, the height of the frame is compared with the number of elements it contains
        """
        current_height = self.master.winfo_height()
        if current_height != self.previous_frame_height:
            self.previous_frame_height = current_height
            if self.required_height_for_scrollbar > current_height:
                self._scrollbar.grid(column= 1, row= 1, pady= 6, sticky= "nesw")
            else:
                self._scrollbar.grid_forget()


    def notification(self, head_message=None, color=None, message=None):
        """Creates notifications attached to the main window. 

        Parameters
        ------------
        head_message : `str`, optional
            Main content. None by default
        color : `str`, optional
            Notification border color. Grey by default
        message : `str`, optional
            Sub-content used to display the path of the last saved file. None by default
        """
        self.master.master.master.notification(head_message, message, color)
     
    # Needs new option to prompt user for sweep start stop angle and step size. Pass two user inputted variables to the sweep logic (rotation_mount.py)
    def open_rotation_mount_settings(self, device):
        self.popup = CTkToplevel(self)
        self.popup.title("Rotation Mount Settings")
        self.popup.geometry("450x500")  # Increased height to accommodate new elements
        self.popup.resizable(True, True)

        # Degrees input
        self.label3 = CTkLabel(self.popup, text="Step Angle (°):")
        self.label3.pack(pady=(10, 5))
        self.degree_entry = CTkEntry(self.popup, width=220, placeholder_text="1")
        self.degree_entry.pack()

        # Start Angle input (default 0)
        self.label_start = CTkLabel(self.popup, text="Start Angle (°):")
        self.label_start.pack(pady=(10, 5))
        self.start_entry = CTkEntry(self.popup, width=220, placeholder_text="0")
        self.start_entry.pack()

    def open_filter_settings(self, device):
        """Popup window allowing user to name filters for each wheel position."""
        # avoid opening duplicates
        if getattr(self, 'popup', None):
            try:
                self.popup.lift()
            except Exception:
                pass
            return
        self.popup = CTkToplevel(self.master)
        self.popup.title("Filter Wheel Settings")
        # ensure reference cleared when popup is closed
        def _on_filter_popup_close():
            try:
                self.popup.destroy()
            except Exception:
                pass
            finally:
                self.popup = None
        self.popup.protocol("WM_DELETE_WINDOW", _on_filter_popup_close)
        # compute height: base space for header + one row per position + footer buttons
        count = device.position_count or device.get_position_count() or 0
        height = 100 + 30 * count
        # enforce a sensible minimum so very small wheels still show buttons
        height = max(height, 180)
        self.popup.geometry(f"400x{height}")
        self.popup.resizable(True, True)

        # ensure we know how many positions exist
        count = device.position_count or device.get_position_count() or 0
        device.position_count = count
        self._filter_entries = []

        body = CTkFrame(self.popup)
        body.pack(padx=10, pady=10, fill="both", expand=True)

        for pos in range(1, count + 1):
            row = CTkFrame(body)
            row.pack(fill="x", pady=2)
            lbl = CTkLabel(row, text=f"Position {pos}:")
            lbl.pack(side="left")
            ent = CTkEntry(row, width=200)
            ent.pack(side="left", padx=5)
            ent.insert(0, device.filter_names.get(pos, ""))
            self._filter_entries.append((pos, ent))

        # action buttons
        btn_frame = CTkFrame(self.popup)
        btn_frame.pack(pady=10)
        save_btn = CTkButton(btn_frame, text="Save", command=lambda d=device: self._save_filter_settings(d))
        save_btn.grid(row=0, column=0, padx=5)
        cancel_btn = CTkButton(btn_frame, text="Cancel", command=lambda: _on_filter_popup_close())
        cancel_btn.grid(row=0, column=1, padx=5)

        self.popup.transient(self)

    def _save_filter_settings(self, device):
        # commit entries to the device and persist
        for pos, ent in getattr(self, '_filter_entries', []):
            device.filter_names[pos] = ent.get()
        if hasattr(device, 'save_settings'):
            device.save_settings()
        if hasattr(device, 'update_ui'):
            device.update_ui()
        try:
            self.popup.destroy()
        except Exception:
            pass
        finally:
            # clear reference so popup can be reopened later
            self.popup = None

        # Stop Angle input (default 360)
        self.label_stop = CTkLabel(self.popup, text="Stop Angle (°):")
        self.label_stop.pack(pady=(10, 5))
        self.stop_entry = CTkEntry(self.popup, width=220, placeholder_text="360")
        self.stop_entry.pack()

        # Run Sweep Button
        self.sweep_btn = CTkButton(self.popup, text="Run Sweep", command=lambda d=device: self.begin_sweep(d))
        self.sweep_btn.pack(pady=(5, 10))

        # Calibration folder input
        self.label1 = CTkLabel(self.popup, text="Calibration folder name:")
        self.label1.pack(pady=(15, 5))
        self.text_entry = CTkEntry(self.popup, width=220, placeholder_text=device.auto_calibrate.calibration_folder)
        self.text_entry.pack()

        # Wavelength input
        self.label2 = CTkLabel(self.popup, text="Wavelength to calibrate on:")
        self.label2.pack(pady=(10, 5))
        self.num_entry = CTkEntry(self.popup, width=220, placeholder_text=device.auto_calibrate.calibration_wavelength)
        self.num_entry.pack()
        
        # Button Frame
        button_frame = CTkFrame(self.popup)
        button_frame.pack(pady=20)
        
        self.save_btn = CTkButton(button_frame, text="Save", command=lambda d=device: self.rotation_mount_save(d))
        self.save_btn.grid(row=0, column=0, padx=10)

        self.cancel_btn = CTkButton(button_frame, text="Cancel", command=self.popup.destroy)
        self.cancel_btn.grid(row=0, column=1, padx=10)

        self.popup.transient(self)

    def begin_sweep(self, device):
        # Placeholder function for sweep logic        
        try:
            # Read and validate step angle
            degree_value = int(self.degree_entry.get()) if self.degree_entry.get() else int(self.degree_entry.placeholder_text)
            # Read start/stop angles, fall back to placeholders/defaults when empty
            start_text = self.start_entry.get() if hasattr(self, 'start_entry') else ''
            stop_text = self.stop_entry.get() if hasattr(self, 'stop_entry') else ''
            start_value = float(start_text) if start_text else float(self.start_entry.placeholder_text)
            stop_value = float(stop_text) if stop_text else float(self.stop_entry.placeholder_text)

            # Basic validation
            if degree_value <= 0:
                messagebox.showerror("Invalid Step Angle", "Step angle must be a positive integer.")
                return

            # Normalize angles into integers and a 0-360 range
            start_value = int(start_value) % 360
            # allow 360 as stop to represent full circle; normalize to 360 if entry is 360 specifically
            if float(stop_text) == 360.0 if stop_text else (float(self.stop_entry.placeholder_text) == 360.0):
                stop_value = 360
            else:
                stop_value = int(float(stop_value)) % 360

            device.start_sweep(degree_value, start_angle=start_value, stop_angle=stop_value)
            self.popup.destroy()
        except ValueError:
            messagebox.showerror("Invalid Step Angle", "Please enter a valid number.")
            return
        

    def rotation_mount_save(self, device):
        folder_name = self.text_entry.get()
        try:
            wavelength = float(self.num_entry.get())
        except ValueError:
            messagebox.showerror("Invalid Wavelength", "Please enter a valid number.")
            return

        print(wavelength)
        device.set_settings(wavelength, folder_name)
        self.popup.destroy()

    def open_stage_settings(self, device):
        # make the popup a child of the main app window
        self.popup = CTkToplevel(self.master)
        self.popup.title("Stage Settings")
        self.popup.geometry("700x420")
        # allow the user to resize the popup
        self.popup.resizable(True, True)
        # bring the popup to the front on open, then allow normal window behaviour
        # CTkToplevel internally toggles -topmost around 200ms after creation,
        # so we schedule our lift + clear after that internal handler finishes.
        def _ensure_on_top():
            try:
                self.popup.lift()
                self.popup.focus_force()
            except Exception:
                pass
            # clear topmost so the user can freely switch windows afterwards
            try:
                self.popup.after(100, lambda: self.popup.attributes("-topmost", False))
            except Exception:
                pass

        try:
            self.popup.attributes("-topmost", True)
            self.popup.lift()
            self.popup.focus_force()
            # run after CTkToplevel's internal topmost handler (~200ms)
            self.popup.after(500, _ensure_on_top)
        except Exception:
            pass

        def _on_popup_close():
            try:
                self.popup.destroy()
            except Exception:
                pass

        try:
            self.popup.protocol('WM_DELETE_WINDOW', _on_popup_close)
        except Exception:
            pass

        # Top label showing current Z position
        top_frame = CTkFrame(self.popup, fg_color="transparent")
        top_frame.pack(pady=(10, 5), fill="x")
        self.z_label = CTkLabel(top_frame, text="Z: 0.0000", font=("Arial", 14))
        self.z_label.pack()

        self._stage_body = CTkFrame(self.popup)
        self._stage_body.pack(padx=10, pady=5, fill="both", expand=True)
        self._stage_body.grid_rowconfigure(0, weight=1)
        self._stage_body.grid_columnconfigure(0, weight=1)

        # container pages — both sit in the same grid cell; only one visible at a time
        self._stage_page = CTkFrame(self._stage_body, fg_color="transparent")
        self._stage_page.grid(row=0, column=0, sticky="nsew")
        self._saved_page = CTkFrame(self._stage_body, fg_color="transparent")
        # start with saved page hidden
        self._saved_page.grid(row=0, column=0, sticky="nsew")
        self._saved_page.grid_remove()

        # Left: vertical slider with min/max displays (placed on stage page)
        # Read the device safety limit (in mm) if available; fall back to 3 mm
        try:
            slider_limit = device._position_limit_um / 1000.0
        except Exception:
            slider_limit = 3.0
        slider_steps = max(int(slider_limit * 2 / 0.05), 10)  # 50 µm per step

        slider_frame = CTkFrame(self._stage_page)
        slider_frame.grid(row=0, column=0, rowspan=3, padx=(10,20), sticky="ns")

        self.max_entry = CTkEntry(slider_frame, width=50, justify="center")
        self.max_entry.insert(0, str(slider_limit))
        self.max_entry.configure(state="disabled")
        self.max_entry.pack()

        # Vertical slider: make it thin and vertical
        try:
            self.stage_slider = CTkSlider(slider_frame, from_=slider_limit, to=-slider_limit, number_of_steps=slider_steps, orientation="vertical", height=220, width=20, command=self._on_slider_changed)
        except Exception:
            # fallback if orientation not supported
            self.stage_slider = CTkSlider(slider_frame, from_=slider_limit, to=-slider_limit, number_of_steps=slider_steps, command=self._on_slider_changed)
        self.stage_slider.pack(pady=5, fill="y", expand=True)

        self.min_entry = CTkEntry(slider_frame, width=50, justify="center")
        self.min_entry.insert(0, str(-slider_limit))
        self.min_entry.configure(state="disabled")
        self.min_entry.pack()

        # Middle: plus/minus controls and setpoint
        ctrl_frame = CTkFrame(self._stage_page, fg_color="transparent")
        ctrl_frame.grid(row=0, column=1, sticky="n", padx=(5,10))

        # plus/minus buttons
        pm_frame = CTkFrame(ctrl_frame, fg_color="transparent")
        pm_frame.pack(pady=(10,5))
        plus_btn = CTkButton(pm_frame, text="+", width=40, command=lambda: self._step_stage(device, 1))
        minus_btn = CTkButton(pm_frame, text="-", width=40, command=lambda: self._step_stage(device, -1))
        plus_btn.grid(row=0, column=0, padx=5)
        minus_btn.grid(row=1, column=0, padx=5, pady=(5,0))

        # Center setpoint entry with label
        setpoint_frame = CTkFrame(ctrl_frame, fg_color="transparent")
        setpoint_frame.pack(pady=(10,5))
        lbl = CTkLabel(setpoint_frame, text="Move to position:")
        lbl.grid(row=0, column=0, padx=(0,8))
        self.setpoint_entry = CTkEntry(setpoint_frame, width=120, placeholder_text="0.0")
        self.setpoint_entry.grid(row=0, column=1)

        # Button row: Go, Save Position, Set Zero
        btn_row = CTkFrame(ctrl_frame, fg_color="transparent")
        btn_row.pack(pady=(15,5))
        go_btn = CTkButton(btn_row, text="Go", width=80, command=lambda d=device: self._go_to_setpoint(d))
        save_btn = CTkButton(btn_row, text="Save Position", width=100, command=lambda d=device: self._save_position(d))
        zero_btn = CTkButton(btn_row, text="Set Zero", width=80, command=lambda d=device: self._set_zero(d))
        go_btn.grid(row=0, column=0, padx=5)
        save_btn.grid(row=0, column=1, padx=5)
        zero_btn.grid(row=0, column=2, padx=5)

        # Right: Step size and mode
        right_frame = CTkFrame(self._stage_page, fg_color="transparent")
        right_frame.grid(row=0, column=2, sticky="n", padx=(10,5))

        step_frame = CTkFrame(right_frame, fg_color="transparent")
        step_frame.pack(pady=(20,5))
        # units are always millimetres for the stage control panel
        CTkLabel(step_frame, text="Step size (mm)").grid(row=0, column=0, sticky="w")
        self.step_entry = CTkEntry(step_frame, width=80)
        self.step_entry.insert(0, "0.5")
        self.step_entry.grid(row=0, column=1, padx=(8,0))

        # Mode (Coarse/Fine) - implemented as simple option menu
        mode_frame = CTkFrame(right_frame, fg_color="transparent")
        mode_frame.pack(pady=(10,5))
        CTkLabel(mode_frame, text="Mode:").grid(row=0, column=0, sticky="w")
        try:
            self.mode_menu = CTkOptionMenu(mode_frame, values=["Coarse","Fine"]) 
            self.mode_menu.set("Coarse")
            self.mode_menu.grid(row=0, column=1, padx=(8,0))
            # attach behaviour when the user switches mode
            self.mode_menu.configure(command=lambda _v=None: self._on_mode_change())
        except Exception:
            # fallback: use an entry to display mode (read-only)
            self.mode_var = CTkEntry(mode_frame, width=80)
            self.mode_var.insert(0, "Coarse")
            self.mode_var.configure(state="disabled")
            self.mode_var.grid(row=0, column=1, padx=(8,0))

        # initialize displayed values
        try:
            current = float(getattr(device, 'get_position', lambda: 0)())
        except Exception:
            current = 0.0
        self._update_z_display(current)
        try:
            self.stage_slider.set(current)
        except Exception:
            pass

        # small helper: update label periodically if device provides position
        def _periodic_update():
            try:
                pos = float(getattr(device, 'get_position', lambda: None)() or 0)
                self._update_z_display(pos)
                try:
                    self.stage_slider.set(pos)
                except Exception:
                    pass
            except Exception:
                pass
            self.popup.after(200, _periodic_update)

        _periodic_update()

        # Footer: saved positions button on the right for stage control page
        self._footer = CTkFrame(self.popup, fg_color="transparent")
        self._footer.pack(fill="x", padx=10, pady=(6,10))
        self._saved_btn = CTkButton(self._footer, text="Saved positions", width=140, command=lambda d=device: self._show_saved_positions(d))
        self._saved_btn.pack(side="right")

    def _show_saved_positions(self, device):
        # hide stage page, show saved positions page
        try:
            self._stage_page.grid_remove()
        except Exception:
            pass

        # destroy old saved-page content and rebuild
        try:
            for w in list(self._saved_page.winfo_children()):
                w.destroy()
        except Exception:
            pass

        header = CTkLabel(self._saved_page, text="Saved positions:", font=("Arial", 14))
        header.pack(pady=(10,8))

        # list saved positions from device.saved_positions if available
        positions = getattr(device, 'saved_positions', None)
        if not positions:
            # try single saved_position
            sp = getattr(device, 'saved_position', None)
            positions = [sp] if sp is not None else []

        if positions:
            for idx, entry in enumerate(positions, start=1):
                # entries can be (name, pos) tuples or bare floats (legacy)
                if isinstance(entry, (list, tuple)) and len(entry) == 2:
                    label_name, pos_val = entry[0], entry[1]
                else:
                    label_name, pos_val = None, entry
                try:
                    pos_float = float(pos_val)
                    if label_name:
                        btn_text = f"{label_name}  ({pos_float:.4f} mm)"
                    else:
                        btn_text = f"{idx}: {pos_float:.4f} mm"
                except Exception:
                    btn_text = f"{idx}: {entry}"
                    pos_float = None
                btn = CTkButton(self._saved_page, text=btn_text, width=260,
                                fg_color="transparent", border_width=2, border_color="#1F6AA5",
                                anchor="w")
                if pos_float is not None:
                    # capture pos_float by value for the lambda
                    btn.configure(command=lambda d=device, p=pos_float: self._go_to_saved_position(d, p))
                else:
                    btn.configure(state="disabled")
                btn.pack(anchor="w", padx=20, pady=3)
        else:
            CTkLabel(self._saved_page, text="(No saved positions)").pack(pady=10)

        # footer for saved page: back button on left
        for child in list(self._footer.winfo_children()):
            try:
                child.pack_forget()
            except Exception:
                pass
        back_btn = CTkButton(self._footer, text="Stage control", width=140, command=lambda d=device: self._show_stage_control(d))
        back_btn.pack(side="left")

        self._saved_page.grid(row=0, column=0, sticky="nsew")

    def _show_stage_control(self, device):
        # hide saved page, show stage page
        try:
            self._saved_page.grid_remove()
        except Exception:
            pass
        # restore footer saved button
        for child in list(self._footer.winfo_children()):
            try:
                child.pack_forget()
            except Exception:
                pass
        self._saved_btn.pack(side="right")
        self._stage_page.grid(row=0, column=0, sticky="nsew")

    # --- Stage control helper methods ---
    def _update_z_display(self, value):
        try:
            self.z_label.configure(text=f"Z: {float(value):.4f}")
        except Exception:
            self.z_label.configure(text=f"Z: {value}")

    def _on_slider_changed(self, value):
        # update setpoint entry when slider moves
        try:
            v = float(value)
            self.setpoint_entry.delete(0, "end")
            self.setpoint_entry.insert(0, f"{v:.4f}")
            self._update_z_display(v)
        except Exception:
            pass

    def _on_mode_change(self, *_args):
        """Adjust the step-entry value when the mode dropdown changes.

        *Coarse* -> *Fine* multiplies current step by 0.1.
        *Fine* -> *Coarse* multiplies by 10.  This behaviour ensures
a single additional decimal place is added or removed, matching the
user request.
        """
        try:
            val = float(self.step_entry.get())
        except Exception:
            return
        mode = None
        try:
            mode = self.mode_menu.get()
        except Exception:
            # fallback entry contains the text
            mode = getattr(self, 'mode_var', None) and self.mode_var.get()
        if mode == "Fine":
            new = val * 0.1
        else:
            new = val * 10.0
        # format with appropriate precision (always show one or two decimals)
        fmt = "{:.2f}" if mode == "Fine" else "{:.1f}"
        self.step_entry.delete(0, "end")
        self.step_entry.insert(0, fmt.format(new))

    def _step_stage(self, device, direction):
        # step by the step size (direction: 1 or -1)
        try:
            step = float(self.step_entry.get())
        except Exception:
            step = 0.5
        delta = step * (1 if direction > 0 else -1)

        def _worker():
            try:
                if hasattr(device, 'step'):
                    device.step(delta)
                elif hasattr(device, 'move_by'):
                    device.move_by(delta)
                elif hasattr(device, 'get_position') and hasattr(device, 'move_to'):
                    cur = float(device.get_position() or 0)
                    device.move_to(cur + delta)
                else:
                    self.after(0, lambda: messagebox.showinfo("Not implemented", "Stage stepping not implemented for this device."))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", f"Unable to step stage: {e}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _go_to_setpoint(self, device):
        try:
            target = float(self.setpoint_entry.get())
        except Exception:
            messagebox.showerror("Invalid value", "Please enter a valid numeric setpoint.")
            return

        def _worker():
            try:
                if hasattr(device, 'move_to'):
                    device.move_to(target)
                elif hasattr(device, 'set_position'):
                    device.set_position(target)
                else:
                    self.after(0, lambda: messagebox.showinfo("Not implemented", "Direct move not implemented for this device."))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", f"Unable to move stage: {e}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _set_zero(self, device):
        def _worker():
            try:
                if hasattr(device, 'set_zero'):
                    device.set_zero()
                elif hasattr(device, 'move_to'):
                    device.move_to(0)
                else:
                    self.after(0, lambda: messagebox.showinfo("Not implemented", "Set zero not implemented for this device."))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", f"Unable to set zero: {e}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _go_to_saved_position(self, device, pos):
        """Move the stage to a previously saved position (threaded)."""
        def _worker():
            try:
                if hasattr(device, 'move_to'):
                    device.move_to(pos)
                elif hasattr(device, 'set_position'):
                    device.set_position(pos)
                else:
                    self.after(0, lambda: messagebox.showinfo("Not implemented", "Direct move not implemented for this device."))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", f"Unable to move to saved position: {e}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _save_position(self, device):
        try:
            pos = None
            if hasattr(device, 'get_position'):
                pos = float(device.get_position() or 0)
            if pos is None:
                messagebox.showinfo("Save", "Could not read current position to save.")
                return
            # prompt user for a name
            name = simpledialog.askstring("Save Position", f"Position: {pos:.4f} mm\nEnter a name:",
                                          parent=self.popup if hasattr(self, 'popup') and self.popup else self)
            if not name:
                return  # user cancelled
            # store on device as (name, position) tuples
            try:
                if not hasattr(device, 'saved_positions'):
                    device.saved_positions = []
                device.saved_positions.append((name.strip(), pos))
                device.saved_position = pos
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Error", f"Unable to save position: {e}")


class DeviceEntry:
    """Class to simplify connection between devices and graphic frame elements"""

    def __init__(self, switch, device, widgets=[], frame=None):
        """Create object to simplify connection between devices and graphic frame elements

        Notes
        ------------
        In the setup frame, a space is created for each device associated with the microscope to enable control.
        Each device is equipped with a switch button to connect or disconnect it, 
        along with specific elements tailored to the device type. 
        Some devices can also be controlled from another, more specific frame

        Each widget can be associated with a keyword, allowing it to be treated differently

        Parameters
        ------------
        switch : `CTkSwitch`
            Contains the swicth associated with a device
        device : `class`
            Object containing all the information related to a device
        widgets : `list(CTk class)`, optional
            List of additional objects specific to a device type, Empty by default
        frame : `CTK`, optional
            Corresponds to a device control frame
        """
        self.switch = switch
        self.device = device
        self.widgets = widgets
        self.frame = frame


    def activate(self):
        """For a device, update the graphical content of the element to match the activation state
        """
        self.switch.select()
        self.update_widgets_state("normal")


    def desactivate(self):
        """For a device, update the graphical content of the element to match the desactivation state
        """
        self.switch.deselect()
        self.update_widgets_state("disabled")


    def update_widgets_state(self, state):
        """For all elements associated with a switch, update the graphical content with the requested state

        Notes
        ------------
        Each widget can be associated with a keyword, allowing it to be treated differently

        Parameters
        ------------
        state : `str`
            Corresponds to the graphic state you wish to apply to an element (normal/disabled)
        """
        for widget, type in self.widgets:
            if type != "NonDisableable":
                widget.configure(state=state)
            if type == "Shutter":
                update_shutter_button_style(widget, self.device)


    def is_device_connected(self):
        """Provides device connection status

        Returns
        ---------
        is_device_connected : `bool`
            Provides device connection status (True/False)
        """
        return self.device.connected



def update_shutter_button_style(widget, device):
    """Updates the graphic content of the shutter open/close button according to the actual state of the device

    Parameters
    ------------
    widget : `CTkButton`
        Graphic element associated with the shutter
    device : `MyShutter`
        Object containing all the information related to a shutter
    """
    if device.state():
        widget.configure(text="Open", border_color="#009200", hover_color="#004b00")
    else:
        widget.configure(text="Close", border_color="#920000", hover_color="#4b0000")


class RoutinesFrame(CTkScrollableFrame):
    """Secondary left-side menu for routines.

    Adds a "Polarizer sweep" routine that opens a multi-page popup. This initial
    implementation provides page 1 (configure parameters) and a minimal confirmation
    page. The actual sweep start is a placeholder — it should later call into the
    appropriate `MyRotationMount.start_sweep` method.
    """
    def __init__(self, master, microscope):
        super().__init__(master)
        self.microscope = microscope
        self.popup = None
        self.grid_columnconfigure(0, weight=1)

        title = CTkLabel(self, text="Routines", font=HEADLINE_FONT)
        title.grid(row=0, column=0, padx=20, pady=(12, 6), sticky="w")

        # Polarizer sweep routine button
        self.polarizer_btn = CTkButton(self, text="Polarizer sweep", width=200, command=self.open_polarizer_sweep_popup)
        self.polarizer_btn.grid(row=1, column=0, padx=20, pady=(8, 6), sticky="w")

        # Additional placeholders for future routines (kept for layout parity)
        self.other_btn_1 = CTkButton(self, text="Routine 2", width=200, command=lambda: self.run_routine(2))
        self.other_btn_1.grid(row=2, column=0, padx=20, pady=6, sticky="w")
        self.other_btn_2 = CTkButton(self, text="Routine 3", width=200, command=lambda: self.run_routine(3))
        self.other_btn_2.grid(row=3, column=0, padx=20, pady=6, sticky="w")

        # match QuickSetupFrame behavior for scrollbar heuristics
        self.update_idletasks()
        try:
            self.required_height_for_scrollbar = self.winfo_reqheight()
        except Exception:
            self.required_height_for_scrollbar = 0
        try:
            self.previous_frame_height = self.master.winfo_height()
        except Exception:
            self.previous_frame_height = 0
        try:
            self.master.bind("<Configure>", lambda event: self.update_scrollbar_visibility())
        except Exception:
            pass

    def run_routine(self, n):
        # simple notification for placeholder routines
        try:
            self.master.notification(f"Started routine {n}")
        except Exception:
            pass

    def update_scrollbar_visibility(self):
        """Hide/show the scrollbar depending on available space (same logic as QuickSetupFrame)."""
        current_height = self.master.winfo_height()
        if current_height != getattr(self, "previous_frame_height", None):
            self.previous_frame_height = current_height
            if getattr(self, "required_height_for_scrollbar", 0) > current_height:
                try:
                    self._scrollbar.grid(column=1, row=1, pady=6, sticky="nesw")
                except Exception:
                    pass
            else:
                try:
                    self._scrollbar.grid_forget()
                except Exception:
                    pass

    # --- Polarizer sweep popup (page 1: configure) ---
    def open_polarizer_sweep_popup(self):
        """Open the polarizer sweep configuration popup (page 1).

        Page 1 contains three textboxes: step angle, start angle, stop angle, and
        a 'Next' button that proceeds to a confirmation page.
        """
        if self.popup:
            try:
                self.popup.lift()
            except Exception:
                pass
            return

        # ensure a new SweepRoutine container exists for this run (best-effort)
        try:
            self._ensure_sweep_routine_folder()
        except Exception:
            pass

        # make the popup a child of the main app window so it stays above it
        self.popup = CTkToplevel(self.master)
        self.popup.title("Polarizer sweep")
        self.popup.geometry("420x300")
        self.popup.resizable(False, False)
        self.popup.protocol("WM_DELETE_WINDOW", self.close_popup)
        # ensure the popup appears above the main window on open
        try:
            self.popup.attributes("-topmost", True)
            self.popup.transient(self.master)
            # clear the topmost flag shortly after so modality returns to normal
            self.after(50, lambda: self.popup.attributes("-topmost", False))
        except Exception:
            pass

        self.page_frame = CTkFrame(self.popup)
        self.page_frame.pack(fill="both", expand=True, padx=16, pady=12)

        # build first page (may be reused when navigating back)
        self._build_page1()
        self.popup.focus_force()

    def _build_page1(self, step_val=None, start_val=None, stop_val=None):
        """Construct page 1: Configure sweep parameters.

        If values are provided, they are inserted into the entries.
        """
        # clear any existing content
        for w in getattr(self, 'page_frame', []).winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        headline = CTkLabel(self.page_frame, text="Configure sweep parameters", font=("Arial", 16))
        headline.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        CTkLabel(self.page_frame, text="Step angle (°):").grid(row=1, column=0, sticky="w", pady=6)
        self._step_entry = CTkEntry(self.page_frame, width=140, placeholder_text="1")
        self._step_entry.grid(row=1, column=1, sticky="e", pady=6)
        if step_val is not None:
            try:
                self._step_entry.delete(0, 'end')
                self._step_entry.insert(0, str(step_val))
            except Exception:
                pass

        CTkLabel(self.page_frame, text="Start angle (°):").grid(row=2, column=0, sticky="w", pady=6)
        self._start_entry = CTkEntry(self.page_frame, width=140, placeholder_text="0")
        self._start_entry.grid(row=2, column=1, sticky="e", pady=6)
        if start_val is not None:
            try:
                self._start_entry.delete(0, 'end')
                self._start_entry.insert(0, str(start_val))
            except Exception:
                pass

        CTkLabel(self.page_frame, text="Stop angle (°):").grid(row=3, column=0, sticky="w", pady=6)
        self._stop_entry = CTkEntry(self.page_frame, width=140, placeholder_text="360")
        self._stop_entry.grid(row=3, column=1, sticky="e", pady=6)
        if stop_val is not None:
            try:
                self._stop_entry.delete(0, 'end')
                self._stop_entry.insert(0, str(stop_val))
            except Exception:
                pass

        footer = CTkFrame(self.popup, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(8, 12))
        next_btn = CTkButton(footer, text="Next", width=120, command=self._polarizer_popup_next)
        next_btn.pack(side="right")

    def _polarizer_popup_next(self):
        """Validate page 1 values and show a minimal confirmation page (page 2)."""
        try:
            step_text = self._step_entry.get().strip() or self._step_entry.placeholder_text or "1"
            start_text = self._start_entry.get().strip() or self._start_entry.placeholder_text or "0"
            stop_text = self._stop_entry.get().strip() or self._stop_entry.placeholder_text or "360"

            step = float(step_text)
            start = float(start_text)
            stop = float(stop_text)
        except Exception:
            try:
                self.notification("Invalid input", color="#8e0101")
            except Exception:
                pass
            return
        # clear page and store validated sweep parameters to allow navigation back
        try:
            for w in self.page_frame.winfo_children():
                w.destroy()
        except Exception:
            pass

        # store validated sweep parameters to allow navigation back
        self._pending_sweep_params = (step, start, stop)

        # build second page: Configure data to record
        headline = CTkLabel(self.page_frame, text="Configure data to record", font=("Arial", 16))
        headline.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        CTkLabel(self.page_frame, text="Number of dark reference(s):").grid(row=1, column=0, sticky="w", pady=6)
        self._dark_refs_entry = CTkEntry(self.page_frame, width=140, placeholder_text="1")
        self._dark_refs_entry.grid(row=1, column=1, sticky="e", pady=6)

        CTkLabel(self.page_frame, text="Number of light reference(s):").grid(row=2, column=0, sticky="w", pady=6)
        self._light_refs_entry = CTkEntry(self.page_frame, width=140, placeholder_text="1")
        self._light_refs_entry.grid(row=2, column=1, sticky="e", pady=6)

        CTkLabel(self.page_frame, text="Number of sweeps:").grid(row=3, column=0, sticky="w", pady=6)
        self._sweeps_entry = CTkEntry(self.page_frame, width=140, placeholder_text="1")
        self._sweeps_entry.grid(row=3, column=1, sticky="e", pady=6)

        # Footer
        for child in list(self.popup.winfo_children()):
            if isinstance(child, CTkFrame) and child is not self.page_frame:
                try:
                    child.destroy()
                except Exception:
                    pass

        footer = CTkFrame(self.popup, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(8, 12))
        back_btn = CTkButton(footer, text="Back", width=120, command=self._polarizer_page2_back)
        back_btn.pack(side="left")
        next_btn = CTkButton(footer, text="Next", width=120, command=self._polarizer_page2_next)
        next_btn.pack(side="right")

    def _polarizer_page2_back(self):
        """Return from page 2 to page 1, preserving entered sweep parameters."""
        if not self.popup:
            return
        # read stored pending params if available
        step = start = stop = None
        if hasattr(self, '_pending_sweep_params') and self._pending_sweep_params:
            try:
                step, start, stop = self._pending_sweep_params
            except Exception:
                step = start = stop = None

        # remove any extra footer frames
        try:
            for child in list(self.popup.winfo_children()):
                if isinstance(child, CTkFrame) and child is not self.page_frame:
                    try:
                        child.destroy()
                    except Exception:
                        pass
        except Exception:
            pass

        # clear page and rebuild page1 with preserved values
        try:
            for w in self.page_frame.winfo_children():
                w.destroy()
        except Exception:
            pass

        self._build_page1(step, start, stop)

    def _polarizer_page2_next(self):
        """Validate data entries on page 2 and start the sweep using the first available rotation mount.

        Saves the entered dark/light reference counts and sweeps into `self._pending_data_config`.
        Attempts to find a `MyRotationMount` in the currently selected microscope and calls
        its `start_sweep` method. If none is found, shows a notification.
        """
        # Validate integer inputs
        try:
            dark_count = int(self._dark_refs_entry.get() or self._dark_refs_entry.placeholder_text)
            light_count = int(self._light_refs_entry.get() or self._light_refs_entry.placeholder_text)
            sweeps_count = int(self._sweeps_entry.get() or self._sweeps_entry.placeholder_text)
            if dark_count < 0 or light_count < 0 or sweeps_count <= 0:
                raise ValueError("Counts must be positive")
        except Exception:
            try:
                self.notification("Invalid data configuration", color="#8e0101")
            except Exception:
                pass
            return

        # store pending data config and navigate to the dark-reference recording page
        self._pending_data_config = {'dark_refs': dark_count, 'light_refs': light_count, 'sweeps': sweeps_count}

        # ensure sweep parameters exist
        if not hasattr(self, '_pending_sweep_params') or not self._pending_sweep_params:
            try:
                self.notification("Sweep parameters missing", color="#8e0101")
            except Exception:
                pass
            # navigate back to page 1
            self._polarizer_page2_back()
            return

        # Build page 3: Record dark references
        self._build_page3()

    def _build_page3(self):
        """Page 3: Record dark reference(s).

        Shows headline "Record dark reference(s)", a centered button to record the dark
        references and footer with Back and Next (Next disabled until recording completes).
        """
        # clear page
        try:
            for w in self.page_frame.winfo_children():
                w.destroy()
        except Exception:
            pass

        headline = CTkLabel(self.page_frame, text="Record dark reference(s)", font=("Arial", 16))
        headline.grid(row=0, column=0, columnspan=3, sticky="n", pady=(8, 12))

        # centered record button
        self._record_button = CTkButton(self.page_frame, text="Record dark reference(s)", width=220, command=self._record_dark_refs)
        self._record_button.grid(row=1, column=0, columnspan=3, pady=(20, 6))

        # status label
        self._record_status_label = CTkLabel(self.page_frame, text="Not recorded", font=("Arial", 12), text_color="grey")
        self._record_status_label.grid(row=2, column=0, columnspan=3, pady=(6, 6))

        # Footer: Back + Next (Next disabled until recorded)
        for child in list(self.popup.winfo_children()):
            if isinstance(child, CTkFrame) and child is not self.page_frame:
                try:
                    child.destroy()
                except Exception:
                    pass

        footer = CTkFrame(self.popup, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(8, 12))
        back_btn = CTkButton(footer, text="Back", width=120, command=self._polarizer_page3_back)
        back_btn.pack(side="left")
        self._page3_next_btn = CTkButton(footer, text="Next", width=120, state="disabled", command=self._polarizer_page3_next)
        self._page3_next_btn.pack(side="right")

    def _polarizer_page3_back(self):
        """Return from page 3 to page 2, preserving data config entries."""
        # rebuild page2 with previous entries
        if not self.popup:
            return
        try:
            # clear footers
            for child in list(self.popup.winfo_children()):
                if isinstance(child, CTkFrame) and child is not self.page_frame:
                    try:
                        child.destroy()
                    except Exception:
                        pass
        except Exception:
            pass

        # rebuild page2 UI with preserved entries
        try:
            for w in self.page_frame.winfo_children():
                w.destroy()
        except Exception:
            pass

        # reuse values from _pending_data_config if available
        dark = light = sweeps = None
        if hasattr(self, '_pending_data_config') and self._pending_data_config:
            try:
                dark = self._pending_data_config.get('dark_refs')
                light = self._pending_data_config.get('light_refs')
                sweeps = self._pending_data_config.get('sweeps')
            except Exception:
                dark = light = sweeps = None

        # rebuild page2 content
        headline = CTkLabel(self.page_frame, text="Configure data to record", font=("Arial", 16))
        headline.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        CTkLabel(self.page_frame, text="Number of dark reference(s):").grid(row=1, column=0, sticky="w", pady=6)
        self._dark_refs_entry = CTkEntry(self.page_frame, width=140, placeholder_text="1")
        self._dark_refs_entry.grid(row=1, column=1, sticky="e", pady=6)
        if dark is not None:
            try:
                self._dark_refs_entry.delete(0, 'end')
                self._dark_refs_entry.insert(0, str(dark))
            except Exception:
                pass

        CTkLabel(self.page_frame, text="Number of light reference(s):").grid(row=2, column=0, sticky="w", pady=6)
        self._light_refs_entry = CTkEntry(self.page_frame, width=140, placeholder_text="1")
        self._light_refs_entry.grid(row=2, column=1, sticky="e", pady=6)
        if light is not None:
            try:
                self._light_refs_entry.delete(0, 'end')
                self._light_refs_entry.insert(0, str(light))
            except Exception:
                pass

        CTkLabel(self.page_frame, text="Number of sweeps:").grid(row=3, column=0, sticky="w", pady=6)
        self._sweeps_entry = CTkEntry(self.page_frame, width=140, placeholder_text="1")
        self._sweeps_entry.grid(row=3, column=1, sticky="e", pady=6)
        if sweeps is not None:
            try:
                self._sweeps_entry.delete(0, 'end')
                self._sweeps_entry.insert(0, str(sweeps))
            except Exception:
                pass

        footer = CTkFrame(self.popup, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(8, 12))
        back_btn = CTkButton(footer, text="Back", width=120, command=self._polarizer_page2_back)
        back_btn.pack(side="left")
        next_btn = CTkButton(footer, text="Next", width=120, command=self._polarizer_page2_next)
        next_btn.pack(side="right")

    def _record_dark_refs(self):
        """Record dark references the requested number of times in a background thread.

        Enables the Next button on completion.
        """
        # Prefer the value stored in pending config (from page2). Fallback to entry if present.
        try:
            if hasattr(self, '_pending_data_config') and self._pending_data_config:
                count = int(self._pending_data_config.get('dark_refs', 1))
            else:
                count = int(self._dark_refs_entry.get() or self._dark_refs_entry.placeholder_text)
        except Exception:
            count = 1
        

        # Reset per-run counters so repeated runs don't accumulate state
        try:
            self._light_recorded = 0
            self._sample_recorded = 0
        except Exception:
            pass

        debugp("Routines", f"Starting dark reference recording x{count}")

        # Best-effort: close any KST201 shutters on the microscope before recording dark references.
        closed_shutters = []
        try:
            # prefer explicit microscope reference passed into the frame
            microscope = getattr(self, 'microscope', None) or getattr(self.master, 'selected_microscope', None)
            if microscope and hasattr(microscope, 'devices'):
                for dev in microscope.devices:
                    try:
                        # target MyShutter wrappers backed by KST201 devices specifically
                        if isinstance(dev, MyShutter) and getattr(dev, 'model', None) == 'KST201':
                            try:
                                dev.close()
                                closed_shutters.append(dev)
                                debugp("Routines", f"Closed KST201 shutter: {dev}")
                            except Exception as e:
                                debugp("Routines", f"Failed to close KST201 shutter {dev}: {e}")
                    except Exception:
                        # ignore devices that don't match
                        pass
        except Exception as e:
            debugp("Routines", f"Error while closing shutters: {e}")

        # disable record button and update status
        try:
            self._record_button.configure(state="disabled", text="Recording...")
            self._record_status_label.configure(text=f"Recording 0/{count}")
        except Exception:
            pass

        def _worker():
            # aggregated saved directories across all iterations
            saved_dirs = []
            recorded = 0

            for i in range(count):
                try:
                    # locate spectrometer_frame in case widget hierarchy differs
                    spec_frame = None
                    try:
                        if hasattr(self.master, 'spectrometer_frame') and getattr(self.master, 'spectrometer_frame'):
                            spec_frame = self.master.spectrometer_frame
                        elif hasattr(self.master, 'master') and hasattr(self.master.master, 'spectrometer_frame') and getattr(self.master.master, 'spectrometer_frame'):
                            spec_frame = self.master.master.spectrometer_frame
                        elif hasattr(self.master, 'master') and hasattr(self.master.master, 'master') and hasattr(self.master.master.master, 'spectrometer_frame'):
                            spec_frame = self.master.master.master.spectrometer_frame
                    except Exception:
                        spec_frame = None

                    if not spec_frame:
                        # fallback: notify and break (call app notification directly)
                        try:
                            self.master.notification("No spectrometer available", None, "#8e0101")
                        except Exception:
                            pass
                        break

                    # Ensure spectrometer is running so chart_queue has data
                    try:
                        if spec_frame.connected_spectrometers and not spec_frame.connected_spectrometers[0].is_running:
                            spec_frame.start_spectrometer(spec_frame.connected_spectrometers[0])
                    except Exception:
                        pass

                    # request dark reference; allow spectrometer_frame to show its per-file notification
                    try:
                        # enable per-iteration notifications so the user sees confirmation for each saved dark reference
                        result = spec_frame.set_dark_reference(display_notification=True)
                    except Exception as e:
                        debugp("Routines", f"set_dark_reference error: {e}")
                        result = None

                    # wait for spectrometer saving to finish (best-effort)
                    try:
                        wait_spec = None
                        if spec_frame and getattr(spec_frame, 'connected_spectrometers', None):
                            wait_spec = spec_frame.connected_spectrometers[0]
                    except Exception:
                        wait_spec = None

                    start_time_local = time.time()
                    timeout_local = 60 * 2  # 2 minutes per dark reference
                    while True:
                        try:
                            if wait_spec is None or getattr(wait_spec, 'acquire_save_data', 0) == 0:
                                break
                        except Exception:
                            break
                        if time.time() - start_time_local > timeout_local:
                            debugp("Routines", f"Dark reference save timed out for iteration {i+1}")
                            break
                        time.sleep(0.2)

                    # consider this iteration successful (increment) even if result is None but wait finished;
                    # aggregate returned saved dirs if any
                    try:
                        if result:
                            # result may be a list of saved directories (one per spectrometer)
                            if isinstance(result, (list, tuple)):
                                saved_dirs.extend(result)
                            else:
                                saved_dirs.append(result)
                    except Exception:
                        # ignore aggregation errors
                        pass

                    # increment recorded count now that save/wait is done
                    recorded += 1

                except Exception as e:
                    debugp("Routines", f"Error recording dark reference: {e}")
                finally:
                    # update status label from main thread
                    def _update_status(r=recorded):
                        try:
                            self._record_status_label.configure(text=f"Recorded {r}/{count}")
                        except Exception:
                            pass
                    self.after(0, _update_status)
                    time.sleep(0.3)

            # enable Next button on completion
            def _on_done():
                try:
                    self._record_button.configure(state="normal", text="Record dark reference(s)")
                except Exception:
                    pass
                try:
                    self._page3_next_btn.configure(state="normal")
                    self._record_status_label.configure(text=f"Recorded {recorded}/{count}")
                except Exception:
                    pass
                # Re-open any shutters we closed before recording (best-effort)
                try:
                    for sh in closed_shutters:
                        try:
                            if hasattr(sh, 'open'):
                                sh.open()
                        except Exception as e:
                            debugp("Routines", f"Failed to reopen shutter {sh}: {e}")
                except Exception:
                    pass

                # Single end-of-process notification (include folder if available)
                try:
                    folder_msg = None
                    if saved_dirs:
                        # prefer first directory
                        folder_msg = saved_dirs[0]
                    if recorded > 0:
                        try:
                            if folder_msg:
                                # call application notification directly: head_message, message, color
                                self.master.notification(f"Recorded {recorded} dark reference(s)", f"Saved to: {folder_msg}", "#1a8300")
                            else:
                                self.master.notification(f"Recorded {recorded} dark reference(s)", None, "#1a8300")
                        except Exception:
                            pass
                except Exception:
                    pass

            self.after(0, _on_done)

        threading.Thread(target=_worker, daemon=True).start()

    def _polarizer_page3_next(self):
        """Proceed to the light-reference recording page after dark refs are done."""
        # Build page 4 (light references)
        self._build_page4()

    def _build_page4(self):
        """Page 4: Record light reference(s). Similar to page 3."""
        try:
            for w in self.page_frame.winfo_children():
                w.destroy()
        except Exception:
            pass

        headline = CTkLabel(self.page_frame, text="Record light reference(s)", font=("Arial", 16))
        headline.grid(row=0, column=0, columnspan=3, sticky="n", pady=(8, 12))
        # Instruction text for light reference sweeps
        try:
            total_light_refs = int(self._pending_data_config.get('light_refs', 1)) if hasattr(self, '_pending_data_config') and self._pending_data_config else 1
        except Exception:
            total_light_refs = 1

        instruct = CTkLabel(self.page_frame, text=f"Move sample to a blank (reference) surface and record {total_light_refs} light reference sweep(s).\nYou will trigger each sweep manually by clicking the button below.", font=("Arial", 12), text_color="white", justify="center")
        instruct.grid(row=1, column=0, columnspan=3, pady=(6, 12))

        # centered record button. Button text is dynamic to indicate which reference will be recorded next.
        self._light_total = total_light_refs
        self._light_recorded = getattr(self, '_light_recorded', 0)
        btn_text = f"Record light reference {self._light_recorded + 1}" if self._light_recorded < self._light_total else "Record light reference"
        self._record_light_button = CTkButton(self.page_frame, text=btn_text, width=280, command=self._record_light_refs)
        self._record_light_button.grid(row=2, column=0, columnspan=3, pady=(6, 6))

        # status label
        self._record_light_status_label = CTkLabel(self.page_frame, text=f"Recorded {self._light_recorded}/{self._light_total}", font=("Arial", 12), text_color="grey")
        self._record_light_status_label.grid(row=3, column=0, columnspan=3, pady=(6, 6))

        # Footer: Back + Next (Next disabled until recorded)
        for child in list(self.popup.winfo_children()):
            if isinstance(child, CTkFrame) and child is not self.page_frame:
                try:
                    child.destroy()
                except Exception:
                    pass

        footer = CTkFrame(self.popup, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(8, 12))
        back_btn = CTkButton(footer, text="Back", width=120, command=self._polarizer_page4_back)
        back_btn.pack(side="left")
        self._page4_next_btn = CTkButton(footer, text="Next", width=120, state="disabled", command=self._polarizer_page4_next)
        self._page4_next_btn.pack(side="right")

    def _polarizer_page4_back(self):
        """Return from page 4 to page 3."""
        # rebuild page3
        try:
            for w in self.page_frame.winfo_children():
                w.destroy()
        except Exception:
            pass
        self._build_page3()

    def _build_page5(self):
        """Page 5: Sample sweeps. User triggers each sweep manually; Finish button closes popup."""
        try:
            for w in self.page_frame.winfo_children():
                w.destroy()
        except Exception:
            pass

        # total sample sweeps
        try:
            total = int(self._pending_data_config.get('sweeps', 1)) if hasattr(self, '_pending_data_config') and self._pending_data_config else 1
        except Exception:
            total = 1

        self._sample_total = total
        self._sample_recorded = getattr(self, '_sample_recorded', 0)

        # Instruction text: first vs subsequent
        if self._sample_recorded == 0:
            instruct_text = "Align with structure to sweep and click the button below"
        else:
            instruct_text = "Move and align with the next structure to sweep and click the button below"

        instruct = CTkLabel(self.page_frame, text=instruct_text, font=("Arial", 12), text_color="white", justify="center")
        instruct.grid(row=0, column=0, columnspan=3, pady=(8, 12))

        # dynamic record button
        btn_text = f"Record sweep {self._sample_recorded + 1}" if self._sample_recorded < self._sample_total else "Record sweep"
        self._record_sample_button = CTkButton(self.page_frame, text=btn_text, width=280, command=self._record_sample_sweep)
        self._record_sample_button.grid(row=1, column=0, columnspan=3, pady=(6, 6))

        # status label
        self._record_sample_status_label = CTkLabel(self.page_frame, text=f"Recorded {self._sample_recorded}/{self._sample_total}", font=("Arial", 12), text_color="grey")
        self._record_sample_status_label.grid(row=2, column=0, columnspan=3, pady=(6, 6))

        # Footer: Back + Finish (Finish disabled until done)
        for child in list(self.popup.winfo_children()):
            if isinstance(child, CTkFrame) and child is not self.page_frame:
                try:
                    child.destroy()
                except Exception:
                    pass

        footer = CTkFrame(self.popup, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(8, 12))
        back_btn = CTkButton(footer, text="Back", width=120, command=self._polarizer_page5_back)
        back_btn.pack(side="left")
        self._finish_btn = CTkButton(footer, text="Finish", width=120, state="disabled", command=self._polarizer_page5_finish)
        self._finish_btn.pack(side="right")

    def _polarizer_page5_back(self):
        """Go back to light reference page."""
        try:
            for w in self.page_frame.winfo_children():
                w.destroy()
        except Exception:
            pass
        # preserve state and go back to page4 UI
        self._build_page4()


    def _build_page5(self):
        """Page 5: Sample sweeps. User triggers each sweep manually; Finish button closes popup."""
        try:
            for w in self.page_frame.winfo_children():
                w.destroy()
        except Exception:
            pass

        # total sample sweeps
        try:
            total = int(self._pending_data_config.get('sweeps', 1)) if hasattr(self, '_pending_data_config') and self._pending_data_config else 1
        except Exception:
            total = 1

        self._sample_total = total
        self._sample_recorded = getattr(self, '_sample_recorded', 0)

        # Instruction text: first vs subsequent
        if self._sample_recorded == 0:
            instruct_text = "Align with structure to sweep and click the button below"
        else:
            instruct_text = "Move and align with the next structure to sweep and click the button below"

        instruct = CTkLabel(self.page_frame, text=instruct_text, font=("Arial", 12), text_color="white", justify="center")
        instruct.grid(row=0, column=0, columnspan=3, pady=(8, 12))

        # dynamic record button
        btn_text = f"Record sweep {self._sample_recorded + 1}" if self._sample_recorded < self._sample_total else "Record sweep"
        self._record_sample_button = CTkButton(self.page_frame, text=btn_text, width=280, command=self._record_sample_sweep)
        self._record_sample_button.grid(row=1, column=0, columnspan=3, pady=(6, 6))

        # status label
        self._record_sample_status_label = CTkLabel(self.page_frame, text=f"Recorded {self._sample_recorded}/{self._sample_total}", font=("Arial", 12), text_color="grey")
        self._record_sample_status_label.grid(row=2, column=0, columnspan=3, pady=(6, 6))

        # Footer: Back + Finish (Finish disabled until done)
        for child in list(self.popup.winfo_children()):
            if isinstance(child, CTkFrame) and child is not self.page_frame:
                try:
                    child.destroy()
                except Exception:
                    pass

        footer = CTkFrame(self.popup, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(8, 12))
        back_btn = CTkButton(footer, text="Back", width=120, command=self._polarizer_page5_back)
        back_btn.pack(side="left")
        self._finish_btn = CTkButton(footer, text="Finish", width=120, state="disabled", command=self._polarizer_page5_finish)
        self._finish_btn.pack(side="right")

    def _polarizer_page5_finish(self):
        """Finish the routine and close the popup."""
        try:
            # Run preview generation in background using the active SweepRoutine folder (best-effort)
            try:
                fs = self._get_filesystem()
                if fs and getattr(fs, "current_sweep_routine", None):
                    sweep_root = os.path.join(fs.backup_directory, fs.current_sweep_routine)
                    def _run_preview_and_notify(root, app_master=self.master):
                        try:
                            out = preview.generate_preview_from_sweep(root)
                            # notify on main thread if possible
                            try:
                                app_master.notification("Preview ready", f"Saved to: {out}", "#1a8300")
                            except Exception:
                                pass
                        except Exception as e:
                            try:
                                app_master.notification("Preview failed", str(e), "#e17e00")
                            except Exception:
                                pass
                    threading.Thread(target=_run_preview_and_notify, args=(sweep_root,), daemon=True).start()
            except Exception:
                pass

            # teardown sweep routine so subsequent runs create a new SweepRoutineN folder
            try:
                self._teardown_sweep_routine()
            except Exception:
                pass

            if self.popup:
                self.popup.destroy()
        except Exception:
            pass
        self.popup = None

    def _record_sample_sweep(self):
        """Record a single sample sweep (user-triggered)."""
        total = getattr(self, '_sample_total', 1)
        recorded = getattr(self, '_sample_recorded', 0)

        # disable button and update status
        try:
            self._record_sample_button.configure(state="disabled", text=f"Recording {recorded + 1}/{total}...")
            self._record_sample_status_label.configure(text=f"Recording {recorded}/{total}")
        except Exception:
            pass

        def _worker():
            nonlocal recorded, total

            # find rotation mount
            rotation_mount = None
            try:
                microscope = getattr(self, 'microscope', None) or getattr(self.master, 'selected_microscope', None)
                if microscope:
                    for dev in microscope.devices:
                        if isinstance(dev, MyRotationMount):
                            rotation_mount = dev
                            break
            except Exception:
                rotation_mount = None

            if rotation_mount is None:
                try:
                    self.master.notification("No rotation mount found", None, "#8e0101")
                except Exception:
                    pass
                def _reenable():
                    try:
                        self._record_sample_button.configure(state="normal", text=f"Record sweep {recorded + 1}")
                    except Exception:
                        pass
                self.after(0, _reenable)
                return

            # Ensure spectrometer running
            try:
                spec_frame = getattr(self.master, 'spectrometer_frame', None)
            except Exception:
                spec_frame = None
            try:
                if spec_frame and spec_frame.connected_spectrometers and not spec_frame.connected_spectrometers[0].is_running:
                    spec_frame.start_spectrometer(spec_frame.connected_spectrometers[0])
            except Exception:
                pass

            # Set folder name for this sweep
            idx = recorded + 1
            sweep_folder = f"Sweep_{idx}"
            try:
                rotation_mount.sweep_folder_name = sweep_folder
            except Exception:
                pass

            # start sweep
            try:
                rotation_mount.start_sweep(int(self._pending_sweep_params[0]), start_angle=int(self._pending_sweep_params[1]), stop_angle=int(self._pending_sweep_params[2]))
            except Exception as e:
                debugp("Routines", f"Failed to start sample sweep: {e}")
                try:
                    self.master.notification("Failed to start sweep", None, "#8e0101")
                except Exception:
                    pass
                def _reenable_err():
                    try:
                        self._record_sample_button.configure(state="normal", text=f"Record sweep {recorded + 1}")
                    except Exception:
                        pass
                self.after(0, _reenable_err)
                return

            # wait for completion
            wait_spec = getattr(rotation_mount, 'spectrometer', None)
            if wait_spec is None and spec_frame and spec_frame.connected_spectrometers:
                wait_spec = spec_frame.connected_spectrometers[0]

            timeout = 60 * 10
            start_time = time.time()
            while True:
                try:
                    if wait_spec is None or getattr(wait_spec, 'acquire_save_data', 0) == 0:
                        break
                except Exception:
                    break
                if time.time() - start_time > timeout:
                    try:
                        self.master.notification(f"Sweep timed out", None, "#e17e00")
                    except Exception:
                        pass
                    break
                time.sleep(0.5)

            # determine folder
            folder = None
            try:
                if spec_frame and spec_frame.connected_spectrometers:
                    spec = spec_frame.connected_spectrometers[0]
                    file_path = spec_frame.file_system.get_spectrometer_directory(spec.integration_time, spec.name, rotation_mount.sweep_folder_name)
                    folder = os.path.dirname(file_path)
            except Exception:
                folder = None

            # update UI
            def _on_done():
                try:
                    self._sample_recorded = recorded + 1
                    rec = self._sample_recorded
                    self._record_sample_status_label.configure(text=f"Recorded {rec}/{total}")
                    # notify per sweep
                    try:
                        if folder:
                            self.master.notification(f"Sweep {idx} recorded", f"Saved to: {folder}", "#1a8300")
                        else:
                            self.master.notification(f"Sweep {idx} recorded", None, "#1a8300")
                    except Exception:
                        pass
                    if rec >= total:
                        try:
                            self._finish_btn.configure(state="normal")
                        except Exception:
                            pass
                        try:
                            self._record_sample_button.configure(state="disabled", text="All recorded")
                        except Exception:
                            pass
                    else:
                        # update instruction text and button
                        try:
                            # replace instruction text
                            for child in self.page_frame.winfo_children():
                                if isinstance(child, CTkLabel) and child is not None:
                                    # first label is instruction
                                    child.configure(text="Move and align with the next structure to sweep and click the button below")
                                    break
                        except Exception:
                            pass
                        try:
                            self._record_sample_button.configure(state="normal", text=f"Record sweep {rec + 1}")
                        except Exception:
                            pass
                except Exception:
                    pass

            self.after(0, _on_done)

        threading.Thread(target=_worker, daemon=True).start()

    def _record_light_refs(self):
        """Record light references in background thread and enable Next when done."""
        # Determine target count and current progress
        try:
            total = int(self._pending_data_config.get('light_refs', 1)) if hasattr(self, '_pending_data_config') and self._pending_data_config else int(self._light_refs_entry.get() or self._light_refs_entry.placeholder_text)
        except Exception:
            total = 1

        # Disable immediate re-click and start background worker for a single sweep
        try:
            self._record_light_button.configure(state="disabled", text=f"Recording {self._light_recorded + 1}/{total}...")
            self._record_light_status_label.configure(text=f"Recording {self._light_recorded}/{total}")
        except Exception:
            pass

        def _worker():
            nonlocal total
            idx = self._light_recorded + 1
            # find rotation mount
            rotation_mount = None
            try:
                microscope = getattr(self, 'microscope', None) or getattr(self.master, 'selected_microscope', None)
                if microscope:
                    for dev in microscope.devices:
                        if isinstance(dev, MyRotationMount):
                            rotation_mount = dev
                            break
            except Exception:
                rotation_mount = None

            if rotation_mount is None:
                try:
                    self.master.notification("No rotation mount found", None, "#8e0101")
                except Exception:
                    pass
                # re-enable button
                def _reenable():
                    try:
                        self._record_light_button.configure(state="normal", text=f"Record light reference {self._light_recorded + 1}")
                    except Exception:
                        pass
                self.after(0, _reenable)
                return

            # Ensure spectrometer is running
            try:
                spec_frame = getattr(self.master, 'spectrometer_frame', None)
            except Exception:
                spec_frame = None
            try:
                if spec_frame and spec_frame.connected_spectrometers and not spec_frame.connected_spectrometers[0].is_running:
                    spec_frame.start_spectrometer(spec_frame.connected_spectrometers[0])
            except Exception:
                pass

            # Set folder name for this light reference and start sweep
            sweep_folder = f"LightRef_{idx}"
            try:
                rotation_mount.sweep_folder_name = sweep_folder
            except Exception:
                pass

            try:
                rotation_mount.start_sweep(int(self._pending_sweep_params[0]), start_angle=int(self._pending_sweep_params[1]), stop_angle=int(self._pending_sweep_params[2]))
            except Exception as e:
                debugp("Routines", f"Failed to start light reference sweep: {e}")
                try:
                    self.master.notification("Failed to start light reference sweep", None, "#8e0101")
                except Exception:
                    pass
                # re-enable button
                def _reenable_err():
                    try:
                        self._record_light_button.configure(state="normal", text=f"Record light reference {self._light_recorded + 1}")
                    except Exception:
                        pass
                self.after(0, _reenable_err)
                return

            # Wait for sweep completion by polling spectrometer acquire flag
            wait_spec = getattr(rotation_mount, 'spectrometer', None)
            if wait_spec is None and spec_frame and spec_frame.connected_spectrometers:
                wait_spec = spec_frame.connected_spectrometers[0]

            timeout = 60 * 10
            start_time = time.time()
            while True:
                try:
                    if wait_spec is None or getattr(wait_spec, 'acquire_save_data', 0) == 0:
                        break
                except Exception:
                    break
                if time.time() - start_time > timeout:
                    try:
                        self.master.notification(f"Light reference sweep timed out", None, "#e17e00")
                    except Exception:
                        pass
                    break
                time.sleep(0.5)

            # After completion, compute the folder where files were written
            folder = None
            try:
                if spec_frame and spec_frame.connected_spectrometers:
                    spec = spec_frame.connected_spectrometers[0]
                    file_path = spec_frame.file_system.get_spectrometer_directory(spec.integration_time, spec.name, rotation_mount.sweep_folder_name)
                    folder = os.path.dirname(file_path)
            except Exception:
                folder = None

            # update recorded counter and UI from main thread
            def _on_done():
                try:
                    self._light_recorded += 1
                    recorded = self._light_recorded
                    self._record_light_status_label.configure(text=f"Recorded {recorded}/{total}")
                    # show per-light-reference notification with folder
                    try:
                        if folder:
                            self.master.notification(f"Light reference {idx} recorded", f"Saved to: {folder}", "#1a8300")
                        else:
                            self.master.notification(f"Light reference {idx} recorded", None, "#1a8300")
                    except Exception:
                        pass
                    if recorded >= total:
                        try:
                            self._page4_next_btn.configure(state="normal")
                        except Exception:
                            pass
                        try:
                            self._record_light_button.configure(state="disabled", text="All recorded")
                        except Exception:
                            pass
                    else:
                        # update button text for next reference
                        try:
                            self._record_light_button.configure(state="normal", text=f"Record light reference {recorded + 1}")
                        except Exception:
                            pass
                except Exception:
                    pass

            self.after(0, _on_done)

        threading.Thread(target=_worker, daemon=True).start()

    def _polarizer_page4_next(self):
        """Proceed to the sample sweep page where the user records each sweep manually.

        The sample sweep page provides a dynamic button to record each sweep one-byone
        (user aligns between sweeps). When all sweeps are recorded the Finish button is enabled.
        """
        # Validate pending configuration
        if not hasattr(self, '_pending_sweep_params') or not self._pending_sweep_params:
            try:
                self.notification("Sweep parameters missing", color="#8e0101")
            except Exception:
                pass
            return

        if not hasattr(self, '_pending_data_config') or not self._pending_data_config:
            try:
                self.notification("Data configuration missing", color="#8e0101")
            except Exception:
                pass
            return

        # Build the sample sweep page (page 5)
        self._build_page5()

    def _polarizer_popup_back(self):
        # Rebuild the initial page by destroying and reopening popup
        if self.popup:
            try:
                self.popup.destroy()
            except Exception:
                pass
        self.popup = None
        self.open_polarizer_sweep_popup()

    def _polarizer_start(self, step, start, stop):
        # Placeholder action: notify and close. Integration with rotation mount will be added later.
        try:
            self.notification("Sweep started", f"{start}° → {stop}° step {step}°", "#1a8300")
        except Exception:
            pass
        if self.popup:
            try:
                self.popup.destroy()
            except Exception:
                pass
        # cleanup sweep routine state so next run creates a new folder
        try:
            self._teardown_sweep_routine()
        except Exception:
            pass
        self.popup = None

    def close_popup(self):
        if self.popup:
            try:
                self.popup.destroy()
            except Exception:
                pass
            self.popup = None
        # popup closed/cancelled -> clear active sweep routine so next run makes a new folder
        try:
            self._teardown_sweep_routine()
        except Exception:
            pass

    def _ensure_sweep_routine_folder(self):
        """Best-effort locate a FileSystem instance and call start_new_sweep_routine once."""
        # avoid repeated creation if popup reopened
        if getattr(self, "_sweep_routine_started", False):
            return
        fs = None

        # check direct microscope object passed to this frame
        try:
            if getattr(self, "microscope", None) and hasattr(self.microscope, "file_system"):
                fs = self.microscope.file_system
        except Exception:
            fs = None

        # walk up the master chain to find file_system (common app placements)
        node = self.master
        for _ in range(6):  # search a few levels
            if not node:
                break
            if hasattr(node, "file_system"):
                fs = getattr(node, "file_system")
                break
            # also check spectrometer_frame which often holds file_system
            if hasattr(node, "spectrometer_frame") and getattr(node, "spectrometer_frame", None) and hasattr(node.spectrometer_frame, "file_system"):
                fs = node.spectrometer_frame.file_system
                break
            node = getattr(node, "master", None)

        # final attempt: spectrometer_frame directly on known locations
        try:
            if not fs and hasattr(self.master, "spectrometer_frame") and getattr(self.master, "spectrometer_frame"):
                fs = self.master.spectrometer_frame.file_system
        except Exception:
            pass

        if fs and hasattr(fs, "start_new_sweep_routine"):
            try:
                fs.start_new_sweep_routine()
                self._sweep_routine_started = True
            except Exception:
                pass

    def _get_filesystem(self):
        """Best-effort: locate and return the FileSystem instance used by the app (or None)."""
        fs = None
        try:
            if getattr(self, "microscope", None) and hasattr(self.microscope, "file_system"):
                return self.microscope.file_system
        except Exception:
            pass

        node = self.master
        for _ in range(6):
            if not node:
                break
            if hasattr(node, "file_system"):
                return getattr(node, "file_system")
            if hasattr(node, "spectrometer_frame") and getattr(node, "spectrometer_frame", None) and hasattr(node.spectrometer_frame, "file_system"):
                return node.spectrometer_frame.file_system
            node = getattr(node, "master", None)

        try:
            if hasattr(self.master, "spectrometer_frame") and getattr(self.master, "spectrometer_frame", None):
                return self.master.spectrometer_frame.file_system
        except Exception:
            pass

        return None

    def _teardown_sweep_routine(self):
        """Clear the active sweep routine marker (both on this frame and on FileSystem) so the next run creates a new folder."""
        # reset frame flag first
        try:
            self._sweep_routine_started = False
        except Exception:
            pass

        fs = None
        try:
            fs = self._get_filesystem()
        except Exception:
            fs = None

        if fs:
            try:
                # perform cleanup: remove the SweepRoutineN folder if it contains no files
                if hasattr(fs, "cleanup_current_sweep_routine"):
                    try:
                        fs.cleanup_current_sweep_routine()
                    except Exception as e:
                        debugp("Routines", f"cleanup_current_sweep_routine failed: {e}")
                else:
                    # fallback: unset the marker
                    fs.current_sweep_routine = None
                    fs.current_sweep_has_data = False
                    debugp("Routines", "Cleared FileSystem.current_sweep_routine (fallback)")
            except Exception as e:
                debugp("Routines", f"Failed to clear sweep routine on filesystem: {e}")
