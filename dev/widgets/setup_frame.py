from tkinter import messagebox, simpledialog
from customtkinter import Variable as CTkVariable, CTkOptionMenu
from CTkToolTip import *
from dev.debugHelp import debugp
from dev.devices.rotation_mounts.rotation_mount import MyRotationMount
import json
import os
import sys
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
from ..autofocus import AutoFocus
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
        self.microscope = microscope
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
                # Autofocus button (enabled when both camera + stage are connected)
                af_btn = CTkButton(frame, text="Autofocus", width=80, state="disabled",
                                   command=lambda: self._run_autofocus())
                CTkToolTip(af_btn, delay=0.2, message="Auto-focus via Z sweep")
                af_settings = CTkButton(frame, text="", width=30, height=30,
                                        image=img_cogwheel, fg_color="transparent",
                                        state="disabled",
                                        command=lambda: self._open_autofocus_settings())
                CTkToolTip(af_settings, delay=0.2, message="Autofocus settings")
                af_btn.pack(side="left", padx=(10, 2))
                af_settings.pack(side="left", padx=(0, 5))
                widgets.append((af_btn, "Autofocus"))
                widgets.append((af_settings, "Autofocus"))

            elif isinstance(device, MySpectrometer):
                master_frame = self.master.master.master.spectrometer_frame
                if getattr(device, "supports_image_view", False):
                    settings = CTkButton(
                        frame,
                        text="",
                        width=30,
                        height=30,
                        image=img_cogwheel,
                        fg_color="transparent",
                        state="disabled",
                        command=lambda d=device: self.open_spectrograph_settings(d),
                    )
                    CTkToolTip(settings, delay=0.2, message="Kymera settings")
                    settings.pack(side="left", padx=(10, 0))
                    widgets.append((settings, ""))
                else:
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

                # --- Polarization preset buttons (only for Half Wave Plate) ---
                if device.name == "Half Wave Plate":
                    pol_x_btn = CTkButton(frame, text="X", width=30, state="disabled",
                                          command=lambda: self.move_polarization_preset("horizontal"))
                    CTkToolTip(pol_x_btn, delay=0.2, message="Move to Horizontal preset")
                    pol_y_btn = CTkButton(frame, text="Y", width=30, state="disabled",
                                          command=lambda: self.move_polarization_preset("vertical"))
                    CTkToolTip(pol_y_btn, delay=0.2, message="Move to Vertical preset")
                    pol_settings_btn = CTkButton(frame, text="", width=30, height=30,
                                                 image=img_cogwheel, fg_color="transparent",
                                                 state="disabled",
                                                 command=lambda: self.open_polarization_preset_settings())
                    CTkToolTip(pol_settings_btn, delay=0.2, message="Polarization Preset Settings")

                    pol_x_btn.pack(side="left", padx=(10, 2))
                    pol_y_btn.pack(side="left", padx=(2, 2))
                    pol_settings_btn.pack(side="left", padx=(2, 5))

                    widgets.append((pol_x_btn, ""))
                    widgets.append((pol_y_btn, ""))
                    widgets.append((pol_settings_btn, ""))

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


    def open_spectrograph_settings(self, device):
        if getattr(self, "popup", None):
            try:
                self.popup.destroy()
            except Exception:
                pass

        was_running = bool(getattr(device, "is_running", False))
        if was_running and hasattr(device, "stop"):
            try:
                device.stop()
            except Exception:
                pass
        try:
            device.refresh_sdk_capabilities()
        except Exception:
            pass
        finally:
            if was_running and hasattr(device, "start"):
                try:
                    device.start()
                except Exception:
                    pass

        self.popup = CTkToplevel(self)
        self.popup.title(f"{device.name} settings")
        self.popup.geometry("940x660")
        self.popup.resizable(False, False)
        self.popup.grid_columnconfigure(0, weight=1)
        self.popup.grid_rowconfigure(2, weight=1)

        def _close():
            if self.popup:
                self.popup.destroy()
                self.popup = None

        self.popup.protocol("WM_DELETE_WINDOW", _close)

        header = CTkFrame(self.popup, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 12))
        header.grid_columnconfigure(0, weight=1)
        CTkLabel(header, text=f"{device.name} acquisition setup", font=("Arial", 22)).grid(row=0, column=0, sticky="w")
        CTkLabel(header, text=f"Detector: {getattr(device, 'detector_name', 'Newton CCD')}", text_color="gray60").grid(row=1, column=0, sticky="w", pady=(4, 0))

        state = {
            "page": getattr(device, "selected_settings_page", getattr(device, "selected_read_mode", "FVB")),
            "acquisition_mode": getattr(device, "selected_acquisition_mode", "Single"),
            "exposure": f"{device.get_exposure_seconds():.5f}",
            "accumulations": str(getattr(device, "number_accumulations", 1)),
            "kinetic_series": str(getattr(device, "kinetic_series_length", 60)),
            "vertical_shift_key": getattr(device, "selected_vertical_shift_speed_key", None),
            "vertical_clock_key": getattr(device, "selected_vertical_clock_amplitude_key", None),
            "output_amplifier": getattr(device, "selected_output_amplifier", "Conventional"),
            "readout_rate_key": getattr(device, "selected_readout_rate_key", None),
            "preamp_key": getattr(device, "selected_preamp_gain_key", None),
            "target_temperature": str(getattr(device, "target_temperature_c", -70)),
            "cooler_enabled": bool(getattr(device, "cooler_enabled", False)),
            "cooler_startup_enabled": bool(getattr(device, "cooler_startup_enabled", False)),
            "current_temperature": device.get_temperature(),
            "excitation_wavelength": f"{getattr(device, 'excitation_wavelength_nm', 785.0):.3f}",
            "cycle_time": f"{device.get_cycle_time_seconds():.5f}",
        }
        widgets = {}

        def _option_label(options, selected_key, fallback_text=""):
            for option in options:
                if option["key"] == selected_key:
                    return option["label"]
            return options[0]["label"] if options else fallback_text

        def _option_key(options, selected_label, fallback_key=None):
            for option in options:
                if option["label"] == selected_label:
                    return option["key"]
            if fallback_key in {option["key"] for option in options}:
                return fallback_key
            return options[0]["key"] if options else None

        def _filtered_readout_options():
            amplifier_slug = "conv" if state["output_amplifier"] == "Conventional" else "em"
            options = [
                option
                for option in device.readout_rate_options
                if option["key"].split(":")[1] == amplifier_slug
            ]
            return options or list(device.readout_rate_options)

        def _ensure_readout_key():
            options = _filtered_readout_options()
            keys = [option["key"] for option in options]
            if state["readout_rate_key"] not in keys:
                state["readout_rate_key"] = keys[0] if keys else None

        def _snapshot_visible_fields():
            if "exposure_entry" in widgets:
                state["exposure"] = widgets["exposure_entry"].get().strip() or state["exposure"]
            if "accumulations_entry" in widgets:
                state["accumulations"] = widgets["accumulations_entry"].get().strip() or state["accumulations"]
            if "kinetic_series_entry" in widgets:
                state["kinetic_series"] = widgets["kinetic_series_entry"].get().strip() or state["kinetic_series"]
            if "target_temperature_entry" in widgets:
                state["target_temperature"] = widgets["target_temperature_entry"].get().strip() or state["target_temperature"]
            if "cooler_switch" in widgets:
                state["cooler_enabled"] = bool(widgets["cooler_switch"].get())
            if "cooler_startup_switch" in widgets:
                state["cooler_startup_enabled"] = bool(widgets["cooler_startup_switch"].get())
            if "excitation_wavelength_entry" in widgets:
                state["excitation_wavelength"] = widgets["excitation_wavelength_entry"].get().strip() or state["excitation_wavelength"]
            if "cycle_time_entry" in widgets:
                state["cycle_time"] = widgets["cycle_time_entry"].get().strip() or state["cycle_time"]

        def _timing_preview():
            try:
                exposure_seconds = max(float(state["exposure"]), 0.00001)
            except Exception:
                exposure_seconds = device.get_exposure_seconds()
            accumulate_seconds = exposure_seconds + getattr(device, "cycle_time_offset_s", 0.00305) * 0.82
            kinetic_seconds = exposure_seconds + getattr(device, "cycle_time_offset_s", 0.00305)
            return exposure_seconds, accumulate_seconds, kinetic_seconds

        def _track_summary():
            tracks = getattr(device, "multi_track_tracks", [])
            if not tracks:
                return "No tracks configured"
            preview = ", ".join(f"{start}-{end}" for start, end in tracks[:3])
            if len(tracks) > 3:
                preview += f" ... (+{len(tracks) - 3})"
            return f"{len(tracks)} track(s) | Rows {preview} | H range {device.multi_track_horizontal_start}-{device.multi_track_horizontal_end}"

        def _switch_page(page_name):
            _snapshot_visible_fields()
            state["page"] = page_name
            _render_settings_page()

        def _switch_acquisition_mode(choice):
            _snapshot_visible_fields()
            state["acquisition_mode"] = choice
            _render_settings_page()

        def _switch_output_amplifier(choice):
            _snapshot_visible_fields()
            state["output_amplifier"] = choice
            _ensure_readout_key()
            _render_settings_page()

        def _refresh_temperature():
            try:
                device.refresh_sdk_capabilities()
            except Exception:
                pass
            state["current_temperature"] = device.get_temperature()
            state["target_temperature"] = str(getattr(device, "target_temperature_c", state["target_temperature"]))
            state["cooler_enabled"] = bool(getattr(device, "cooler_enabled", state["cooler_enabled"]))
            state["cooler_startup_enabled"] = bool(getattr(device, "cooler_startup_enabled", state["cooler_startup_enabled"]))
            _render_settings_page()

        def _open_multi_track_setup():
            _snapshot_visible_fields()
            popup = CTkToplevel(self.popup)
            popup.title("Setup Multi-track")
            popup.geometry("500x560")
            popup.resizable(False, False)
            popup.grid_columnconfigure(0, weight=1)
            popup.grid_rowconfigure(1, weight=1)

            CTkLabel(popup, text="Multi-track setup", font=("Arial", 20)).grid(row=0, column=0, padx=18, pady=(16, 10), sticky="w")

            controls = CTkFrame(popup)
            controls.grid(row=1, column=0, padx=18, pady=(0, 10), sticky="nsew")
            controls.grid_columnconfigure(0, weight=1)
            controls.grid_columnconfigure(1, weight=1)

            top_controls = CTkFrame(controls, fg_color="transparent")
            top_controls.grid(row=0, column=0, columnspan=2, padx=10, pady=(10, 10), sticky="ew")
            for column_index in range(4):
                top_controls.grid_columnconfigure(column_index, weight=1)

            CTkLabel(top_controls, text="Tracks").grid(row=0, column=0, sticky="w")
            tracks_entry = CTkEntry(top_controls, width=80)
            tracks_entry.grid(row=1, column=0, padx=(0, 8), sticky="w")
            tracks_entry.insert(0, str(getattr(device, "multi_track_count", len(device.get_multi_track_tracks()))))

            CTkLabel(top_controls, text="Height").grid(row=0, column=1, sticky="w")
            height_entry = CTkEntry(top_controls, width=80)
            height_entry.grid(row=1, column=1, padx=(0, 8), sticky="w")
            height_entry.insert(0, str(getattr(device, "multi_track_height", 1)))

            CTkLabel(top_controls, text="Offset").grid(row=0, column=2, sticky="w")
            offset_entry = CTkEntry(top_controls, width=80)
            offset_entry.grid(row=1, column=2, padx=(0, 8), sticky="w")
            offset_entry.insert(0, str(getattr(device, "multi_track_offset", 0)))

            track_entries = []
            track_table = CTkScrollableFrame(controls, width=300, height=260)
            track_table.grid(row=1, column=0, padx=(10, 6), pady=(0, 10), sticky="nsew")
            track_table.grid_columnconfigure(1, weight=1)
            track_table.grid_columnconfigure(2, weight=1)

            side_buttons = CTkFrame(controls, fg_color="transparent")
            side_buttons.grid(row=1, column=1, padx=(6, 10), pady=(0, 10), sticky="ns")
            side_buttons.grid_columnconfigure(0, weight=1)

            hbin_entry = None
            hstart_entry = None
            hend_entry = None
            flip_switch = None

            def _render_track_rows(track_rows):
                nonlocal track_entries
                for child in track_table.winfo_children():
                    child.destroy()

                CTkLabel(track_table, text="Track", text_color="gray60").grid(row=0, column=0, padx=(4, 8), pady=(2, 6), sticky="w")
                CTkLabel(track_table, text="Start row", text_color="gray60").grid(row=0, column=1, padx=(0, 8), pady=(2, 6), sticky="w")
                CTkLabel(track_table, text="End row", text_color="gray60").grid(row=0, column=2, padx=(0, 4), pady=(2, 6), sticky="w")

                track_entries = []
                for index, (start_row, end_row) in enumerate(track_rows, start=1):
                    CTkLabel(track_table, text=str(index)).grid(row=index, column=0, padx=(4, 8), pady=4, sticky="w")
                    start_entry = CTkEntry(track_table, width=88)
                    start_entry.grid(row=index, column=1, padx=(0, 8), pady=4, sticky="ew")
                    start_entry.insert(0, str(start_row))
                    end_entry = CTkEntry(track_table, width=88)
                    end_entry.grid(row=index, column=2, padx=(0, 4), pady=4, sticky="ew")
                    end_entry.insert(0, str(end_row))
                    track_entries.append((start_entry, end_entry))

            def _read_tracks_from_entries():
                rows = []
                for start_entry, end_entry in track_entries:
                    start_value = start_entry.get().strip()
                    end_value = end_entry.get().strip()
                    if not start_value and not end_value:
                        continue
                    rows.append((int(float(start_value)), int(float(end_value))))
                return rows

            def _generate_tracks():
                try:
                    generated_rows = device.generate_multi_track_tracks(
                        int(float(tracks_entry.get() or device.multi_track_count)),
                        int(float(height_entry.get() or device.multi_track_height)),
                        int(float(offset_entry.get() or device.multi_track_offset)),
                    )
                except Exception:
                    self.notification("Multi-track setup must be numeric", "#8e0101")
                    return
                _render_track_rows(generated_rows)

            def _add_track():
                try:
                    rows = _read_tracks_from_entries()
                except Exception:
                    rows = list(device.get_multi_track_tracks())

                if rows:
                    next_start = rows[-1][1] + 1
                else:
                    next_start = 1
                rows.append((next_start, next_start + max(int(float(height_entry.get() or 1)) - 1, 0)))
                _render_track_rows(rows)

            def _remove_track():
                try:
                    rows = _read_tracks_from_entries()
                except Exception:
                    rows = list(device.get_multi_track_tracks())
                if rows:
                    rows.pop()
                _render_track_rows(rows)

            CTkButton(top_controls, text="Generate", width=96, command=_generate_tracks).grid(row=1, column=3, sticky="e")
            CTkButton(side_buttons, text="Add Track", width=110, command=_add_track).grid(row=0, column=0, pady=(8, 6), sticky="ew")
            CTkButton(side_buttons, text="Delete Last", width=110, command=_remove_track).grid(row=1, column=0, pady=(0, 6), sticky="ew")

            bottom_controls = CTkFrame(controls, fg_color="transparent")
            bottom_controls.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 8), sticky="ew")
            for column_index in range(3):
                bottom_controls.grid_columnconfigure(column_index, weight=1)

            CTkLabel(bottom_controls, text="Horizontal binning").grid(row=0, column=0, sticky="w")
            hbin_entry = CTkEntry(bottom_controls, width=90)
            hbin_entry.grid(row=1, column=0, padx=(0, 8), sticky="w")
            hbin_entry.insert(0, str(getattr(device, "multi_track_horizontal_binning", 1)))

            CTkLabel(bottom_controls, text="Horizontal start").grid(row=0, column=1, sticky="w")
            hstart_entry = CTkEntry(bottom_controls, width=90)
            hstart_entry.grid(row=1, column=1, padx=(0, 8), sticky="w")
            hstart_entry.insert(0, str(getattr(device, "multi_track_horizontal_start", 1)))

            CTkLabel(bottom_controls, text="Horizontal end").grid(row=0, column=2, sticky="w")
            hend_entry = CTkEntry(bottom_controls, width=90)
            hend_entry.grid(row=1, column=2, sticky="w")
            hend_entry.insert(0, str(getattr(device, "multi_track_horizontal_end", device.detector_width_pixels)))

            flip_switch = CTkSwitch(controls, text="Flip data horizontally")
            flip_switch.grid(row=3, column=0, columnspan=2, padx=10, pady=(0, 12), sticky="w")
            if getattr(device, "multi_track_flip_horizontal", False):
                flip_switch.select()

            button_row = CTkFrame(popup, fg_color="transparent")
            button_row.grid(row=2, column=0, padx=18, pady=(0, 16), sticky="ew")
            button_row.grid_columnconfigure(0, weight=1)

            def _save_multi_track_setup():
                try:
                    track_rows = _read_tracks_from_entries()
                    if not track_rows:
                        track_rows = device.generate_multi_track_tracks(
                            int(float(tracks_entry.get() or 1)),
                            int(float(height_entry.get() or 1)),
                            int(float(offset_entry.get() or 0)),
                        )
                    device.set_multi_track_tracks(track_rows)
                    device.multi_track_count = max(int(float(tracks_entry.get() or len(track_rows))), 1)
                    device.multi_track_height = max(int(float(height_entry.get() or 1)), 1)
                    device.multi_track_offset = max(int(float(offset_entry.get() or 0)), 0)
                    device.set_multi_track_horizontal_binning(hbin_entry.get())
                    device.set_multi_track_horizontal_range(hstart_entry.get(), hend_entry.get())
                    device.set_multi_track_flip_horizontal(bool(flip_switch.get()))
                except Exception:
                    self.notification("Multi-track setup must be numeric", "#8e0101")
                    return

                popup.destroy()
                _render_settings_page()

            CTkButton(button_row, text="Cancel", fg_color="transparent", border_width=2, border_color="#1F6AA5", command=popup.destroy).grid(row=0, column=1, padx=(0, 8), sticky="e")
            CTkButton(button_row, text="Save", command=_save_multi_track_setup).grid(row=0, column=2, sticky="e")

            _render_track_rows(device.get_multi_track_tracks())
            popup.transient(self.popup)

        page_row = CTkFrame(self.popup, fg_color="transparent")
        page_row.grid(row=1, column=0, sticky="ew", padx=20)
        for column_index, page_name in enumerate(device.get_settings_pages()):
            page_row.grid_columnconfigure(column_index, weight=1)
            CTkButton(
                page_row,
                text=page_name,
                height=30,
                fg_color=("#1F6AA5" if state["page"] == page_name else "transparent"),
                border_width=(0 if state["page"] == page_name else 1),
                border_color="#1F6AA5",
                command=lambda selected_page=page_name: _switch_page(selected_page),
            ).grid(row=0, column=column_index, padx=(0 if column_index == 0 else 6, 0), sticky="ew")

        content = CTkFrame(self.popup)
        content.grid(row=2, column=0, sticky="nsew", padx=20, pady=(14, 12))
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        def _render_settings_page():
            _snapshot_visible_fields()
            _ensure_readout_key()
            widgets.clear()

            for child in page_row.winfo_children():
                child.destroy()
            for column_index, page_name in enumerate(device.get_settings_pages()):
                page_row.grid_columnconfigure(column_index, weight=1)
                CTkButton(
                    page_row,
                    text=page_name,
                    height=30,
                    fg_color=("#1F6AA5" if state["page"] == page_name else "transparent"),
                    border_width=(0 if state["page"] == page_name else 1),
                    border_color="#1F6AA5",
                    command=lambda selected_page=page_name: _switch_page(selected_page),
                ).grid(row=0, column=column_index, padx=(0 if column_index == 0 else 6, 0), sticky="ew")

            for child in content.winfo_children():
                child.destroy()

            if state["page"] == "Temperature":
                temperature_frame = CTkFrame(content)
                temperature_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")
                temperature_frame.grid_columnconfigure(0, weight=1)

                current_temperature = state["current_temperature"]
                current_temperature_text = f"{current_temperature:.2f} °C" if isinstance(current_temperature, (int, float)) else "Unavailable"
                minimum_temperature, maximum_temperature = device.get_temperature_range()

                CTkLabel(temperature_frame, text="Detector temperature", font=("Arial", 18)).grid(row=0, column=0, padx=18, pady=(18, 6), sticky="w")
                CTkLabel(temperature_frame, text=f"Current temperature: {current_temperature_text}", text_color="gray60").grid(row=1, column=0, padx=18, sticky="w")
                CTkLabel(temperature_frame, text=f"Allowed range: {minimum_temperature} °C to {maximum_temperature} °C", text_color="gray60").grid(row=2, column=0, padx=18, pady=(4, 12), sticky="w")

                settings_grid = CTkFrame(temperature_frame, fg_color="transparent")
                settings_grid.grid(row=3, column=0, padx=18, pady=(0, 18), sticky="ew")
                settings_grid.grid_columnconfigure(0, weight=1)
                settings_grid.grid_columnconfigure(1, weight=1)

                CTkLabel(settings_grid, text="Target temperature [°C]").grid(row=0, column=0, sticky="w")
                widgets["target_temperature_entry"] = CTkEntry(settings_grid, width=160)
                widgets["target_temperature_entry"].grid(row=1, column=0, pady=(4, 12), sticky="w")
                widgets["target_temperature_entry"].insert(0, state["target_temperature"])

                widgets["cooler_switch"] = CTkSwitch(settings_grid, text="Cooler enabled")
                widgets["cooler_switch"].grid(row=0, column=1, rowspan=2, padx=(20, 0), sticky="w")
                if state["cooler_enabled"]:
                    widgets["cooler_switch"].select()

                widgets["cooler_startup_switch"] = CTkSwitch(temperature_frame, text="Cooler on at program startup")
                widgets["cooler_startup_switch"].grid(row=4, column=0, padx=18, pady=(0, 12), sticky="w")
                if state["cooler_startup_enabled"]:
                    widgets["cooler_startup_switch"].select()

                CTkButton(temperature_frame, text="Refresh temperature", width=150, command=_refresh_temperature).grid(row=5, column=0, padx=18, pady=(0, 18), sticky="w")
                return

            acquisition_frame = CTkFrame(content)
            acquisition_frame.grid(row=0, column=0, padx=(0, 10), sticky="nsew")
            acquisition_frame.grid_columnconfigure(0, weight=1)
            acquisition_frame.grid_columnconfigure(1, weight=1)

            hardware_frame = CTkFrame(content)
            hardware_frame.grid(row=0, column=1, padx=(10, 0), sticky="nsew")
            hardware_frame.grid_columnconfigure(0, weight=1)

            CTkLabel(acquisition_frame, text="Acquisition", font=("Arial", 18)).grid(row=0, column=0, columnspan=2, padx=18, pady=(18, 10), sticky="w")
            CTkLabel(acquisition_frame, text="Acquisition mode").grid(row=1, column=0, padx=18, sticky="w")
            acquisition_menu = CTkOptionMenu(
                acquisition_frame,
                values=device.get_acquisition_mode_options(),
                width=180,
                variable=CTkVariable(value=state["acquisition_mode"]),
                command=_switch_acquisition_mode,
            )
            acquisition_menu.grid(row=2, column=0, padx=18, pady=(4, 12), sticky="w")

            CTkLabel(acquisition_frame, text="Exposure time [s]").grid(row=3, column=0, padx=18, sticky="w")
            widgets["exposure_entry"] = CTkEntry(acquisition_frame, width=160)
            widgets["exposure_entry"].grid(row=4, column=0, padx=18, pady=(4, 12), sticky="w")
            widgets["exposure_entry"].insert(0, state["exposure"])

            CTkLabel(acquisition_frame, text="Raman excitation wavelength [nm]").grid(row=5, column=0, padx=18, sticky="w")
            widgets["excitation_wavelength_entry"] = CTkEntry(acquisition_frame, width=160)
            widgets["excitation_wavelength_entry"].grid(row=6, column=0, padx=18, pady=(4, 12), sticky="w")
            widgets["excitation_wavelength_entry"].insert(0, state["excitation_wavelength"])

            exposure_seconds, accumulate_seconds, kinetic_seconds = _timing_preview()
            if state["acquisition_mode"] == "Kinetic":
                CTkLabel(acquisition_frame, text="Number of accumulations").grid(row=7, column=0, padx=18, sticky="w")
                widgets["accumulations_entry"] = CTkEntry(acquisition_frame, width=160)
                widgets["accumulations_entry"].grid(row=8, column=0, padx=18, pady=(4, 10), sticky="w")
                widgets["accumulations_entry"].insert(0, state["accumulations"])

                CTkLabel(acquisition_frame, text="Kinetic series length").grid(row=9, column=0, padx=18, sticky="w")
                widgets["kinetic_series_entry"] = CTkEntry(acquisition_frame, width=160)
                widgets["kinetic_series_entry"].grid(row=10, column=0, padx=18, pady=(4, 10), sticky="w")
                widgets["kinetic_series_entry"].insert(0, state["kinetic_series"])

                CTkLabel(acquisition_frame, text="Kinetic cycle time [s]").grid(row=11, column=0, padx=18, sticky="w")
                widgets["cycle_time_entry"] = CTkEntry(acquisition_frame, width=160)
                widgets["cycle_time_entry"].grid(row=12, column=0, padx=18, pady=(4, 4), sticky="w")
                widgets["cycle_time_entry"].insert(0, state["cycle_time"])
                CTkLabel(
                    acquisition_frame,
                    text=f"Delay between scans = cycle - exposure; auto fallback {kinetic_seconds:.5f} s",
                    text_color="gray60",
                ).grid(row=13, column=0, padx=18, pady=(0, 4), sticky="w")
                CTkLabel(acquisition_frame, text=f"Accumulation cycle time: {accumulate_seconds:.5f} s", text_color="gray60").grid(row=14, column=0, padx=18, sticky="w")
            else:
                CTkLabel(acquisition_frame, text=f"Actual exposure: {exposure_seconds:.5f} s", text_color="gray60").grid(row=7, column=0, padx=18, sticky="w")

            if state["page"] == "Multi-track":
                CTkButton(acquisition_frame, text="MT setup", width=120, command=_open_multi_track_setup).grid(row=13, column=0, padx=18, pady=(18, 10), sticky="w")
                CTkLabel(acquisition_frame, text=_track_summary(), text_color="gray60", wraplength=360, justify="left").grid(row=14, column=0, columnspan=2, padx=18, pady=(0, 12), sticky="w")

            CTkLabel(hardware_frame, text="Readout hardware", font=("Arial", 18)).grid(row=0, column=0, padx=18, pady=(18, 10), sticky="w")

            vertical_shift_options = device.get_vertical_shift_speed_options()
            CTkLabel(hardware_frame, text="Vertical shift speed").grid(row=1, column=0, padx=18, sticky="w")
            vertical_shift_menu = CTkOptionMenu(
                hardware_frame,
                width=220,
                values=[option["label"] for option in vertical_shift_options],
                variable=CTkVariable(value=_option_label(vertical_shift_options, state["vertical_shift_key"])),
                command=lambda selected_label: state.__setitem__("vertical_shift_key", _option_key(vertical_shift_options, selected_label, state["vertical_shift_key"])),
            )
            vertical_shift_menu.grid(row=2, column=0, padx=18, pady=(4, 12), sticky="w")

            vertical_clock_options = device.get_vertical_clock_amplitude_options()
            CTkLabel(hardware_frame, text="Vertical clock amplitude").grid(row=3, column=0, padx=18, sticky="w")
            vertical_clock_menu = CTkOptionMenu(
                hardware_frame,
                width=220,
                values=[option["label"] for option in vertical_clock_options],
                variable=CTkVariable(value=_option_label(vertical_clock_options, state["vertical_clock_key"])),
                command=lambda selected_label: state.__setitem__("vertical_clock_key", _option_key(vertical_clock_options, selected_label, state["vertical_clock_key"])),
            )
            vertical_clock_menu.grid(row=4, column=0, padx=18, pady=(4, 12), sticky="w")

            readout_rate_options = _filtered_readout_options()
            CTkLabel(hardware_frame, text="Readout rate").grid(row=5, column=0, padx=18, sticky="w")
            readout_rate_menu = CTkOptionMenu(
                hardware_frame,
                width=220,
                values=[option["label"] for option in readout_rate_options],
                variable=CTkVariable(value=_option_label(readout_rate_options, state["readout_rate_key"])),
                command=lambda selected_label: state.__setitem__("readout_rate_key", _option_key(readout_rate_options, selected_label, state["readout_rate_key"])),
            )
            readout_rate_menu.grid(row=6, column=0, padx=18, pady=(4, 12), sticky="w")

            preamp_options = device.get_preamp_gain_options()
            CTkLabel(hardware_frame, text="Pre-amp gain").grid(row=7, column=0, padx=18, sticky="w")
            preamp_menu = CTkOptionMenu(
                hardware_frame,
                width=220,
                values=[option["label"] for option in preamp_options],
                variable=CTkVariable(value=_option_label(preamp_options, state["preamp_key"])),
                command=lambda selected_label: state.__setitem__("preamp_key", _option_key(preamp_options, selected_label, state["preamp_key"])),
            )
            preamp_menu.grid(row=8, column=0, padx=18, pady=(4, 12), sticky="w")

            CTkLabel(hardware_frame, text="Output amplifier").grid(row=9, column=0, padx=18, sticky="w")
            amplifier_row = CTkFrame(hardware_frame, fg_color="transparent")
            amplifier_row.grid(row=10, column=0, padx=18, pady=(6, 12), sticky="w")
            for amplifier_index, amplifier_name in enumerate(device.get_output_amplifier_options()):
                CTkButton(
                    amplifier_row,
                    text=amplifier_name,
                    width=130,
                    fg_color=("#1F6AA5" if state["output_amplifier"] == amplifier_name else "transparent"),
                    border_width=(0 if state["output_amplifier"] == amplifier_name else 1),
                    border_color="#1F6AA5",
                    command=lambda selected_amplifier=amplifier_name: _switch_output_amplifier(selected_amplifier),
                ).grid(row=0, column=amplifier_index, padx=(0, 8))

        button_row = CTkFrame(self.popup, fg_color="transparent")
        button_row.grid(row=3, column=0, padx=20, pady=(0, 18), sticky="ew")
        button_row.grid_columnconfigure(0, weight=1)

        def _save():
            _snapshot_visible_fields()
            try:
                device.set_settings_page(state["page"])
                device.set_acquisition_mode(state["acquisition_mode"])
                device.set_exposure_seconds(float(state["exposure"]))
                device.set_number_accumulations(int(float(state["accumulations"])))
                device.set_kinetic_series_length(int(float(state["kinetic_series"])))
                if hasattr(device, "set_cycle_time_seconds"):
                    try:
                        device.set_cycle_time_seconds(float(state["cycle_time"]))
                    except (TypeError, ValueError):
                        pass
                device.set_vertical_shift_speed(state["vertical_shift_key"])
                device.set_vertical_clock_amplitude(state["vertical_clock_key"])
                device.set_output_amplifier(state["output_amplifier"])
                device.set_readout_rate(state["readout_rate_key"])
                device.set_preamp_gain(state["preamp_key"])
                device.set_target_temperature(float(state["target_temperature"]))
                device.set_cooler_enabled(bool(state["cooler_enabled"]))
                device.set_cooler_startup_enabled(bool(state["cooler_startup_enabled"]))
                if hasattr(device, "set_excitation_wavelength"):
                    device.set_excitation_wavelength(float(state["excitation_wavelength"]))
            except Exception:
                self.notification("Spectrograph settings must be numeric", "#8e0101")
                return

            was_running = bool(getattr(device, "is_running", False))
            if was_running and hasattr(device, "stop"):
                try:
                    device.stop()
                except Exception:
                    pass
            try:
                device.apply_camera_configuration(state["page"])
            except Exception:
                pass
            finally:
                if was_running and hasattr(device, "start"):
                    try:
                        device.start()
                    except Exception:
                        pass

            if hasattr(self._app, "spectrometer_frame"):
                try:
                    self._app.spectrometer_frame.refresh_kymera_controls(device)
                    self._app.spectrometer_frame.render_cached_plot()
                except Exception:
                    pass

            _close()

        CTkButton(button_row, text="Cancel", fg_color="transparent", border_width=2, border_color="#1F6AA5", command=_close).grid(row=0, column=1, padx=(0, 8), sticky="e")
        CTkButton(button_row, text="Save", command=_save).grid(row=0, column=2, sticky="e")

        _render_settings_page()
        self.popup.transient(self)

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

    # ------------------------------------------------------------------
    # Polarization preset helpers (X / Y buttons + settings popup)
    # ------------------------------------------------------------------

    _POLARIZATION_PRESETS_DIR = os.path.join(
        os.environ.get("APPDATA", os.path.expanduser("~")), "MicroView"
    )
    _POLARIZATION_PRESETS_PATH = os.path.join(
        _POLARIZATION_PRESETS_DIR, "polarization_presets.json"
    )

    def _load_polarization_presets(self):
        """Load polarization preset angles from disk."""
        defaults = {
            "laser_polarizer": {"horizontal": 0, "vertical": 90},
            "hwp": {"horizontal": 0, "vertical": 45},
        }
        try:
            path = os.path.normpath(self._POLARIZATION_PRESETS_PATH)
            if os.path.isfile(path):
                with open(path, "r") as f:
                    data = json.load(f)
                # merge with defaults so missing keys are filled in
                for key in defaults:
                    if key in data and isinstance(data[key], dict):
                        defaults[key].update(data[key])
                return defaults
        except Exception as e:
            debugp("PolarizationPresets", f"Failed to load presets: {e}")
        return defaults

    def _save_polarization_presets(self, presets):
        """Persist polarization preset angles to disk."""
        try:
            os.makedirs(os.path.normpath(self._POLARIZATION_PRESETS_DIR), exist_ok=True)
            path = os.path.normpath(self._POLARIZATION_PRESETS_PATH)
            with open(path, "w") as f:
                json.dump(presets, f, indent=4)
        except Exception as e:
            debugp("PolarizationPresets", f"Failed to save presets: {e}")

    def _find_device_by_name(self, name):
        """Find a device in the current microscope by its name."""
        for dev in self.microscope.devices:
            if dev.name == name:
                return dev
        return None

    def open_polarization_preset_settings(self):
        """Open a popup to configure polarization preset angles for Laser Polarizer and HWP."""
        presets = self._load_polarization_presets()

        popup = CTkToplevel(self)
        popup.title("Polarization Preset Settings")
        popup.geometry("400x220")
        popup.resizable(False, False)

        # --- Header row ---
        CTkLabel(popup, text="", width=80).grid(row=0, column=0, padx=5, pady=(15, 5))
        CTkLabel(popup, text="Laser Polarizer", font=("Arial", 14, "bold")).grid(row=0, column=1, padx=10, pady=(15, 5))
        CTkLabel(popup, text="HWP", font=("Arial", 14, "bold")).grid(row=0, column=2, padx=10, pady=(15, 5))

        # --- Horizontal row ---
        CTkLabel(popup, text="Horizontal", anchor="w").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        lp_h_entry = CTkEntry(popup, width=100)
        lp_h_entry.grid(row=1, column=1, padx=10, pady=5)
        lp_h_entry.insert(0, str(presets["laser_polarizer"]["horizontal"]))

        hwp_h_entry = CTkEntry(popup, width=100)
        hwp_h_entry.grid(row=1, column=2, padx=10, pady=5)
        hwp_h_entry.insert(0, str(presets["hwp"]["horizontal"]))

        # --- Vertical row ---
        CTkLabel(popup, text="Vertical", anchor="w").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        lp_v_entry = CTkEntry(popup, width=100)
        lp_v_entry.grid(row=2, column=1, padx=10, pady=5)
        lp_v_entry.insert(0, str(presets["laser_polarizer"]["vertical"]))

        hwp_v_entry = CTkEntry(popup, width=100)
        hwp_v_entry.grid(row=2, column=2, padx=10, pady=5)
        hwp_v_entry.insert(0, str(presets["hwp"]["vertical"]))

        # --- Save button ---
        def _save():
            try:
                new_presets = {
                    "laser_polarizer": {
                        "horizontal": float(lp_h_entry.get()),
                        "vertical": float(lp_v_entry.get()),
                    },
                    "hwp": {
                        "horizontal": float(hwp_h_entry.get()),
                        "vertical": float(hwp_v_entry.get()),
                    },
                }
            except ValueError:
                messagebox.showerror("Invalid Input", "All fields must be valid numbers.")
                return
            self._save_polarization_presets(new_presets)
            self.notification("Polarization presets saved", color="#1a8300")
            popup.destroy()

        btn_frame = CTkFrame(popup, fg_color="transparent")
        btn_frame.grid(row=3, column=0, columnspan=3, pady=15, sticky="e", padx=10)
        CTkButton(btn_frame, text="Save", width=80, command=_save).pack(side="right")

        popup.transient(self)
        popup.grab_set()

    def move_polarization_preset(self, direction):
        """Move the Laser Polarizer and HWP to preset angles.

        Parameters
        ----------
        direction : str
            Either ``"horizontal"`` or ``"vertical"``.
        """
        presets = self._load_polarization_presets()
        lp_angle = presets["laser_polarizer"].get(direction, 0)
        hwp_angle = presets["hwp"].get(direction, 0)

        laser_plzr = self._find_device_by_name("Laser-Plzr")
        hwp_device = self._find_device_by_name("Half Wave Plate")

        if laser_plzr and not laser_plzr.connected:
            self.notification(f"Laser-Plzr is not connected", color="#8e0101")
            return
        if hwp_device and not hwp_device.connected:
            self.notification(f"Half Wave Plate is not connected", color="#8e0101")
            return
        if not laser_plzr and not hwp_device:
            self.notification("No polarization devices found", color="#8e0101")
            return

        label = "Horizontal" if direction == "horizontal" else "Vertical"

        def _move():
            try:
                if laser_plzr and laser_plzr.connected:
                    laser_plzr.set_absolute_angle(lp_angle)
                if hwp_device and hwp_device.connected:
                    hwp_device.set_absolute_angle(hwp_angle)
                self.after(0, lambda: self.notification(
                    f"Moved to {label} preset  (LP: {lp_angle}°, HWP: {hwp_angle}°)", color="#1a8300"))
            except Exception as e:
                self.after(0, lambda: self.notification(
                    f"Error moving to {label} preset: {e}", color="#8e0101"))

        threading.Thread(target=_move, daemon=True).start()

    # ── Autofocus ─────────────────────────────────────────────────────

    # Default parameters (shared across popup opens)
    _af_params = {
        'sweep_range_mm': 0.1,
        'coarse_step_mm': 0.01,
        'fine_step_mm': 0.001,
        'settle_time_ms': 300,
    }

    def _find_stage(self):
        """Return the first stage device in the current microscope."""
        for device in self.microscope.devices:
            if isinstance(device, (MyStage, MySimStage, MyMCM301Stage)):
                return device
        return None

    def _run_autofocus(self):
        """Start the autofocus sweep with current parameters."""
        # Check camera
        camera_frame = getattr(self._app, 'camera_frame', None)
        if camera_frame is None or not getattr(camera_frame, 'camera', None):
            self.notification("No camera available", color="#8e0101")
            return
        if not getattr(camera_frame.camera, 'connected', False):
            self.notification("Camera not connected", color="#8e0101")
            return

        # Check stage
        stage = self._find_stage()
        if stage is None:
            self.notification("No stage found for this microscope", color="#8e0101")
            return
        if not getattr(stage, 'connected', False):
            self.notification("Stage not connected", color="#8e0101")
            return

        # Prevent double-start
        if getattr(self, '_af_instance', None) is not None:
            self.notification("Autofocus already running", color="#8e0101")
            return

        p = self._af_params
        sweep_range = p['sweep_range_mm']
        coarse_step = p['coarse_step_mm']
        fine_step = p['fine_step_mm']
        settle_s = p['settle_time_ms'] / 1000.0

        # Clamp sweep to stage safety limit
        from dev.autofocus import _get_stage_safety_limit_mm
        safety = _get_stage_safety_limit_mm(stage)
        if safety is not None and sweep_range > safety:
            sweep_range = safety
            debugp("AutoFocus",
                   f"Sweep range reduced to ±{safety:.3f} mm (stage limit)")

        self.notification("Autofocus started…", color="#006bd2")

        # Disable the autofocus button during sweep
        self._set_af_buttons_state("disabled")

        def _on_progress(step, total, z_mm, score):
            pass  # silent — the user sees the live camera feed moving

        def _on_complete(best_z, best_score):
            def _done():
                self._af_instance = None
                self._set_af_buttons_state("normal")
                self.notification(
                    f"Autofocus done: Z={best_z:.4f} mm", color="#1a8300")
            self.after(0, _done)

        def _on_error(exc):
            def _err():
                self._af_instance = None
                self._set_af_buttons_state("normal")
                self.notification(
                    f"Autofocus failed: {exc}", color="#8e0101")
            self.after(0, _err)

        # Resolve save location for the focus-curve CSV.  Lives inside
        # the user's currently-active experiment folder so it sits next
        # to the rest of the run's data.
        _fs = None
        try:
            _node = self.master
            for _ in range(6):
                if not _node:
                    break
                if hasattr(_node, "file_system"):
                    _fs = _node.file_system
                    break
                if hasattr(_node, "spectrometer_frame") and getattr(_node, "spectrometer_frame", None) \
                        and hasattr(_node.spectrometer_frame, "file_system"):
                    _fs = _node.spectrometer_frame.file_system
                    break
                _node = getattr(_node, "master", None)
        except Exception:
            _fs = None

        _save_dir = _fs.get_backup_directory() if _fs is not None else None
        if _save_dir is None:
            debugp("AutoFocus",
                   "Warning: file_system not found; focus curve will NOT be saved.")
        else:
            debugp("AutoFocus", f"Focus curve will save under {_save_dir}\\Autofocus")

        self._af_instance = AutoFocus(
            camera_frame=camera_frame,
            stage=stage,
            sweep_range_mm=sweep_range,
            coarse_step_mm=coarse_step,
            fine_step_mm=fine_step,
            settle_time_s=settle_s,
            save_curve_dir=_save_dir,
            on_progress=_on_progress,
            on_complete=_on_complete,
            on_error=_on_error,
        )

        threading.Thread(target=self._af_instance.run, daemon=True).start()

    def _set_af_buttons_state(self, state):
        """Enable or disable all autofocus widgets in the device panel."""
        for entry in self.device_entries:
            for widget, wtype in entry.widgets:
                if wtype == "Autofocus":
                    try:
                        widget.configure(state=state)
                    except Exception:
                        pass

    def _open_autofocus_settings(self):
        """Open a popup to configure autofocus sweep parameters."""
        # Check stage exists so we can display the safety limit
        stage = self._find_stage()

        if getattr(self, '_af_settings_popup', None):
            try:
                self._af_settings_popup.lift()
            except Exception:
                pass
            return

        self._af_settings_popup = CTkToplevel(self._app)
        self._af_settings_popup.title("Autofocus Settings")
        self._af_settings_popup.geometry("380x300")
        self._af_settings_popup.resizable(False, False)
        self._af_settings_popup.protocol(
            "WM_DELETE_WINDOW", self._close_af_settings)
        try:
            self._af_settings_popup.attributes("-topmost", True)
            self._af_settings_popup.transient(self._app)
            self.after(50, lambda: self._af_settings_popup.attributes(
                "-topmost", False))
        except Exception:
            pass

        body = CTkFrame(self._af_settings_popup)
        body.pack(fill="both", expand=True, padx=16, pady=12)

        headline = CTkLabel(body, text="Autofocus parameters",
                            font=("Arial", 16))
        headline.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        # Show safety limit hint
        from dev.autofocus import _get_stage_safety_limit_mm
        safety = _get_stage_safety_limit_mm(stage) if stage else None
        limit_hint = f"  (stage limit: ±{safety:.1f} mm)" if safety else ""

        p = self._af_params

        CTkLabel(body, text="Sweep range ±(mm):").grid(
            row=1, column=0, sticky="w", pady=6)
        range_entry = CTkEntry(body, width=140)
        range_entry.insert(0, str(p['sweep_range_mm']))
        range_entry.grid(row=1, column=1, sticky="e", pady=6)

        CTkLabel(body, text="Coarse step (mm):").grid(
            row=2, column=0, sticky="w", pady=6)
        coarse_entry = CTkEntry(body, width=140)
        coarse_entry.insert(0, str(p['coarse_step_mm']))
        coarse_entry.grid(row=2, column=1, sticky="e", pady=6)

        CTkLabel(body, text="Fine step (mm):").grid(
            row=3, column=0, sticky="w", pady=6)
        fine_entry = CTkEntry(body, width=140)
        fine_entry.insert(0, str(p['fine_step_mm']))
        fine_entry.grid(row=3, column=1, sticky="e", pady=6)

        CTkLabel(body, text="Settle time (ms):").grid(
            row=4, column=0, sticky="w", pady=6)
        settle_entry = CTkEntry(body, width=140)
        settle_entry.insert(0, str(p['settle_time_ms']))
        settle_entry.grid(row=4, column=1, sticky="e", pady=6)

        if limit_hint:
            info = CTkLabel(body, text=limit_hint, font=("Arial", 11),
                            text_color="grey")
            info.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))

        footer = CTkFrame(self._af_settings_popup, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(8, 12))

        def _save():
            try:
                sr = float(range_entry.get())
                cs = float(coarse_entry.get())
                fs = float(fine_entry.get())
                st = float(settle_entry.get())
            except (ValueError, TypeError):
                messagebox.showerror("Invalid input",
                                     "Please enter valid numeric values.",
                                     parent=self._af_settings_popup)
                return
            if sr <= 0 or cs <= 0 or fs <= 0 or st <= 0:
                messagebox.showerror("Invalid input",
                                     "All values must be positive.",
                                     parent=self._af_settings_popup)
                return
            if fs >= cs:
                messagebox.showerror("Invalid input",
                                     "Fine step must be smaller than coarse step.",
                                     parent=self._af_settings_popup)
                return
            self._af_params['sweep_range_mm'] = sr
            self._af_params['coarse_step_mm'] = cs
            self._af_params['fine_step_mm'] = fs
            self._af_params['settle_time_ms'] = st
            self.notification("Autofocus settings saved", color="#1a8300")
            self._close_af_settings()

        CTkButton(footer, text="Cancel", width=100,
                  command=self._close_af_settings).pack(side="left")
        CTkButton(footer, text="Save", width=100,
                  command=_save).pack(side="right")

        self._af_settings_popup.focus_force()

    def _close_af_settings(self):
        """Close the autofocus settings popup."""
        if getattr(self, '_af_settings_popup', None):
            try:
                self._af_settings_popup.destroy()
            except Exception:
                pass
            self._af_settings_popup = None

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
        # CTkScrollableFrame reparents this widget into an internal canvas,
        # so self.master does NOT point to the application window. Keep a
        # direct reference to the real app (mirrors QuickSetupFrame._app).
        self._app = master
        self.microscope = microscope
        self.popup = None
        self.grid_columnconfigure(0, weight=1)

        title = CTkLabel(self, text="Routines", font=HEADLINE_FONT)
        title.grid(row=0, column=0, padx=20, pady=(12, 6), sticky="w")

        # Polarizer sweep routine button
        self.polarizer_btn = CTkButton(self, text="Polarizer sweep", width=200, command=self.open_polarizer_sweep_popup)
        self.polarizer_btn.grid(row=1, column=0, padx=20, pady=(8, 6), sticky="w")

        # Z-stack routine button
        self.zstack_btn = CTkButton(self, text="Z stack", width=200, command=self.open_zstack_popup)
        self.zstack_btn.grid(row=2, column=0, padx=20, pady=6, sticky="w")

        # Placeholder for future routines (kept for layout parity)
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

    def _get_app(self):
        """Return the MyApp instance.

        RoutinesFrame is a ``CTkScrollableFrame``, so ``self.master`` is an
        internal canvas/frame, NOT the application window. Prefer the
        reference captured at construction time; fall back to walking up the
        master chain in case the widget hierarchy ever differs.
        """
        app = getattr(self, "_app", None)
        if app is not None and (hasattr(app, "camera_frame") or hasattr(app, "notification")):
            return app
        node = self.master
        for _ in range(6):
            if node is None:
                break
            if hasattr(node, "camera_frame") or hasattr(node, "notification"):
                return node
            node = getattr(node, "master", None)
        return app or self.master

    def notification(self, head_message=None, color=None, message=None):
        """Forward notification calls to the application window.

        RoutinesFrame is a ``CTkScrollableFrame`` which does not expose a
        notification API of its own, so before this delegate every call to
        ``self.notification(...)`` from within the routine workflows was
        silently raising ``AttributeError`` and being swallowed by the
        surrounding ``try/except`` blocks. That made validation errors
        (e.g. "Stage not connected") invisible to the user, who would see
        the Start button do "nothing".
        """
        try:
            self._get_app().notification(head_message, message, color)
        except Exception:
            # Last-resort: surface the message to the console so it is at
            # least visible to the developer running the app.
            print(f"[Routines] {head_message}{(' - ' + message) if message else ''}")

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

    # ──────────────────────────────────────────────────────────────────
    # Z-stack routine (Kymera + Newton)
    #
    # Flow:
    #   page 1 : start / stop / step in µm + "use autofocus" toggle
    #   page 2 : (only when autofocus is OFF) — let the user focus
    #            manually and click "Set zero" to anchor z=0
    #   page 3 : save settings (file name, separator, .sif, separate files)
    #            and "Start" button that launches the worker thread.
    #
    # For each z position the worker performs:
    #   1. Open white-light shutter (KST201)
    #   2. Auto-expose the camera, grab a frame, save it
    #   3. Close white-light shutter
    #   4. Open laser shutter (KSC101)
    #   5. Set camera to its minimum exposure, grab a frame, save it
    #   6. Drive the Kymera through its currently-configured acquisition
    #      (Single or Kinetic) and save the resulting spectrum
    #   7. Close laser shutter
    #   8. Move stage to next z position
    # ──────────────────────────────────────────────────────────────────

    # Default values shared across popup re-opens
    _zstack_params = {
        "start_um": -5.0,
        "stop_um": 5.0,
        "step_um": 1.0,
        "use_autofocus": False,
    }
    _zstack_save = {
        "file_name": "ZStack",
        "separator": "Comma",
        "save_sif": False,
        "separate_files": True,
    }

    def open_zstack_popup(self):
        """Open the Z-stack configuration popup (page 1)."""
        if self.popup:
            try:
                self.popup.lift()
            except Exception:
                pass
            return
        if getattr(self, "_zstack_running", False):
            try:
                self.notification("A Z-stack is already running", color="#e17e00")
            except Exception:
                pass
            return

        # Reserve a dedicated ZStackRoutineN folder (mirrors the sweep flow)
        try:
            self._ensure_zstack_routine_folder()
        except Exception:
            pass

        self.popup = CTkToplevel(self.master)
        self.popup.title("Z stack")
        self.popup.geometry("460x420")
        self.popup.resizable(False, False)
        self.popup.protocol("WM_DELETE_WINDOW", self.close_popup)
        try:
            self.popup.attributes("-topmost", True)
            self.popup.transient(self.master)
            self.after(50, lambda: self.popup.attributes("-topmost", False))
        except Exception:
            pass

        self.page_frame = CTkFrame(self.popup)
        self.page_frame.pack(fill="both", expand=True, padx=16, pady=12)
        self._build_zstack_page1()
        self.popup.focus_force()

    def _zstack_clear_footers(self):
        """Remove any non-page CTkFrame children of the popup (footers)."""
        try:
            for child in list(self.popup.winfo_children()):
                if isinstance(child, CTkFrame) and child is not self.page_frame:
                    try:
                        child.destroy()
                    except Exception:
                        pass
        except Exception:
            pass

    def _zstack_clear_page(self):
        try:
            for w in self.page_frame.winfo_children():
                w.destroy()
        except Exception:
            pass

    def _build_zstack_page1(self):
        """Page 1 — Z-stack parameters."""
        self._zstack_clear_page()

        p = self._zstack_params

        headline = CTkLabel(self.page_frame, text="Configure Z stack", font=("Arial", 16))
        headline.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        CTkLabel(self.page_frame, text="Z start (µm):").grid(row=1, column=0, sticky="w", pady=6)
        self._zstart_entry = CTkEntry(self.page_frame, width=160, placeholder_text=str(p["start_um"]))
        self._zstart_entry.grid(row=1, column=1, sticky="e", pady=6)
        self._zstart_entry.insert(0, str(p["start_um"]))

        CTkLabel(self.page_frame, text="Z stop (µm):").grid(row=2, column=0, sticky="w", pady=6)
        self._zstop_entry = CTkEntry(self.page_frame, width=160, placeholder_text=str(p["stop_um"]))
        self._zstop_entry.grid(row=2, column=1, sticky="e", pady=6)
        self._zstop_entry.insert(0, str(p["stop_um"]))

        CTkLabel(self.page_frame, text="Step size (µm):").grid(row=3, column=0, sticky="w", pady=6)
        self._zstep_entry = CTkEntry(self.page_frame, width=160, placeholder_text=str(p["step_um"]))
        self._zstep_entry.grid(row=3, column=1, sticky="e", pady=6)
        self._zstep_entry.insert(0, str(p["step_um"]))

        self._zautofocus_switch = CTkSwitch(self.page_frame, text="Run autofocus and zero before stack")
        self._zautofocus_switch.grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 0))
        if p["use_autofocus"]:
            self._zautofocus_switch.select()
        else:
            self._zautofocus_switch.deselect()

        hint = CTkLabel(
            self.page_frame,
            text=(
                "Positions are relative to z=0. With autofocus ON the focus plane is "
                "found and set as z=0 automatically; with autofocus OFF you set z=0 "
                "manually on the next page."
            ),
            font=("Arial", 11),
            text_color="grey",
            wraplength=400,
            justify="left",
        )
        hint.grid(row=5, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self._zstack_clear_footers()
        footer = CTkFrame(self.popup, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(8, 12))
        cancel_btn = CTkButton(footer, text="Cancel", width=110, fg_color="transparent",
                               border_width=2, border_color="#1F6AA5", command=self.close_popup)
        cancel_btn.pack(side="left")
        next_btn = CTkButton(footer, text="Next", width=120, command=self._zstack_page1_next)
        next_btn.pack(side="right")

    def _zstack_page1_next(self):
        try:
            start = float(self._zstart_entry.get())
            stop = float(self._zstop_entry.get())
            step = float(self._zstep_entry.get())
        except Exception:
            try:
                self.notification("Z-stack parameters must be numeric", color="#8e0101")
            except Exception:
                pass
            return

        if step <= 0:
            try:
                self.notification("Step size must be positive", color="#8e0101")
            except Exception:
                pass
            return
        if start == stop:
            try:
                self.notification("Z start and stop must differ", color="#8e0101")
            except Exception:
                pass
            return

        use_af = bool(self._zautofocus_switch.get())

        # Persist for the next popup open
        self._zstack_params = {
            "start_um": start,
            "stop_um": stop,
            "step_um": step,
            "use_autofocus": use_af,
        }

        if use_af:
            # Autofocus path: skip the set-zero page and go straight to save settings
            self._build_zstack_page3()
        else:
            self._build_zstack_page2()

    def _build_zstack_page2(self):
        """Page 2 — manual set-zero (only when autofocus is OFF)."""
        self._zstack_clear_page()

        headline = CTkLabel(self.page_frame, text="Focus and zero the stage", font=("Arial", 16))
        headline.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        instruction = CTkLabel(
            self.page_frame,
            text=(
                "Use the live camera view to bring the sample into focus with the "
                "white light source, then click \"Set z=0 here\" to anchor the "
                "current stage position as z=0 for the stack."
            ),
            font=("Arial", 12),
            text_color="white",
            wraplength=400,
            justify="left",
        )
        instruction.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 12))

        # Display current stage position so the user can see it update
        self._z_pos_var = StringVar(value="--- mm")
        CTkLabel(self.page_frame, text="Current Z position:").grid(row=2, column=0, sticky="w", pady=6)
        self._z_pos_label = CTkLabel(self.page_frame, textvariable=self._z_pos_var, font=("Arial", 14, "bold"))
        self._z_pos_label.grid(row=2, column=1, sticky="e", pady=6)

        refresh_btn = CTkButton(
            self.page_frame, text="Refresh position", width=160,
            command=self._zstack_refresh_z_pos,
        )
        refresh_btn.grid(row=3, column=0, sticky="w", pady=(8, 0))

        set_zero_btn = CTkButton(
            self.page_frame, text="Set z=0 here", width=160,
            command=self._zstack_set_zero,
        )
        set_zero_btn.grid(row=3, column=1, sticky="e", pady=(8, 0))

        self._zstack_zero_status = CTkLabel(self.page_frame, text="z=0 not yet set",
                                            font=("Arial", 12), text_color="grey")
        self._zstack_zero_status.grid(row=4, column=0, columnspan=2, sticky="w", pady=(10, 0))

        # Push an initial readout
        self._zstack_refresh_z_pos()

        self._zstack_clear_footers()
        footer = CTkFrame(self.popup, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(8, 12))
        back_btn = CTkButton(footer, text="Back", width=120, command=self._build_zstack_page1)
        back_btn.pack(side="left")
        next_btn = CTkButton(footer, text="Next", width=120, command=self._build_zstack_page3)
        next_btn.pack(side="right")

    def _zstack_refresh_z_pos(self):
        stage = self._zstack_find_stage()
        if stage is None or not getattr(stage, "connected", False):
            try:
                self._z_pos_var.set("stage not connected")
            except Exception:
                pass
            return

        def _worker():
            try:
                pos = float(stage.get_position() or 0.0)
            except Exception:
                pos = None
            def _ui():
                try:
                    if pos is None:
                        self._z_pos_var.set("---")
                    else:
                        self._z_pos_var.set(f"{pos*1000.0:+.3f} µm  ({pos:+.4f} mm)")
                except Exception:
                    pass
            self.after(0, _ui)

        threading.Thread(target=_worker, daemon=True).start()

    def _zstack_set_zero(self):
        stage = self._zstack_find_stage()
        if stage is None or not getattr(stage, "connected", False):
            try:
                self.notification("Stage not connected", color="#8e0101")
            except Exception:
                pass
            return

        def _worker():
            try:
                if hasattr(stage, "set_zero"):
                    stage.set_zero()
                elif hasattr(stage, "move_to"):
                    stage.move_to(0)
                def _ui():
                    try:
                        self._zstack_zero_status.configure(text="z=0 set", text_color="#1a8300")
                    except Exception:
                        pass
                    self._zstack_refresh_z_pos()
                self.after(0, _ui)
            except Exception as e:
                debugp("Routines", f"Set z=0 failed: {e}")
                def _err():
                    try:
                        self._zstack_zero_status.configure(text=f"Set z=0 failed: {e}", text_color="#8e0101")
                    except Exception:
                        pass
                self.after(0, _err)

        threading.Thread(target=_worker, daemon=True).start()

    def _build_zstack_page3(self):
        """Page 3 — Save settings (mimics the Kymera signal-save popup)."""
        self._zstack_clear_page()

        s = self._zstack_save

        headline = CTkLabel(self.page_frame, text="Save settings", font=("Arial", 16))
        headline.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        name_frame = CTkFrame(self.page_frame, fg_color="transparent")
        name_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        name_frame.grid_columnconfigure(1, weight=1)
        CTkLabel(name_frame, text="File name").grid(row=0, column=0, padx=(0, 10), sticky="w")
        self._zsave_name_entry = CTkEntry(name_frame)
        self._zsave_name_entry.grid(row=0, column=1, sticky="ew")
        self._zsave_name_entry.insert(0, s.get("file_name", "ZStack"))

        # Separator radios
        sep_frame = CTkFrame(self.page_frame)
        sep_frame.grid(row=2, column=0, padx=(0, 6), pady=8, sticky="nsew")
        CTkLabel(sep_frame, text="Separator").pack(anchor="w", padx=12, pady=(10, 2))
        self._zsave_sep_var = StringVar(value=s.get("separator", "Comma"))
        for label in ("Comma", "Tab", "Semicolon", "Space"):
            CTkRadioButton(
                sep_frame,
                text=label,
                variable=self._zsave_sep_var,
                value=label,
                border_color="#1F6AA5",
            ).pack(anchor="w", padx=12, pady=3)

        # Output options
        opt_frame = CTkFrame(self.page_frame)
        opt_frame.grid(row=2, column=1, padx=(6, 0), pady=8, sticky="nsew")
        CTkLabel(opt_frame, text="Output").pack(anchor="w", padx=12, pady=(10, 2))
        self._zsave_sif_check = CTkCheckBox(
            opt_frame, text="Also save .sif",
            border_width=2, border_color="#1F6AA5",
        )
        self._zsave_sif_check.pack(anchor="w", padx=12, pady=5)
        if s.get("save_sif", False):
            self._zsave_sif_check.select()
        self._zsave_separate_check = CTkCheckBox(
            opt_frame, text="Write each image to a separate file",
            border_width=2, border_color="#1F6AA5",
        )
        self._zsave_separate_check.pack(anchor="w", padx=12, pady=5)
        if s.get("separate_files", True):
            self._zsave_separate_check.select()

        info = CTkLabel(
            self.page_frame,
            text=(
                "Files are saved to a ZStackRoutine folder inside the current "
                "experiment. Each Z position gets its own subfolder containing "
                "the white-light image, the laser-spot image, and the Kymera "
                "spectrum."
            ),
            font=("Arial", 11),
            text_color="grey",
            wraplength=420,
            justify="left",
        )
        info.grid(row=3, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self._zstack_clear_footers()
        footer = CTkFrame(self.popup, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(8, 12))
        back_target = self._build_zstack_page1 if self._zstack_params.get("use_autofocus") else self._build_zstack_page2
        back_btn = CTkButton(footer, text="Back", width=120, command=back_target)
        back_btn.pack(side="left")
        start_btn = CTkButton(footer, text="Start", width=120, command=self._zstack_start)
        start_btn.pack(side="right")

    # ── Device lookup helpers ─────────────────────────────────────────

    def _zstack_find_stage(self):
        try:
            microscope = getattr(self, "microscope", None) or getattr(self._get_app(), "selected_microscope", None)
            if microscope:
                for dev in microscope.devices:
                    if isinstance(dev, (MyStage, MySimStage, MyMCM301Stage)):
                        return dev
        except Exception:
            pass
        return None

    def _zstack_find_kymera(self):
        try:
            spec_frame = getattr(self._get_app(), "spectrometer_frame", None)
            if spec_frame and getattr(spec_frame, "connected_spectrometers", None):
                for spec in spec_frame.connected_spectrometers:
                    if getattr(spec, "supports_image_view", False) and getattr(spec, "connected", False):
                        return spec
        except Exception:
            pass
        # Fall back to scanning the microscope for any image-view spectrometer
        try:
            microscope = getattr(self, "microscope", None) or getattr(self._get_app(), "selected_microscope", None)
            if microscope:
                for dev in microscope.devices:
                    if isinstance(dev, MySpectrometer) and getattr(dev, "supports_image_view", False):
                        return dev
        except Exception:
            pass
        return None

    def _zstack_find_white_shutter(self):
        try:
            microscope = getattr(self, "microscope", None) or getattr(self._get_app(), "selected_microscope", None)
            if microscope:
                for dev in microscope.devices:
                    if isinstance(dev, MyShutter) and getattr(dev, "model", None) == "KST201" \
                            and getattr(dev, "connected", False):
                        return dev
        except Exception:
            pass
        return None

    def _zstack_find_laser_shutter(self):
        try:
            microscope = getattr(self, "microscope", None) or getattr(self._get_app(), "selected_microscope", None)
            if microscope:
                for dev in microscope.devices:
                    if isinstance(dev, MyShutter) and getattr(dev, "model", None) == "KSC101" \
                            and getattr(dev, "connected", False):
                        return dev
        except Exception:
            pass
        return None

    # ── Z-stack routine folder management ─────────────────────────────

    def _ensure_zstack_routine_folder(self):
        """Create the next ZStackRoutineN folder under the experiment directory
        and set it as the active sweep-routine folder so the existing
        FileSystem.get_spectrometer_directory plumbing places files into it.
        """
        if getattr(self, "_sweep_routine_started", False):
            return

        fs = self._get_filesystem()
        if not fs:
            return

        base = fs.backup_directory
        try:
            existing = []
            if os.path.exists(base) and os.path.isdir(base):
                import re as _re
                pat = _re.compile(r"ZStackRoutine(\d+)$")
                for name in os.listdir(base):
                    m = pat.match(name)
                    if m:
                        existing.append(int(m.group(1)))
            next_idx = (max(existing) + 1) if existing else 1
            folder_name = f"ZStackRoutine{next_idx}"
            folder_path = os.path.join(base, folder_name)
            os.makedirs(folder_path, exist_ok=True)
            fs.current_sweep_routine = folder_name
            fs.current_sweep_has_data = False
            self._sweep_routine_started = True
            debugp("Routines", f"Started new Z-stack routine folder: {folder_name}")
        except Exception as e:
            debugp("Routines", f"Failed to start ZStackRoutine folder: {e}")

    # ── Start ─────────────────────────────────────────────────────────

    def _zstack_start(self):
        """Validate the resources and launch the Z-stack worker thread."""
        # Persist save settings for re-opens
        try:
            self._zstack_save = {
                "file_name": (self._zsave_name_entry.get().strip() or "ZStack"),
                "separator": self._zsave_sep_var.get() if hasattr(self, "_zsave_sep_var") else "Comma",
                "save_sif": bool(self._zsave_sif_check.get()),
                "separate_files": bool(self._zsave_separate_check.get()),
            }
        except Exception as e:
            debugp("Routines", f"Z-stack: persist save cfg failed: {e}")

        debugp("Routines", "Z-stack: Start clicked, validating resources")

        stage = self._zstack_find_stage()
        if stage is None or not getattr(stage, "connected", False):
            debugp("Routines", f"Z-stack: stage check failed (stage={stage})")
            self.notification("Z-stack: stage not connected", color="#8e0101")
            return

        kymera = self._zstack_find_kymera()
        if kymera is None:
            debugp("Routines", "Z-stack: Kymera spectrograph not found")
            self.notification("Z-stack: Kymera spectrograph not connected", color="#8e0101")
            return

        app = self._get_app()
        camera_frame = getattr(app, "camera_frame", None)
        if not camera_frame or not getattr(camera_frame, "camera", None) \
                or not getattr(camera_frame.camera, "connected", False):
            debugp("Routines", f"Z-stack: camera not connected (app={app}, camera_frame={camera_frame})")
            self.notification("Z-stack: camera not connected", color="#8e0101")
            return

        white_shutter = self._zstack_find_white_shutter()
        laser_shutter = self._zstack_find_laser_shutter()
        if white_shutter is None:
            debugp("Routines",
                   "Z-stack: white-light shutter (KST201) not connected — toggle it ON in the Devices panel")
            self.notification(
                "Z-stack: white-light shutter (KST201) not connected",
                color="#8e0101",
            )
            return
        if laser_shutter is None:
            debugp("Routines",
                   "Z-stack: laser shutter (KSC101) not connected — toggle it ON in the Devices panel")
            self.notification(
                "Z-stack: laser shutter (KSC101) not connected",
                color="#8e0101",
            )
            return

        spec_frame = getattr(app, "spectrometer_frame", None)
        if spec_frame is None:
            debugp("Routines", "Z-stack: spectrometer_frame missing on app")
            self.notification("Z-stack: spectrometer frame unavailable", color="#8e0101")
            return

        debugp(
            "Routines",
            f"Z-stack: resources OK (stage={stage}, kymera={kymera}, "
            f"white={white_shutter}, laser={laser_shutter})",
        )

        # Build the list of z positions (µm). Inclusive of both ends.
        start_um = float(self._zstack_params["start_um"])
        stop_um = float(self._zstack_params["stop_um"])
        step_um = abs(float(self._zstack_params["step_um"]))
        if stop_um < start_um:
            step_um = -step_um
        positions_um = []
        z = start_um
        # ~1e-6 µm tolerance to include the final endpoint
        while (step_um > 0 and z <= stop_um + 1e-6) or (step_um < 0 and z >= stop_um - 1e-6):
            positions_um.append(round(z, 6))
            z += step_um
            if len(positions_um) > 100000:
                break
        if not positions_um:
            try:
                self.notification("No Z positions in range", color="#8e0101")
            except Exception:
                pass
            return

        # Lock devices and tear down the popup
        try:
            self.notification(f"Z-stack started ({len(positions_um)} positions)", color="#006bd2")
        except Exception:
            pass

        if self.popup:
            try:
                self.popup.destroy()
            except Exception:
                pass
            self.popup = None

        resources = {
            "stage": stage,
            "kymera": kymera,
            "camera_frame": camera_frame,
            "white_shutter": white_shutter,
            "laser_shutter": laser_shutter,
            "spec_frame": spec_frame,
        }

        self._zstack_running = True
        threading.Thread(
            target=self._zstack_worker,
            args=(resources, positions_um, dict(self._zstack_save), bool(self._zstack_params.get("use_autofocus"))),
            daemon=True,
        ).start()

    # ── Worker ────────────────────────────────────────────────────────

    def _zstack_worker(self, resources, positions_um, save_cfg, use_autofocus):
        """Background thread that drives the whole Z-stack acquisition."""
        try:
            self._zstack_worker_body(resources, positions_um, save_cfg, use_autofocus)
        except Exception as worker_err:
            import traceback as _tb
            debugp("Routines", f"Z-stack worker crashed: {worker_err}")
            _tb.print_exc()
            try:
                app = self._get_app()
                self.after(
                    0,
                    lambda e=worker_err: app.notification(
                        "Z-stack failed", str(e), "#8e0101"
                    ),
                )
            except Exception:
                pass
            try:
                self._teardown_sweep_routine()
            except Exception:
                pass
            self._zstack_running = False

    def _zstack_worker_body(self, resources, positions_um, save_cfg, use_autofocus):
        """Inner worker body. Wrapped by :meth:`_zstack_worker` so any
        unexpected exception becomes a visible notification instead of a
        silent dead thread."""
        from datetime import datetime as _dt
        import numpy as _np

        stage = resources["stage"]
        kymera = resources["kymera"]
        camera_frame = resources["camera_frame"]
        white_shutter = resources["white_shutter"]
        laser_shutter = resources["laser_shutter"]
        spec_frame = resources["spec_frame"]
        debugp(
            "Routines",
            f"Z-stack worker: starting ({len(positions_um)} positions, autofocus={use_autofocus})",
        )

        delimiter = {"Comma": ",", "Tab": "\t", "Semicolon": ";", "Space": " "}.get(
            save_cfg.get("separator", "Comma"), ","
        )
        save_sif = bool(save_cfg.get("save_sif", False))
        separate_files = bool(save_cfg.get("separate_files", True))
        base_name = save_cfg.get("file_name", "ZStack") or "ZStack"

        fs = self._get_filesystem()
        routine_root = None
        if fs and getattr(fs, "current_sweep_routine", None):
            routine_root = os.path.join(fs.backup_directory, fs.current_sweep_routine)
            try:
                os.makedirs(routine_root, exist_ok=True)
            except Exception:
                pass

        app = self._get_app()

        def _ui(fn, *args):
            try:
                self.after(0, lambda: fn(*args))
            except Exception:
                pass

        def _notify(msg, color="#006bd2", detail=None):
            try:
                self.after(0, lambda: app.notification(msg, detail, color))
            except Exception:
                pass

        # Save what we need to restore after the run
        camera_was_auto = bool(getattr(camera_frame.camera, "auto_exposure_enabled", False))
        try:
            original_camera_us = int(camera_frame.camera.camera.exposure_time_us)
        except Exception:
            original_camera_us = None

        # Only the "single" acquisition mode produces a single trace worth
        # overlaying live; in kinetic mode we still save every frame but do
        # not redraw the cumulative plot.
        single_mode = (getattr(kymera, "selected_acquisition_mode", "Single") == "Single")

        # Take ownership of the spectrum plot: this stops live view AND keeps
        # the temperature watchdog from auto-restarting it (which previously
        # left live acquisition fighting our capture calls and wiping the
        # overlay every 20 ms). Give the GUI thread a beat to apply it and
        # for the kymera live acquisition thread to fully abort before the
        # first capture so they never contend for the Andor SDK.
        _ui(spec_frame.begin_routine_plot, "Z stack")
        time.sleep(0.6)

        # Optional autofocus pass (uses the same engine as the camera-frame button)
        if use_autofocus:
            _notify("Running autofocus…", "#006bd2")
            try:
                af = AutoFocus(
                    camera_frame=camera_frame,
                    stage=stage,
                    sweep_range_mm=0.1,
                    coarse_step_mm=0.010,
                    fine_step_mm=0.001,
                    settle_time_s=0.30,
                )
                af.run()
                # The autofocus engine moves to the best-focus Z but does not
                # re-zero afterwards. Anchor z=0 at the focused position so
                # the user's start/stop are relative to focus.
                if hasattr(stage, "set_zero"):
                    stage.set_zero()
            except Exception as e:
                debugp("Routines", f"Autofocus failed: {e}")
                _notify("Autofocus failed; continuing with current z=0", "#e17e00",
                        detail=str(e))

        # Move to start position
        start_mm = positions_um[0] / 1000.0
        try:
            stage.move_to(start_mm)
            time.sleep(0.3)
        except Exception as e:
            _notify("Failed to move to Z start", "#8e0101", detail=str(e))
            return

        # Cache the spectrum-frame helpers we'll call from the worker
        prepare_frames = getattr(spec_frame, "prepare_signal_frames_for_ascii", None)
        build_header = getattr(spec_frame, "build_signal_acquisition_header", None)
        write_ascii = getattr(spec_frame, "write_signal_ascii_file", None)
        save_sif_files_helper = getattr(spec_frame, "save_signal_sif_files", None)
        format_ascii = getattr(spec_frame, "format_ascii_value", lambda v: str(v))

        positions_log_path = None
        if routine_root is not None:
            positions_log_path = os.path.join(routine_root, "z_positions.txt")
            try:
                with open(positions_log_path, "w") as f:
                    f.write("# Z-stack positions (µm relative to z=0)\n")
                    f.write(f"# Started {_dt.now().isoformat()}\n")
                    for i, z in enumerate(positions_um):
                        f.write(f"{i:04d}\t{z:.4f}\n")
            except Exception as e:
                debugp("Routines", f"Could not write z_positions.txt: {e}")

        total = len(positions_um)

        try:
            for idx, z_um in enumerate(positions_um):
                z_mm = z_um / 1000.0

                # Build the per-position folder under the routine root
                z_folder_name = f"Z_{idx:04d}_{z_um:+.3f}um".replace("+", "p").replace("-", "m")
                if routine_root is not None:
                    z_folder = os.path.join(routine_root, z_folder_name)
                else:
                    z_folder = None
                    try:
                        if fs:
                            z_folder = os.path.join(fs.backup_directory, z_folder_name)
                    except Exception:
                        z_folder = None
                if z_folder is not None:
                    try:
                        os.makedirs(z_folder, exist_ok=True)
                    except Exception:
                        z_folder = None

                _notify(f"Z {idx + 1}/{total}: {z_um:+.3f} µm", "#006bd2")

                # ── 1-3. White light image with auto-exposure ────────
                try:
                    white_shutter.open()
                except Exception as e:
                    debugp("Routines", f"White shutter open failed: {e}")
                time.sleep(0.4)  # KST201 motor settle

                try:
                    camera_frame.camera.set_auto_exposure(True)
                except Exception:
                    pass
                # Let the proportional auto-exposure controller settle. The
                # controller adjusts by ~50% of the error each frame, so a
                # second or two with a 100 ms frame cadence is usually plenty.
                self._zstack_wait_for_camera_settle(camera_frame, duration_s=2.0)

                white_path = None
                if z_folder is not None:
                    white_path = os.path.join(z_folder, f"{base_name}_whitelight.png")
                    self._zstack_save_camera_image(camera_frame, white_path)

                try:
                    camera_frame.camera.set_auto_exposure(False)
                except Exception:
                    pass

                try:
                    white_shutter.close()
                except Exception as e:
                    debugp("Routines", f"White shutter close failed: {e}")
                time.sleep(0.4)  # let the motor finish moving back

                # ── 4-5. Laser spot image at minimum exposure ───────
                try:
                    laser_shutter.open()
                except Exception as e:
                    debugp("Routines", f"Laser shutter open failed: {e}")
                time.sleep(0.15)  # KSC101 solenoid is fast

                min_us = int(getattr(camera_frame.camera, "_auto_exposure_min_us", 40)) or 40
                self._zstack_set_camera_exposure_us(camera_frame, min_us)
                # Give the camera one full frame to flush the previous exposure
                time.sleep(max(min_us / 1_000_000.0 * 2.0, 0.2))

                laser_path = None
                if z_folder is not None:
                    laser_path = os.path.join(z_folder, f"{base_name}_laser_spot.png")
                    self._zstack_save_camera_image(camera_frame, laser_path)

                # ── 6. Kymera acquisition (Single or Kinetic) ───────
                # Live view is held off for the whole routine, so the only
                # acquisition touching the Andor SDK here is ours. Retry once
                # if a capture comes back empty (e.g. a transient temperature
                # destabilization) so a single hiccup doesn't drop a position.
                try:
                    if getattr(kymera, "is_running", False):
                        kymera.stop()
                except Exception:
                    pass

                frame_count = 1
                try:
                    frame_count = max(int(kymera.get_signal_frame_count()), 1)
                except Exception:
                    frame_count = 1
                should_spool = frame_count > 1 and save_sif

                kymera_frames = []
                for attempt in range(2):
                    try:
                        try:
                            kymera_frames = kymera.capture_signal_series(spool_sif=should_spool)
                        except TypeError:
                            kymera_frames = kymera.capture_signal_series()
                    except Exception as cap_err:
                        debugp("Routines",
                               f"capture_signal_series failed at z={z_um} "
                               f"(attempt {attempt + 1}): {cap_err}")
                        kymera_frames = []
                    if kymera_frames:
                        break
                    debugp("Routines",
                           f"Empty capture at z={z_um} (attempt {attempt + 1}); retrying")
                    time.sleep(0.5)

                if not kymera_frames:
                    _notify(f"No Kymera data at z={z_um:+.2f} µm", "#e17e00")

                # ── Save Kymera output (ASCII + optional SIF) ────────
                if kymera_frames and z_folder is not None and prepare_frames and build_header and write_ascii:
                    try:
                        processed = prepare_frames(kymera, kymera_frames)
                        header = build_header(kymera, len(processed))
                        if processed:
                            stem = os.path.join(z_folder, f"{base_name}_Z_{idx:04d}")
                            if separate_files:
                                for fi, (dx, dy) in enumerate(processed, start=1):
                                    suffix = f"_{fi:04d}" if len(processed) > 1 else ""
                                    asc_path = f"{stem}{suffix}.asc"
                                    rows = [[format_ascii(x), format_ascii(y)]
                                            for x, y in zip(dx, dy)]
                                    write_ascii(asc_path, header, rows, delimiter)
                            else:
                                common = min(f[0].size for f in processed)
                                common = min(common, *(f[1].size for f in processed))
                                dx0 = processed[0][0][:common]
                                cols = [f[1][:common] for f in processed]
                                rows = []
                                for ri in range(common):
                                    rows.append(
                                        [format_ascii(dx0[ri])]
                                        + [format_ascii(c[ri]) for c in cols]
                                    )
                                write_ascii(f"{stem}.asc", header, rows, delimiter)

                            if save_sif and save_sif_files_helper:
                                try:
                                    save_sif_files_helper(kymera, stem, header,
                                                          len(processed), separate_files)
                                except Exception as sif_err:
                                    debugp("Routines", f"SIF save failed at z={z_um}: {sif_err}")
                    except Exception as e:
                        debugp("Routines", f"Saving Kymera output failed at z={z_um}: {e}")

                # ── Overlay onto the spectrum plot (single mode only) ─
                # In kinetic mode we skip the live overlay (the user asked
                # for show-as-we-go only for single acquisitions); the data
                # is still saved above.
                if single_mode and kymera_frames:
                    try:
                        last_wavelengths, last_intensities = kymera_frames[-1]
                        wl = _np.asarray(last_wavelengths, dtype=_np.float64).copy()
                        it = _np.asarray(last_intensities, dtype=_np.float64).copy()
                        _ui(spec_frame.add_routine_trace, kymera, wl, it,
                            f"z={z_um:+.2f} µm")
                    except Exception as e:
                        debugp("Routines", f"Overlay update failed at z={z_um}: {e}")

                # ── 7. Close laser shutter ─────────────────────────
                try:
                    laser_shutter.close()
                except Exception as e:
                    debugp("Routines", f"Laser shutter close failed: {e}")
                time.sleep(0.1)

                # ── 8. Move to next z (skip after last position) ───
                if idx + 1 < total:
                    next_mm = positions_um[idx + 1] / 1000.0
                    try:
                        stage.move_to(next_mm)
                        time.sleep(0.2)
                    except Exception as e:
                        _notify("Failed to move to next Z", "#8e0101", detail=str(e))
                        break

            _notify(f"Z-stack done ({total} positions)", "#1a8300",
                    detail=routine_root if routine_root else None)

        finally:
            # Restore camera and shutter state best-effort
            try:
                white_shutter.close()
            except Exception:
                pass
            try:
                laser_shutter.close()
            except Exception:
                pass
            if original_camera_us is not None:
                try:
                    self._zstack_set_camera_exposure_us(camera_frame, original_camera_us)
                except Exception:
                    pass
            try:
                camera_frame.camera.set_auto_exposure(camera_was_auto)
            except Exception:
                pass

            # Release the spectrum plot. We do NOT auto-resume live view so
            # the cumulative overlay stays on screen for inspection; the
            # user can press play to return to live view.
            try:
                _ui(spec_frame.end_routine_plot, False)
            except Exception:
                pass

            # Clear the routine flag so a follow-up run gets its own folder
            try:
                self._teardown_sweep_routine()
            except Exception:
                pass
            self._zstack_running = False

    # ── Worker helpers ────────────────────────────────────────────────

    def _zstack_set_camera_exposure_us(self, camera_frame, exposure_us):
        """Set the camera exposure directly in microseconds, bypassing the
        ``update_exposure`` GUI path which expects milliseconds and is gated
        by the software-trigger timer."""
        exposure_us = max(int(exposure_us), 1)
        try:
            cam = camera_frame.camera.camera
            cam.exposure_time_us = exposure_us
        except Exception as e:
            debugp("Routines", f"Failed to set camera exposure: {e}")

    def _zstack_wait_for_camera_settle(self, camera_frame, duration_s=2.0):
        """Block until ``duration_s`` has elapsed, monitoring fresh frames so
        the auto-exposure controller has time to converge."""
        deadline = time.monotonic() + max(float(duration_s), 0.0)
        previous = getattr(camera_frame, "current_image", None)
        # Force at least one fresh frame
        while time.monotonic() < deadline:
            time.sleep(0.05)
            img = getattr(camera_frame, "current_image", None)
            if img is not None and img is not previous:
                previous = img

    def _zstack_save_camera_image(self, camera_frame, path):
        """Wait for a fresh frame and write it to ``path`` as PNG."""
        if not path:
            return None
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except Exception:
            pass

        deadline = time.monotonic() + 3.0
        previous = getattr(camera_frame, "current_image", None)
        img = previous
        while time.monotonic() < deadline:
            time.sleep(0.05)
            current = getattr(camera_frame, "current_image", None)
            if current is not None and current is not previous:
                img = current
                break
        if img is None:
            img = getattr(camera_frame, "current_image", None)
        if img is None:
            debugp("Routines", f"No camera frame to save at {path}")
            return None
        try:
            img.save(path)
            return path
        except Exception as e:
            debugp("Routines", f"Failed to save camera image {path}: {e}")
            return None
