from tkinter import messagebox
from CTkToolTip import *
from dev.debugHelp import debugp
from dev.devices.rotation_mounts.rotation_mount import MyRotationMount
from .notification import *
from ..images.images import *
from ..devices.camera.camera import *
from ..devices.spectrometer import *
from ..devices.shutter.shutter import *
from ..devices.filter import *
from ..devices.stage import *
import threading


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
        self.device_entries = []
        for i, device in enumerate(microscope.devices):

            widgets = []
            master_frame = None
            frame = CTkFrame(self)
            frame.grid(row=i, column=0, sticky="nsew")
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

            elif isinstance(device, MyFilter):
                pass

            elif isinstance(device, MyStage):
                pass

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
        self.required_height_for_scrollbar = (i+1) * frame.winfo_height()
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
            
            #If spectrometer, connect the right one if not connect the device normally
            if isinstance(entry.device, MySpectrometer):  
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
            entry.activate() if entry.is_device_connected() else entry.desactivate()


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

        if isinstance(entry.device, MySpectrometer):
            if entry.switch.get():
                if not element.connect(entry.device):
                    debugp("connecting", "Spectrometer Not Connecting Manually" + str(element))
                    self.notification(f"Unable to connect to {entry.device.name} {entry.device.serial}", color="#8e0101")
                else:
                    debugp("connecting", "Spectrometer Connecting Manually" + str(element))
            else:
                debugp("connecting", "Spectrometer Disconnecting Manually" + str(element))
                element.disconnect(entry.device)
        else:
            if entry.switch.get():
                if not element.connect():
                    print("Tried to connect to device, unsuccessful (toggle_device)")
                    self.notification(f"Unable to connect to {entry.device.name} {entry.device.serial}", color="#8e0101")
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
