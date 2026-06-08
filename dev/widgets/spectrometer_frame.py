from dev.debugHelp import debugp
from ..images.images import *
from .notification import *

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from datetime import *
from tkinter import Canvas, StringVar, simpledialog
import threading
import numpy
import time
import csv
import os
import queue
import shutil
import tempfile
from copy import deepcopy
from CTkToolTip import *


class SpectrometerFrame(CTkFrame):
    """Class for creating a frame to control a spectrometer"""

    def __init__(self, master, spectrometers):
        """Create a frame in the main window.
        Users can easily control the spectrometer

        Parameters
        ------------
        master : `CTk`
            Main window
        spectrometer : `MySpectrometer`
            Object containing all information about a spectrometer
        """
        super().__init__(master)
        
        self.is_disabled = False
        self.unavailable_message_label = None
        
        
        self.file_system = master.file_system
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0, minsize=92)
        self.grid_rowconfigure(5, weight=1)
        self.grid_rowconfigure(6, weight=0)
        self.grid_propagate(False)
        
        self.spectrometer_count = len(spectrometers) if spectrometers else 0
        self.has_raman_spectrograph = any(getattr(spec, "supports_image_view", False) for spec in (spectrometers or []))

        if not spectrometers:
            self.label = CTkLabel(self, text="No spectrometer", font=("Arial", 25))
            self.label.grid(row=3, column=1, padx=5, pady=5)
        else:
            self.spectrometers = spectrometers
            self.init()


    def init(self):
        """Creating the initial spectrometer display
        """
        self.disconnected_label = CTkLabel(self, text="Disconnected", font=("Arial", 25))
        self.disconnected_label.grid(row=5, column=1, padx=5, pady=5)
        self.disconnected_button = CTkButton(self, text="", width=30, height=40,  image=img_retry, fg_color="transparent", command=self.reconnection)
        self.disconnected_button.grid(row=5, column=1, padx=5, pady=(75, 0))

        self.popup = None
        self.backup_name = None
        self.stop_after_saves = False
        self.reflectance_mode = False
        self.save_frequency = 1
        self.backups_counts_memorie = 10
        self.wavelengthsList, self.intensitiesList = [], []
        self.light_reference, self.dark_reference = [], []
        
        self.last_saved_light_reference = []
        self.last_saved_dark_reference = []
        self.last_saved_light_reference_wavelengths = []
        self.last_saved_light_reference_intensities = []
        self.last_saved_dark_reference_wavelengths = []
        self.last_saved_dark_reference_intensities = []
        
        self.light_ref_acquisition_time, self.dark_ref_acquisition_time = [], []
        self.connected_spectrometers = []
        self.graph_updating = False
        self._user_paused_live = False
        self.signal_recording_active = False
        # When an automated routine (e.g. Z-stack) owns the spectrum plot,
        # this freezes the live-view loop and prevents the temperature
        # watchdog from auto-restarting acquisition behind the routine's back.
        self.routine_active = False
        self._routine_trace_count = 0
        self.signal_recording_thread = None
        self.signal_recording_queue = queue.Queue()
        self.signal_recording_result = None
        self.signal_recording_error = None
        self.signal_recording_spectrometer = None
        self.signal_recording_resume_live = False
        self.signal_recorded_frames = []
        self.signal_save_popup = None
        self.signal_recording_label = None
        self.light_reference_wavelengths, self.light_reference_intensities = [], []
        self.dark_reference_wavelengths, self.dark_reference_intensities = [], []
     
        self.split = 1
        self.image_view_enabled = False
        self.figure_layout = None
        self.view_button = None
        self.detector_plot = None
        self.detector_counts_plot = None
        self.detector_row_profile_plot = None
        self.device_controls_frame = None
        self.read_mode_sidebar = None
        self.read_mode_buttons = {}
        self.kymera_control_widgets = []
        self.kymera_controls_enabled = True
        self.kymera_refreshing_controls = False
        self._last_shutter_render_state = None
        self.is_dragging_wavelength_bar = False
        self.wavelength_band_canvas = None
        self.kymera_exposure_slider = None
        self.kymera_exposure_var = None
        self.kymera_exposure_label = None
        self.kymera_cycle_time_var = None
        self.kymera_cycle_time_entry = None
        self.kymera_slit_var = None
        self.kymera_slit_entry = None
        self.kymera_shutter_icon = None
        self.kymera_shutter_mode_label = None
        self.kymera_shutter_ext_button = None
        self.kymera_shutter_toggle_button = None
        self.kymera_grating_icon = None
        self.kymera_grating_title_label = None
        self.kymera_grating_info_label = None
        self.kymera_focus_var = None
        self.kymera_focus_entry = None
        self.kymera_iris_slider = None
        self.kymera_iris_var = None
        self.kymera_iris_entry = None
        
        self.temperature_display = None
        
        self.update_temperature()
    
    def connect(self, device):
        """Try connecting the spectrometers. 
        If the connection is established, the frame is updated to access the associated functionality.
        In addition, if the device enable parameter is activated, the device is automatically started

        Returns
        ------------
        connect : `bool`
            Wether the spectrometer is connected
        """
        
        debugp("spec", "Connecting spectrometer : " + str(device))
        
        if not device.connected and device.connect() == True:
            self.connected_spectrometers.append(device)
            self.wavelengthsList.append([])
            self.intensitiesList.append([])
            self.light_ref_acquisition_time.append([])
            self.dark_ref_acquisition_time.append([])
            self.light_reference_wavelengths.append([])
            self.dark_reference_wavelengths.append([])
            self.light_reference_intensities.append([])
            self.dark_reference_intensities.append([])
            self.last_saved_light_reference_wavelengths.append(numpy.array([]))
            self.last_saved_dark_reference_wavelengths.append(numpy.array([]))
            self.last_saved_light_reference_intensities.append(numpy.array([]))
            self.last_saved_dark_reference_intensities.append(numpy.array([]))
            debugp("spec", "Connected spectrometer successfully : " + str(device))        
                       
        connected_spectrometers_count = len(self.connected_spectrometers)
        
        if connected_spectrometers_count > 0:
            debugp("spec", "Updating Spectrometer Display")

            self.disconnected_label.grid_forget()
            self.disconnected_button.grid_forget()
   
            for spec in self.spectrometers:
                spec.set_integration_time(spec.integration_time)
            self.figure = Figure(figsize=(6, 6))
            # A fresh Figure has no axes, so invalidate the layout cache to force
            # ensure_figure_layout to add the subplot(s) instead of early-returning
            # because the previous Figure was already configured for this layout.
            self.figure_layout = None
            self.ensure_figure_layout(self.supports_image_view(device) and self.image_view_enabled)
        
            self.canvas = FigureCanvasTkAgg(self.figure, master=self)
            self.canvas.get_tk_widget().grid(row=0, column=1, sticky="nsew", rowspan=6)
   
            self.temperature_display = CTkLabel(self, text="∅°c", width=40, height=40, fg_color="transparent")
            self.temperature_display.grid(row=0, column=2, padx=5, pady=5, sticky="ne")
            CTkToolTip(self.temperature_display, delay=0.2, message="Active spectrometer temperature") 
            
            
            self.fullscreen_button = CTkButton(self, text="", width=40, height=40, image=img_full_screen, fg_color="transparent", command=self.extend)
            self.fullscreen_button.grid(row=1, column=2, padx=5, pady=5, sticky="ne")
            CTkToolTip(self.fullscreen_button, delay=0.2, message="Full Screen") 

            self.import_button = CTkButton(self, text="", width=40, height=40, image=img_plus, fg_color="transparent", command=self.import_chart)
            self.import_button.grid(row=2, column=2, padx=5, pady=5, sticky="ne")
            CTkToolTip(self.import_button, delay=0.2, message="Import Chart") 

            self.light_reference_button = CTkButton(self, text="", width=40, height=40, image=img_bulb_on, fg_color="transparent", command=self.set_light_reference)
            self.light_reference_button.grid(row=3, column=2, padx=5, pady=5, sticky="ne")
            CTkToolTip(self.light_reference_button, delay=0.2, message="Set Light Reference") 

            self.dark_reference_button = CTkButton(self, text="", width=40, height=40, image=img_bulb_off, fg_color="transparent", command=self.set_dark_reference)
            self.dark_reference_button.grid(row=4, column=2, padx=5, pady=5, sticky="ne")
            CTkToolTip(self.dark_reference_button, delay=0.2, message="Set Dark Reference") 

            self.pause_button = CTkButton(self, text="", width=40, height=40, image=img_pause, fg_color="transparent", command=self.stop_spectrometer)
            self.pause_button.grid(row=0, column=0, padx=5, pady=5, sticky="nw")
            CTkToolTip(self.pause_button, delay=0.2, message="Pause") 

            self.play_button = CTkButton(self, text="", width=40, height=40,  image=img_play, fg_color="transparent", command=self.start_spectrometer)
            self.play_button.grid(row=0, column=0, padx=5, pady=5, sticky="nw")
            CTkToolTip(self.play_button, delay=0.2, message="Play") 

            self.save_button = CTkButton(self, text="", width=40, height=40, image=img_save, fg_color="transparent", command=self.take_signal)
            self.save_button.grid(row=1, column=0, padx=5, pady=5, sticky="nw")
            CTkToolTip(self.save_button, delay=0.2, message="Take Signal") 

            self.adv_save_button = CTkButton(self, text="", width=40, height=40, image=img_advanced_save, fg_color="transparent", command=self.advanced_save_popup)
            self.adv_save_button.grid(row=5, column=0, padx=5, pady=5, sticky="nw")
            CTkToolTip(self.adv_save_button, delay=0.2, message="Advanced Save") 

            self.reflectance_data_button = CTkButton(self, text="%", font=("Arial", 25), width=40, height=40, fg_color="transparent", command=self.toggle_mode)
            self.reflectance_data_button.grid(row=2, column=0, padx=5, pady=5, sticky="nw")
            CTkToolTip(self.reflectance_data_button, delay=0.2, message="Reflectance Data") 
                        
            self.raw_data_button = CTkButton(self, text="#", font=("Arial", 25), width=40, height=40, fg_color="transparent", command=self.toggle_mode)
            self.raw_data_button.grid(row=2, column=0, padx=5, pady=5, sticky="nw")
            CTkToolTip(self.raw_data_button, delay=0.2, message="Raw Data") 

            self.new_experiment_button = CTkButton(self, text="", image=img_new_experiment, width=40, height=40, fg_color="transparent", command=self.add_experiment)
            self.new_experiment_button.grid(row=3, column=0, padx=5, pady=5, sticky="nw")
            CTkToolTip(self.new_experiment_button, delay=0.2, message="New Experiment")

            self.signal_recording_label = CTkLabel(self, text="", width=86, height=28, fg_color="#1f6aa5", corner_radius=4)
            self.signal_recording_label.grid(row=5, column=2, padx=5, pady=5, sticky="se")
            self.signal_recording_label.grid_remove()

            if self.is_raman_spectrometer(device):
                self.light_reference_button.grid_remove()
                self.dark_reference_button.grid_remove()
                self.reflectance_data_button.grid_remove()
                self.raw_data_button.grid_remove()
                self.ensure_read_mode_sidebar(device)
                self.ensure_device_controls_placeholder(device)
                self.refresh_kymera_controls(device)

            # Display the view button for multi-spectrometer Ocean Optics setups
            # or for Kymera spectrum/image switching.
            if connected_spectrometers_count > 1 or self.supports_image_view(device):
                initial_image = img_split_right if self.image_view_enabled else img_split_left
                self.view_button = CTkButton(self, text="", width=40, height=40, image=initial_image, fg_color="transparent", command=self.toggle_split_screen)
                self.view_button.grid(row=4, column=0, padx=5, pady=5, sticky="nw")
                tooltip = "Switch View" if self.supports_image_view(device) else "Switch Spectrometer"
                CTkToolTip(self.view_button, delay=0.2, message=tooltip)
                
            self.start_spectrometer(device, user_initiated=False)    
                        
        return (connected_spectrometers_count > 0)


    def reconnection(self):
        """Try reconnecting the spectrometer via `setup frame` to update the display correctly
        """
        self.master.quick_setup_frame.reconnection(self.spectrometers[0])

    
    def disconnect(self, device):
        """Stops the current thread, disconnects the spectrometer cleanly, then updates the display
        """
         
        #Remove spectrometer from connected
        self.connected_spectrometers.remove(device)
        device.disconnect()

        self.split = 1
        
        if hasattr(self, 'view_button'):
            self.view_button.destroy()
        
        if(len(self.connected_spectrometers) == 0):
            self.figure.clf() 
            for widget in self.winfo_children():
                widget.destroy()
            self.init()
            self.on_closing()
            

    def is_live_ready_for_spectrometer(self, device=None):
        device = device or self.get_active_spectrometer()
        if not device or not hasattr(device, "get_temperature_state"):
            return True

        try:
            state, _temperature = device.get_temperature_state()
        except Exception:
            return True

        return state in ("reached", "unavailable")


    def start_spectrometer(self, device=None, user_initiated=True):
        """Starts thread for continuous spectrometer data extraction
        """
        target_device = device if device in self.connected_spectrometers else self.get_active_spectrometer()
        if self.supports_image_view(target_device) and not self.is_live_ready_for_spectrometer(target_device):
            self.play_button.lift()
            self.play_button.configure(state="disabled")
            self.pause_button.configure(state="disabled")
            return
        
        if device in self.connected_spectrometers:
            debugp("spec", "Starting spectrometer : " + str(device))
            device.start()
        else:
            for spec in self.connected_spectrometers:
                debugp("spec", "Starting spectrometer : " + str(spec))
                spec.start()
    
        self._user_paused_live = False
        self.pause_button.lift()
        self.update_graph(True)


    def stop_spectrometer(self, user_initiated=True):
        """Stops continuous extraction of spectrometer data without disconnecting the camera
        """
        if user_initiated:
            self._user_paused_live = True
            
        for spec in self.connected_spectrometers:
            debugp("spec", "Stopping spectrometer : " + str(spec))
            spec.stop()

        self.play_button.lift()


    def toggle_mode(self):
        """Switches between spectrometer data display modes. 
        The main mode is raw data display. However, if the ligth reference 
        and dark reference have been taken, it is possible to switch to reflectance/transmittance mode. 
        Otherwise, a notification is displayed to users.
        """
        if self.is_raman_spectrometer():
            return

        if self.reflectance_mode:
            self.reflectance_mode = False
            self.raw_data_button.lift()
        else:
            if not self.light_reference or not self.dark_reference:
                self.notification(f"To use reflectance or transmittance, you need both light and dark references", color="#8e0101")
                return
            self.reflectance_mode = True
            self.reflectance_data_button.lift()
            if self.light_ref_acquisition_time[self.split-1] != self.dark_ref_acquisition_time[self.split-1]:
                self.notification(f"Light reference acquisition time differs from dark", color="#e17e00")              
            if self.light_ref_acquisition_time[self.split-1] != self.connected_spectrometers[self.split-1].integration_time:
                self.notification(f"Light reference acquisition time differs from current", color="#e17e00")              
            if self.dark_ref_acquisition_time[self.split-1] != self.connected_spectrometers[self.split-1].integration_time:
                self.notification(f"Dark reference acquisition time differs from current", color="#e17e00")              


    def get_active_index(self):
        if not self.connected_spectrometers:
            return 0
        return 0 if len(self.connected_spectrometers) == 1 else max(self.split - 1, 0)


    def get_active_spectrometer(self):
        if self.connected_spectrometers:
            index = min(self.get_active_index(), len(self.connected_spectrometers) - 1)
            return self.connected_spectrometers[index]
        if getattr(self, "spectrometers", None):
            return self.spectrometers[0]
        return None


    def is_raman_spectrometer(self, spectrometer=None):
        device = spectrometer or self.get_active_spectrometer()
        return bool(device and callable(getattr(device, "format_chart_data", None)))


    def supports_image_view(self, spectrometer=None):
        device = spectrometer or self.get_active_spectrometer()
        return bool(device and getattr(device, "supports_image_view", False))


    def get_kymera_palette(self):
        dark_mode = getattr(self.master, "apparence_color_theme", "dark") == "dark"
        if dark_mode:
            return {
                "canvas": "#232323",
                "track": "#101010",
                "tick": "#cfcfcf",
                "label": "#e8e8e8",
                "selection": "#9e9e9e",
                "selection_outline": "#d0d0d0",
                "marker_fill": "#1f6aa5",
                "marker_outline": "#69a7db",
                "marker_text": "#f8fbff",
                "accent": "#4aa4ff",
                "muted": "#808080",
                "open": "#40c463",
                "closed": "#d15151",
            }

        return {
            "canvas": "#f5f5f5",
            "track": "#1b1b1b",
            "tick": "#444444",
            "label": "#222222",
            "selection": "#a7a7a7",
            "selection_outline": "#6a6a6a",
            "marker_fill": "#1f6aa5",
            "marker_outline": "#69a7db",
            "marker_text": "#ffffff",
            "accent": "#1f6aa5",
            "muted": "#888888",
            "open": "#2f9d44",
            "closed": "#b44545",
        }


    def register_kymera_control_widget(self, widget):
        self.kymera_control_widgets.append(widget)
        return widget


    def ensure_read_mode_sidebar(self, spectrometer=None):
        if self.read_mode_sidebar or not self.has_raman_spectrograph:
            return

        device = spectrometer or self.get_active_spectrometer()
        self.read_mode_sidebar = []

        descriptions = {
            "FVB": "Full Vertical Binning",
            "Image": "Image",
            "Multi-track": "Multi-track",
        }

        for row, mode in enumerate(device.get_read_mode_options(), start=3):
            button_wrapper = CTkFrame(self, width=28, height=24, fg_color="transparent")
            button_wrapper.grid(row=row, column=2, padx=(6, 8), pady=4, sticky="ne")
            button_wrapper.pack_propagate(False)

            button = Canvas(button_wrapper, width=28, height=24, highlightthickness=0, bd=0)
            button.pack(fill="both", expand=True)

            button_wrapper.bind("<Button-1>", lambda _event, selected_mode=mode: self.set_kymera_read_mode(selected_mode))
            button.bind("<Button-1>", lambda _event, selected_mode=mode: self.set_kymera_read_mode(selected_mode))
            tooltip = CTkToolTip(button_wrapper, delay=0.2, message=descriptions.get(mode, mode))
            button.bind("<Enter>", tooltip.on_enter, add="+")
            button.bind("<Motion>", tooltip.on_enter, add="+")
            button.bind("<B1-Motion>", tooltip.on_enter, add="+")
            button.bind("<Leave>", tooltip.on_leave, add="+")
            self.read_mode_buttons[mode] = button
            self.read_mode_sidebar.append(button_wrapper)

        self.render_kymera_read_mode_buttons(device)


    def ensure_device_controls_placeholder(self, spectrometer=None):
        if self.device_controls_frame or not self.has_raman_spectrograph:
            return

        device = spectrometer or self.get_active_spectrometer()
        self.device_controls_frame = CTkFrame(self, height=208)
        self.device_controls_frame.grid(row=6, column=0, columnspan=3, padx=(6, 8), pady=(0, 8), sticky="ew")
        self.device_controls_frame.grid_propagate(False)
        self.device_controls_frame.grid_columnconfigure(0, weight=1)

        control_row = CTkFrame(self.device_controls_frame, fg_color="transparent")
        control_row.pack(fill="both", expand=True, padx=6, pady=6)
        control_row.grid_columnconfigure(0, weight=44)
        control_row.grid_columnconfigure(1, weight=12)
        control_row.grid_columnconfigure(2, weight=12)
        control_row.grid_columnconfigure(3, weight=12)
        control_row.grid_columnconfigure(4, weight=12)
        control_row.grid_columnconfigure(5, weight=8)

        left_panel = CTkFrame(control_row)
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_panel.grid_columnconfigure(0, weight=1)

        wavelength_header = CTkFrame(left_panel, fg_color="transparent")
        wavelength_header.grid(row=0, column=0, padx=8, pady=(6, 2), sticky="ew")
        wavelength_header.grid_columnconfigure(0, weight=1)
        CTkLabel(wavelength_header, text="Wavelength", font=("Arial", 12, "bold")).grid(row=0, column=0, sticky="w")

        self.kymera_axis_mode_var = StringVar(value="off")  # "off" = Raman shift, "on" = nm
        self.kymera_axis_mode_switch = CTkCheckBox(
            wavelength_header,
            text="nm axis",
            border_width=2,
            border_color="#1F6AA5",
            variable=self.kymera_axis_mode_var,
            onvalue="on",
            offvalue="off",
            command=self.on_kymera_axis_mode_toggle,
            font=("Arial", 10),
        )
        self.kymera_axis_mode_switch.grid(row=0, column=1, padx=(8, 0), sticky="e")

        # Single row of marker boxes at the top of the canvas, leader lines down
        # to the track and ticks below. 122 px is enough for the full layout.
        self.wavelength_band_canvas = Canvas(left_panel, height=122, highlightthickness=0, bd=0)
        self.wavelength_band_canvas.grid(row=1, column=0, padx=8, pady=(0, 4), sticky="ew")
        self.wavelength_band_canvas.bind("<Button-1>", self.on_kymera_wavelength_press)
        self.wavelength_band_canvas.bind("<B1-Motion>", self.on_kymera_wavelength_drag)
        self.wavelength_band_canvas.bind("<ButtonRelease-1>", self.on_kymera_wavelength_release)
        self.wavelength_band_canvas.bind("<Configure>", lambda _event: self.render_kymera_wavelength_panel())

        CTkLabel(left_panel, text="Exposure", font=("Arial", 12, "bold")).grid(row=2, column=0, padx=8, pady=(0, 2), sticky="w")
        exposure_frame = CTkFrame(left_panel, fg_color="transparent")
        exposure_frame.grid(row=3, column=0, padx=8, pady=(0, 6), sticky="ew")
        exposure_frame.grid_columnconfigure(0, weight=1)

        self.kymera_exposure_slider = self.register_kymera_control_widget(
            CTkSlider(exposure_frame, from_=0.001, to=0.100, command=self.on_kymera_exposure_slider)
        )
        self.kymera_exposure_slider.grid(row=0, column=0, columnspan=8, padx=(0, 4), pady=(0, 5), sticky="ew")

        self.kymera_exposure_var = StringVar(value="0.00000")
        self.kymera_exposure_label = CTkLabel(exposure_frame, text="Exposure", font=("Arial", 10))
        self.kymera_exposure_label.grid(row=1, column=0, padx=(0, 4), sticky="w")
        self.kymera_exposure_entry = self.register_kymera_control_widget(CTkEntry(exposure_frame, textvariable=self.kymera_exposure_var, width=64))
        self.kymera_exposure_entry.grid(row=1, column=1, padx=(0, 4), sticky="w")
        CTkLabel(exposure_frame, text="s", font=("Arial", 10)).grid(row=1, column=2, padx=(0, 6), sticky="w")
        self.register_kymera_control_widget(CTkButton(exposure_frame, text="Set", width=34, height=24, font=("Arial", 10), command=self.set_kymera_exposure_from_entry)).grid(row=1, column=3, padx=(0, 10), sticky="w")
        CTkLabel(exposure_frame, text="Cycle", font=("Arial", 10)).grid(row=1, column=4, padx=(0, 4), sticky="w")
        self.kymera_cycle_time_var = StringVar(value="0.00000")
        self.kymera_cycle_time_entry = self.register_kymera_control_widget(
            CTkEntry(exposure_frame, textvariable=self.kymera_cycle_time_var, width=72)
        )
        self.kymera_cycle_time_entry.grid(row=1, column=5, padx=(0, 4), sticky="w")
        self.kymera_cycle_time_entry.bind(
            "<Return>", lambda _event: self.set_kymera_cycle_time_from_entry()
        )
        CTkLabel(exposure_frame, text="s", font=("Arial", 10)).grid(row=1, column=6, padx=(0, 4), sticky="w")
        self.register_kymera_control_widget(
            CTkButton(
                exposure_frame,
                text="Set",
                width=34,
                height=24,
                font=("Arial", 10),
                command=self.set_kymera_cycle_time_from_entry,
            )
        ).grid(row=1, column=7, padx=(0, 6), sticky="w")

        slit_panel = self.build_kymera_control_card(control_row, "Side Input Slit", 1)
        self.build_kymera_slit_panel(slit_panel)

        shutter_panel = self.build_kymera_control_card(control_row, "Shutter", 2)
        self.build_kymera_shutter_panel(shutter_panel)

        grating_panel = self.build_kymera_control_card(control_row, "Grating", 3)
        self.build_kymera_grating_panel(grating_panel)

        focus_panel = self.build_kymera_control_card(control_row, "Focus Mirror", 4)
        self.build_kymera_focus_panel(focus_panel)

        iris_panel = self.build_kymera_control_card(control_row, "Side Input Iris", 5)
        self.build_kymera_iris_panel(iris_panel)

        self.refresh_kymera_controls(device)


    def build_kymera_control_card(self, parent, title, column):
        card = CTkFrame(parent)
        card.grid(row=0, column=column, sticky="nsew", padx=4)
        card.grid_columnconfigure(0, weight=1)
        CTkLabel(card, text=title, font=("Arial", 11, "bold"), justify="center", wraplength=84).grid(row=0, column=0, padx=5, pady=(6, 3), sticky="ew")
        return card


    def build_kymera_slit_panel(self, parent):
        canvas = Canvas(parent, width=78, height=58, highlightthickness=0, bd=0)
        canvas.grid(row=1, column=0, padx=8, pady=(0, 4), sticky="n")
        self.draw_kymera_slit_icon(canvas)

        self.kymera_slit_var = StringVar(value="10.0")
        self.kymera_slit_entry = self.register_kymera_control_widget(CTkEntry(parent, textvariable=self.kymera_slit_var, width=62))
        self.kymera_slit_entry.grid(row=2, column=0, padx=8, pady=(0, 4))
        self.register_kymera_control_widget(CTkButton(parent, text="Set", width=36, height=24, font=("Arial", 10), command=self.set_kymera_side_input_slit)).grid(row=3, column=0, padx=8, pady=(0, 6))


    def build_kymera_shutter_panel(self, parent):
        self.kymera_shutter_icon = Canvas(parent, width=78, height=58, highlightthickness=0, bd=0)
        self.kymera_shutter_icon.grid(row=1, column=0, padx=8, pady=(0, 4), sticky="n")
        self.kymera_shutter_icon.bind("<Button-1>", self.on_kymera_shutter_icon_click)

        button_frame = CTkFrame(parent, fg_color="transparent")
        button_frame.grid(row=2, column=0, padx=8, pady=(0, 4), sticky="ew")
        button_frame.grid_columnconfigure((0, 1), weight=1)

        self.kymera_shutter_ext_button = self.register_kymera_control_widget(
            CTkButton(button_frame, text="EXT", width=32, height=24, font=("Arial", 9), command=self.toggle_kymera_shutter_external)
        )
        self.kymera_shutter_ext_button.grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self.kymera_shutter_toggle_button = self.register_kymera_control_widget(
            CTkButton(button_frame, text="Open", width=44, height=24, font=("Arial", 9), command=self.toggle_kymera_shutter_state)
        )
        self.kymera_shutter_toggle_button.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        self.kymera_shutter_mode_label = CTkLabel(parent, text="AUTO", justify="center", wraplength=76, font=("Arial", 9))
        self.kymera_shutter_mode_label.grid(row=3, column=0, padx=6, pady=(0, 6))


    def build_kymera_grating_panel(self, parent):
        self.kymera_grating_icon = Canvas(parent, width=78, height=58, highlightthickness=0, bd=0)
        self.kymera_grating_icon.grid(row=1, column=0, padx=8, pady=(0, 4), sticky="n")
        self.kymera_grating_icon.bind("<Button-1>", lambda _event: self.cycle_kymera_grating())

        self.kymera_grating_title_label = CTkLabel(parent, text="Grating: 1", justify="left", font=("Arial", 10, "bold"), wraplength=78)
        self.kymera_grating_title_label.grid(row=2, column=0, padx=8, sticky="w")
        self.kymera_grating_info_label = CTkLabel(parent, text="85 l/mm\nBlaze: 1350nm", justify="left", font=("Arial", 9), wraplength=78)
        self.kymera_grating_info_label.grid(row=3, column=0, padx=8, pady=(0, 4), sticky="w")
        self.register_kymera_control_widget(CTkButton(parent, text="Turret", width=56, height=24, font=("Arial", 10), command=self.cycle_kymera_grating)).grid(row=4, column=0, padx=8, pady=(0, 6))


    def build_kymera_focus_panel(self, parent):
        canvas = Canvas(parent, width=78, height=58, highlightthickness=0, bd=0)
        canvas.grid(row=1, column=0, padx=8, pady=(0, 4), sticky="n")
        self.draw_kymera_focus_icon(canvas)

        self.kymera_focus_var = StringVar(value="237")
        focus_frame = CTkFrame(parent, fg_color="transparent")
        focus_frame.grid(row=2, column=0, padx=8, pady=(0, 4), sticky="ew")
        focus_frame.grid_columnconfigure(0, weight=1)

        self.kymera_focus_entry = self.register_kymera_control_widget(CTkEntry(focus_frame, textvariable=self.kymera_focus_var, width=52))
        self.kymera_focus_entry.grid(row=0, column=0, padx=(0, 4), sticky="ew")
        self.register_kymera_control_widget(CTkButton(focus_frame, text="Set", width=34, height=24, font=("Arial", 10), command=self.set_kymera_focus_mirror_steps)).grid(row=0, column=1, sticky="e")
        self.register_kymera_control_widget(CTkButton(parent, text="Auto", width=52, height=24, font=("Arial", 10), command=self.autofocus_kymera_focus_mirror)).grid(row=3, column=0, padx=8, pady=(0, 6))


    def build_kymera_iris_panel(self, parent):
        canvas = Canvas(parent, width=78, height=46, highlightthickness=0, bd=0)
        canvas.grid(row=1, column=0, padx=8, pady=(0, 2), sticky="n")
        self.draw_kymera_iris_icon(canvas)

        label_frame = CTkFrame(parent, fg_color="transparent")
        label_frame.grid(row=2, column=0, padx=6, pady=(0, 2), sticky="ew")
        label_frame.grid_columnconfigure((0, 1), weight=1)
        CTkLabel(label_frame, text="Res", text_color="gray60", font=("Arial", 9)).grid(row=0, column=0, sticky="w")
        CTkLabel(label_frame, text="Thru", text_color="gray60", font=("Arial", 9)).grid(row=0, column=1, sticky="e")

        self.kymera_iris_slider = self.register_kymera_control_widget(CTkSlider(parent, from_=0, to=100, command=self.on_kymera_iris_slider))
        self.kymera_iris_slider.grid(row=3, column=0, padx=6, pady=(0, 4), sticky="ew")

        entry_frame = CTkFrame(parent, fg_color="transparent")
        entry_frame.grid(row=4, column=0, padx=6, pady=(0, 8))
        self.kymera_iris_var = StringVar(value="60")
        self.kymera_iris_entry = self.register_kymera_control_widget(CTkEntry(entry_frame, textvariable=self.kymera_iris_var, width=40))
        self.kymera_iris_entry.grid(row=0, column=0, padx=(0, 4))
        self.register_kymera_control_widget(CTkButton(entry_frame, text="Set", width=34, height=24, font=("Arial", 10), command=self.set_kymera_side_input_iris)).grid(row=0, column=1)


    def refresh_kymera_controls(self, spectrometer=None):
        device = spectrometer or self.get_active_spectrometer()
        if not self.supports_image_view(device):
            return

        self.render_kymera_read_mode_buttons(device)
        self.render_kymera_wavelength_panel(device)
        self.render_kymera_exposure_controls(device)
        self.render_kymera_axis_mode_switch(device)
        self.render_kymera_slit_controls(device)
        self.render_kymera_shutter_controls(device)
        self.render_kymera_grating_controls(device)
        self.render_kymera_focus_controls(device)
        self.render_kymera_iris_controls(device)


    def render_kymera_read_mode_buttons(self, spectrometer=None):
        device = spectrometer or self.get_active_spectrometer()
        if not device:
            return

        for mode, button in self.read_mode_buttons.items():
            is_selected = mode == device.selected_read_mode
            if isinstance(button, Canvas):
                self.draw_kymera_read_mode_icon(button, mode, is_selected)
                button.configure(cursor=("hand2" if self.kymera_controls_enabled else "arrow"))
            else:
                button.configure(
                    fg_color="#1F6AA5" if is_selected else "transparent",
                    hover_color="#1A4E7A" if is_selected else "#163A5D",
                    text_color=("white" if is_selected else ["gray14", "gray90"]),
                )


    def draw_kymera_read_mode_icon(self, canvas, mode, is_selected):
        palette = self.get_kymera_palette()
        active_fill = palette["accent"] if is_selected else "#4a4a4a"
        outline = palette["marker_outline"] if is_selected else palette["muted"]
        icon_fill = "#f3f7fb" if is_selected else "#c7d0d7"

        canvas.configure(bg=palette["canvas"])
        canvas.delete("all")
        canvas.create_rectangle(2, 2, 26, 22, outline=outline, width=1, fill=active_fill)

        if mode == "FVB":
            canvas.create_rectangle(7, 6, 21, 18, outline=icon_fill, width=1)
            canvas.create_line(10, 6, 10, 18, fill=icon_fill, width=1)
            canvas.create_line(14, 6, 14, 18, fill=icon_fill, width=1)
            canvas.create_line(18, 6, 18, 18, fill=icon_fill, width=1)
        elif mode == "Image":
            canvas.create_rectangle(6, 6, 22, 18, outline=icon_fill, width=1)
            canvas.create_oval(8, 8, 11, 11, fill=icon_fill, outline=icon_fill)
            canvas.create_line(7, 17, 12, 12, 16, 15, 21, 9, fill=icon_fill, width=1)
        else:
            canvas.create_rectangle(6, 6, 22, 18, outline=icon_fill, width=1)
            canvas.create_line(8, 9, 20, 9, fill=icon_fill, width=1)
            canvas.create_line(8, 12, 20, 12, fill=icon_fill, width=1)
            canvas.create_line(8, 15, 20, 15, fill=icon_fill, width=1)


    def render_kymera_exposure_controls(self, spectrometer):
        if not self.kymera_exposure_slider or not self.kymera_exposure_var:
            return

        self.kymera_refreshing_controls = True
        try:
            exposure_seconds = spectrometer.get_exposure_seconds()
            self.kymera_exposure_slider.set(exposure_seconds)
            self.kymera_exposure_var.set(f"{exposure_seconds:.5f}")
            if self.kymera_cycle_time_var is not None:
                self.kymera_cycle_time_var.set(f"{spectrometer.get_cycle_time_seconds():.5f}")
        finally:
            self.kymera_refreshing_controls = False

    def render_kymera_axis_mode_switch(self, spectrometer):
        if not getattr(self, "kymera_axis_mode_switch", None):
            return
        mode = getattr(spectrometer, "axis_mode", "raman")
        desired_state = "on" if mode == "wavelength" else "off"
        if self.kymera_axis_mode_var.get() != desired_state:
            self.kymera_refreshing_controls = True
            try:
                self.kymera_axis_mode_var.set(desired_state)
            finally:
                self.kymera_refreshing_controls = False


    def render_kymera_slit_controls(self, spectrometer):
        if self.kymera_slit_var:
            self.kymera_slit_var.set(f"{spectrometer.side_input_slit_um:.1f}")


    def render_kymera_shutter_controls(self, spectrometer):
        palette = self.get_kymera_palette()
        if self.kymera_shutter_ext_button:
            self.kymera_shutter_ext_button.configure(
                fg_color="#1F6AA5" if spectrometer.shutter_external_enabled else "transparent",
                border_width=1,
                border_color="#1F6AA5",
            )

        if self.kymera_shutter_toggle_button:
            self.kymera_shutter_toggle_button.configure(text=("Close" if spectrometer.shutter_is_open else "Open"))

        if self.kymera_shutter_mode_label:
            mode_text = f"EXT: {spectrometer.get_shutter_mode()}" if spectrometer.shutter_external_enabled else "Manual"
            self.kymera_shutter_mode_label.configure(text=mode_text)

        if self.kymera_shutter_icon:
            self.kymera_shutter_icon.configure(bg=palette["canvas"], cursor=("hand2" if spectrometer.shutter_external_enabled and self.kymera_controls_enabled else "arrow"))
            self.render_kymera_shutter_icon(spectrometer)


    def render_kymera_grating_controls(self, spectrometer):
        grating = spectrometer.get_active_grating()
        if self.kymera_grating_title_label:
            self.kymera_grating_title_label.configure(text=f"Grating: {grating['index']}")
        if self.kymera_grating_info_label:
            self.kymera_grating_info_label.configure(text=f"{grating['lines_per_mm']} l/mm\nBlaze: {grating['blaze']}")
        if self.kymera_grating_icon:
            self.kymera_grating_icon.configure(bg=self.get_kymera_palette()["canvas"], cursor=("hand2" if self.kymera_controls_enabled else "arrow"))
            self.render_kymera_grating_icon(spectrometer)


    def render_kymera_focus_controls(self, spectrometer):
        if self.kymera_focus_var:
            self.kymera_focus_var.set(str(spectrometer.focus_mirror_steps))


    def render_kymera_iris_controls(self, spectrometer):
        if self.kymera_iris_slider:
            self.kymera_refreshing_controls = True
            try:
                self.kymera_iris_slider.set(spectrometer.side_input_iris_steps)
                if self.kymera_iris_var:
                    self.kymera_iris_var.set(str(spectrometer.side_input_iris_steps))
            finally:
                self.kymera_refreshing_controls = False


    def render_kymera_wavelength_panel(self, spectrometer=None):
        device = spectrometer or self.get_active_spectrometer()
        if not self.wavelength_band_canvas or not device:
            return

        palette = self.get_kymera_palette()
        canvas = self.wavelength_band_canvas
        canvas.configure(bg=palette["canvas"])
        canvas.delete("all")

        width = max(canvas.winfo_width(), 560)
        left_margin = 20
        right_margin = width - 20
        track_top = 92
        track_bottom = 104
        track_y = (track_top + track_bottom) / 2

        display_min, display_max = device.wavelength_display_range_nm
        min_wave, center_wave, max_wave = device.get_wavelength_window()

        canvas.create_line(left_margin, track_y, right_margin, track_y, fill=palette["track"], width=8, capstyle="round")

        visible_colors = [
            (400.0, "#6a0dad"),
            (460.0, "#3554ff"),
            (520.0, "#1ac95d"),
            (580.0, "#ffde33"),
            (640.0, "#ff7f24"),
            (700.0, "#e53b2c"),
        ]
        for start_value, color in visible_colors:
            end_value = min(start_value + 60.0, 700.0)
            x1 = self.kymera_wavelength_to_x(start_value, left_margin, right_margin, display_min, display_max)
            x2 = self.kymera_wavelength_to_x(end_value, left_margin, right_margin, display_min, display_max)
            canvas.create_rectangle(x1, track_top + 4, x2, track_bottom - 4, fill=color, outline=color)

        selection_x1 = self.kymera_wavelength_to_x(min_wave, left_margin, right_margin, display_min, display_max)
        selection_x2 = self.kymera_wavelength_to_x(max_wave, left_margin, right_margin, display_min, display_max)
        center_x = self.kymera_wavelength_to_x(center_wave, left_margin, right_margin, display_min, display_max)

        canvas.create_rectangle(
            selection_x1,
            track_top - 10,
            selection_x2,
            track_top,
            fill=palette["selection"],
            outline=palette["selection_outline"],
            width=1,
            tags=("wavelength_selection",),
        )
        canvas.create_polygon(
            center_x,
            track_top,
            center_x - 6,
            track_top - 12,
            center_x + 6,
            track_top - 12,
            fill=palette["selection_outline"],
            outline=palette["selection_outline"],
            tags=("wavelength_selection",),
        )

        tick_step = self._pick_tick_step(display_min, display_max)
        first_tick = int((display_min // tick_step)) * int(tick_step) if tick_step >= 1 else display_min
        tick = first_tick
        while tick <= display_max + 1e-6:
            if tick >= display_min:
                tick_x = self.kymera_wavelength_to_x(tick, left_margin, right_margin, display_min, display_max)
                canvas.create_line(tick_x, track_bottom + 1, tick_x, track_bottom + 8, fill=palette["tick"], width=1)
                canvas.create_text(tick_x, track_bottom + 18, text=f"{tick:g}", fill=palette["label"], font=("Arial", 9))
            tick += tick_step

        # Fixed-slot layout: minimum always sits in the top-left corner of the canvas,
        # centre in the top-middle, and maximum in the top-right. Each box has a leader
        # line down to its actual position on the track, so the three label boxes never
        # overlap each other and stay in predictable locations across all gratings.
        box_half_width = 28
        row_height = 22
        row_top = 4

        min_box_x = left_margin + box_half_width + 6
        max_box_x = right_margin - box_half_width - 6
        center_box_x = (left_margin + right_margin) / 2

        marker_specs = [
            ("minimum", min_box_x, selection_x1, f"{min_wave:.2f}"),
            ("center", center_box_x, center_x, f"{center_wave:.2f}"),
            ("maximum", max_box_x, selection_x2, f"{max_wave:.2f}"),
        ]

        for name, box_x, marker_x, text in marker_specs:
            self.draw_kymera_wavelength_marker(
                canvas,
                box_x,
                text,
                name,
                palette,
                left_margin,
                right_margin,
                row_top,
                row_height,
                box_half_width,
                track_y=track_top,
                marker_x=marker_x,
            )

    @staticmethod
    def _pick_tick_step(display_min, display_max):
        span = max(float(display_max) - float(display_min), 1.0)
        for candidate in (10, 20, 50, 100, 200, 500, 1000):
            if span / candidate <= 12:
                return float(candidate)
        return float(int(span / 8) + 1)


    def draw_kymera_wavelength_marker(self, canvas, center_x, text, marker_name, palette, left_margin, right_margin, top=6, height=22, box_half_width=22, track_y=None, marker_x=None):
        x1 = max(center_x - box_half_width, left_margin)
        x2 = min(center_x + box_half_width, right_margin)
        if x2 - x1 < box_half_width * 2:
            if x1 == left_margin:
                x2 = x1 + box_half_width * 2
            else:
                x1 = x2 - box_half_width * 2

        bottom = top + height

        # Leader line from the bottom-centre of the box down to the actual marker
        # position on the track so the user can match each box to its position.
        # ``marker_x`` is the position on the track; if not supplied we point at
        # the box's own x (legacy behaviour).
        leader_x_target = float(marker_x) if marker_x is not None else float(center_x)
        if track_y is not None and track_y > bottom:
            box_bottom_centre_x = (x1 + x2) / 2.0
            canvas.create_line(
                box_bottom_centre_x,
                bottom,
                leader_x_target,
                track_y,
                fill=palette["marker_outline"],
                width=1,
                tags=("wavelength_marker", f"wavelength_marker:{marker_name}"),
            )

        canvas.create_rectangle(
            x1,
            top,
            x2,
            bottom,
            fill=palette["marker_fill"],
            outline=palette["marker_outline"],
            width=1,
            tags=("wavelength_marker", f"wavelength_marker:{marker_name}"),
        )
        canvas.create_text(
            (x1 + x2) / 2,
            top + height / 2,
            text=text,
            fill=palette["marker_text"],
            font=("Arial", 9, "bold"),
            tags=("wavelength_marker", f"wavelength_marker:{marker_name}"),
        )


    def kymera_wavelength_to_x(self, wavelength_nm, left_margin, right_margin, display_min, display_max):
        scale = (float(wavelength_nm) - display_min) / (display_max - display_min)
        scale = min(max(scale, 0.0), 1.0)
        return left_margin + scale * (right_margin - left_margin)


    def canvas_x_to_kymera_wavelength(self, x_position):
        device = self.get_active_spectrometer()
        if not device or not self.wavelength_band_canvas:
            return None

        display_min, display_max = device.wavelength_display_range_nm
        width = max(self.wavelength_band_canvas.winfo_width(), 500)
        left_margin = 20
        right_margin = width - 20
        if right_margin <= left_margin:
            return None

        scale = (x_position - left_margin) / (right_margin - left_margin)
        scale = min(max(scale, 0.0), 1.0)
        return display_min + scale * (display_max - display_min)


    def on_kymera_wavelength_press(self, event):
        if not self.kymera_controls_enabled or not self.supports_image_view():
            return

        tags = self.wavelength_band_canvas.gettags("current")
        marker_tag = next((tag for tag in tags if tag.startswith("wavelength_marker:")), None)
        if marker_tag:
            self.prompt_kymera_wavelength_marker(marker_tag.split(":", 1)[1])
            return

        self.is_dragging_wavelength_bar = True
        target = self.canvas_x_to_kymera_wavelength(event.x)
        if target is not None:
            self.get_active_spectrometer().set_center_wavelength(target)
            self.render_kymera_wavelength_panel()


    def on_kymera_wavelength_drag(self, event):
        if not self.is_dragging_wavelength_bar or not self.kymera_controls_enabled:
            return

        target = self.canvas_x_to_kymera_wavelength(event.x)
        if target is not None:
            self.get_active_spectrometer().set_center_wavelength(target)
            self.render_kymera_wavelength_panel()


    def on_kymera_wavelength_release(self, _event):
        self.is_dragging_wavelength_bar = False


    def prompt_kymera_wavelength_marker(self, marker_name):
        device = self.get_active_spectrometer()
        if not device:
            return

        defaults = dict(zip(("minimum", "center", "maximum"), device.get_wavelength_window()))
        value = simpledialog.askfloat(
            title="Set wavelength",
            prompt=f"Enter {marker_name} wavelength [nm]",
            initialvalue=defaults.get(marker_name, device.center_wavelength_nm),
            parent=self,
        )
        if value is None:
            return

        device.set_wavelength_marker(marker_name, value)
        self.render_kymera_wavelength_panel(device)


    def on_kymera_exposure_slider(self, value):
        if self.kymera_refreshing_controls:
            return

        device = self.get_active_spectrometer()
        if not self.supports_image_view(device):
            return

        device.set_exposure_seconds(value)
        self.render_kymera_exposure_controls(device)


    def set_kymera_exposure_from_entry(self):
        device = self.get_active_spectrometer()
        if not self.supports_image_view(device):
            return

        try:
            device.set_exposure_seconds(float(self.kymera_exposure_var.get()))
        except Exception:
            self.notification("Exposure must be a number", color="#8e0101")
            return

        self.render_kymera_exposure_controls(device)

    def set_kymera_cycle_time_from_entry(self):
        device = self.get_active_spectrometer()
        if not self.supports_image_view(device) or self.kymera_cycle_time_var is None:
            return

        try:
            requested = float(self.kymera_cycle_time_var.get())
        except Exception:
            self.notification("Cycle time must be a number", color="#8e0101")
            return

        exposure = device.get_exposure_seconds()
        if requested < exposure:
            self.notification(
                f"Cycle time must be >= exposure ({exposure:.5f} s)", color="#8e0101"
            )

        device.set_cycle_time_seconds(requested)
        self.render_kymera_exposure_controls(device)

    def on_kymera_axis_mode_toggle(self):
        if self.kymera_refreshing_controls:
            return
        device = self.get_active_spectrometer()
        if not self.supports_image_view(device):
            return
        mode = "wavelength" if self.kymera_axis_mode_var.get() == "on" else "raman"
        device.set_axis_mode(mode)
        try:
            self.render_cached_plot()
        except Exception:
            pass


    def set_kymera_read_mode(self, mode):
        device = self.get_active_spectrometer()
        if not self.supports_image_view(device):
            return

        device.set_read_mode(mode)
        self.render_kymera_read_mode_buttons(device)


    def toggle_kymera_shutter_external(self):
        device = self.get_active_spectrometer()
        if not self.supports_image_view(device):
            return

        device.toggle_shutter_external()
        self.render_kymera_shutter_controls(device)


    def toggle_kymera_shutter_state(self):
        device = self.get_active_spectrometer()
        if not self.supports_image_view(device):
            return

        device.toggle_shutter_state()
        self.render_kymera_shutter_controls(device)


    def on_kymera_shutter_icon_click(self, _event):
        if not self.kymera_controls_enabled:
            return

        device = self.get_active_spectrometer()
        if not self.supports_image_view(device) or not device.shutter_external_enabled:
            return

        device.cycle_shutter_mode()
        self.render_kymera_shutter_controls(device)


    def cycle_kymera_grating(self):
        device = self.get_active_spectrometer()
        if not self.supports_image_view(device):
            return

        device.cycle_grating()
        self.render_kymera_grating_controls(device)
        self.render_kymera_wavelength_panel(device)


    def set_kymera_side_input_slit(self):
        device = self.get_active_spectrometer()
        if not self.supports_image_view(device):
            return

        try:
            device.set_side_input_slit(float(self.kymera_slit_var.get()))
        except Exception:
            self.notification("Slit width must be numeric", color="#8e0101")
            return

        self.render_kymera_slit_controls(device)


    def set_kymera_focus_mirror_steps(self):
        device = self.get_active_spectrometer()
        if not self.supports_image_view(device):
            return

        try:
            device.set_focus_mirror_steps(self.kymera_focus_var.get())
        except Exception:
            self.notification("Focus mirror steps must be numeric", color="#8e0101")
            return

        self.render_kymera_focus_controls(device)


    def autofocus_kymera_focus_mirror(self):
        device = self.get_active_spectrometer()
        if not self.supports_image_view(device):
            return

        device.autofocus_focus_mirror()
        self.render_kymera_focus_controls(device)


    def on_kymera_iris_slider(self, value):
        if self.kymera_refreshing_controls:
            return

        device = self.get_active_spectrometer()
        if not self.supports_image_view(device):
            return

        device.set_side_input_iris_steps(round(value))
        self.render_kymera_iris_controls(device)


    def set_kymera_side_input_iris(self):
        device = self.get_active_spectrometer()
        if not self.supports_image_view(device):
            return

        try:
            device.set_side_input_iris_steps(self.kymera_iris_var.get())
        except Exception:
            self.notification("Iris steps must be numeric", color="#8e0101")
            return

        self.render_kymera_iris_controls(device)


    def draw_kymera_slit_icon(self, canvas):
        palette = self.get_kymera_palette()
        canvas.configure(bg=palette["canvas"])
        canvas.create_oval(10, 8, 82, 66, outline="#9da9b1", width=2)
        canvas.create_line(46, 12, 46, 62, fill="#c8d0d5", width=3)
        canvas.create_arc(12, 10, 80, 64, start=90, extent=180, outline="#737f87", width=2, style="arc")


    def draw_kymera_focus_icon(self, canvas):
        palette = self.get_kymera_palette()
        canvas.configure(bg=palette["canvas"])
        canvas.create_oval(10, 8, 82, 66, outline="#9da9b1", width=2)
        canvas.create_rectangle(18, 16, 26, 58, fill="#4e565b", outline="#4e565b")
        for offset, color in ((0, "#3f8cff"), (6, "#35b0ff"), (-6, "#ff6d4a")):
            canvas.create_line(26, 22 + offset, 72, 18, fill=color, width=2)
            canvas.create_line(26, 36 + offset, 72, 36, fill=color, width=2)
            canvas.create_line(26, 50 + offset, 72, 54, fill=color, width=2)


    def draw_kymera_iris_icon(self, canvas):
        palette = self.get_kymera_palette()
        canvas.configure(bg=palette["canvas"])
        canvas.create_line(12, 36, 78, 12, fill="#d84f4f", width=2)
        canvas.create_line(12, 36, 78, 22, fill="#d84f4f", width=2)
        canvas.create_line(12, 36, 78, 32, fill="#d84f4f", width=2)
        canvas.create_line(12, 36, 78, 42, fill="#d84f4f", width=2)
        canvas.create_line(12, 36, 78, 52, fill="#d84f4f", width=2)
        canvas.create_rectangle(8, 12, 16, 60, fill="#60686e", outline="#60686e")
        canvas.create_rectangle(74, 10, 84, 62, fill="#9da9b1", outline="#9da9b1")


    def render_kymera_shutter_icon(self, spectrometer):
        palette = self.get_kymera_palette()
        canvas = self.kymera_shutter_icon
        canvas.delete("all")
        state_color = palette["open"] if spectrometer.shutter_is_open else palette["closed"]
        outline_color = palette["accent"] if spectrometer.shutter_external_enabled else "#9da9b1"
        canvas.create_oval(10, 8, 82, 66, outline=outline_color, width=3)
        canvas.create_polygon(46, 16, 30, 28, 38, 44, 54, 52, 68, 38, 60, 22, fill=state_color, outline="#d6d6d6", width=1)
        canvas.create_arc(22, 20, 70, 56, start=15, extent=300, outline="#d6d6d6", width=2, style="arc")


    def render_kymera_grating_icon(self, spectrometer):
        canvas = self.kymera_grating_icon
        palette = self.get_kymera_palette()
        canvas.delete("all")
        canvas.create_polygon(16, 12, 76, 12, 62, 40, 30, 40, fill="#5a6d79", outline="#b6c5ce", width=2)
        canvas.create_polygon(16, 12, 30, 40, 16, 58, fill="#d83939", outline="")
        canvas.create_polygon(30, 40, 46, 12, 62, 40, 46, 58, fill="#2cb35b", outline="")
        canvas.create_polygon(46, 12, 76, 12, 62, 40, fill="#27a7ff", outline="")
        canvas.create_line(46, 40, 14, 64, fill="#5e4bff", width=2)
        canvas.create_line(46, 40, 28, 64, fill="#35aaff", width=2)
        canvas.create_line(46, 40, 40, 64, fill="#3dce68", width=2)
        canvas.create_line(46, 40, 52, 64, fill="#f2cb3f", width=2)
        canvas.create_line(46, 40, 64, 64, fill="#ff8b32", width=2)
        canvas.create_line(46, 40, 78, 64, fill="#df3c3c", width=2)
        canvas.create_text(76, 10, text=str(spectrometer.get_active_grating()["index"]), anchor="ne", fill=palette["label"], font=("Arial", 10, "bold"))


    def get_axis_labels(self, spectrometer):
        if self.is_raman_spectrometer(spectrometer) and hasattr(spectrometer, "get_axis_labels"):
            return spectrometer.get_axis_labels()
        if self.reflectance_mode:
            return "Wavelength [nm]", "Relative intensity [%]"
        return "Wavelength [nm]", "Intensity [counts]"


    def get_plot_series(self, spectrometer, index, wavelengths=None, intensities=None):
        raw_wavelengths = numpy.asarray(self.wavelengthsList[index] if wavelengths is None else wavelengths)
        raw_intensities = numpy.asarray(self.intensitiesList[index] if intensities is None else intensities)

        if self.reflectance_mode and not self.is_raman_spectrometer(spectrometer):
            denominator = self.light_reference_intensities[index] - self.dark_reference_intensities[index]
            denominator = numpy.where(denominator == 0, numpy.nan, denominator)
            display_intensities = (raw_intensities - self.dark_reference_intensities[index]) / denominator * 100
        else:
            display_intensities = raw_intensities

        if self.is_raman_spectrometer(spectrometer):
            display_x, display_intensities = spectrometer.format_chart_data(raw_wavelengths, display_intensities)
        else:
            display_x = raw_wavelengths

        return raw_wavelengths, raw_intensities, numpy.asarray(display_x), numpy.asarray(display_intensities)


    def get_detector_count_histogram(self, detector_image):
        finite_values = numpy.asarray(detector_image[numpy.isfinite(detector_image)], dtype=numpy.float64)
        if finite_values.size == 0:
            return numpy.array([]), numpy.array([])

        minimum = float(numpy.nanmin(finite_values))
        maximum = float(numpy.nanmax(finite_values))

        if numpy.isclose(minimum, maximum):
            span = max(abs(minimum) * 0.02, 1.0)
            edges = numpy.linspace(minimum - span, minimum + span, 3)
            histogram = numpy.array([finite_values.size, finite_values.size], dtype=numpy.float64)
        else:
            bin_count = max(24, min(96, int(numpy.sqrt(finite_values.size) / 2)))
            histogram, edges = numpy.histogram(finite_values, bins=bin_count)

        centers = 0.5 * (edges[:-1] + edges[1:])
        return centers, numpy.asarray(histogram, dtype=numpy.float64)


    def get_detector_row_profile(self, detector_image):
        if detector_image.size == 0:
            return numpy.array([]), numpy.array([])

        row_axis = numpy.arange(detector_image.shape[0], dtype=numpy.float64)
        row_profile = numpy.nanmean(detector_image, axis=1)
        return row_axis, numpy.asarray(row_profile, dtype=numpy.float64)


    def ensure_figure_layout(self, image_view):
        target_layout = "image" if image_view else "spectrum"
        if self.figure_layout == target_layout:
            return

        self.figure.clf()
        if image_view:
            grid = self.figure.add_gridspec(3, 2, width_ratios=[0.72, 20.0], height_ratios=[1.0, 6.2, 1.8], wspace=0.075, hspace=0.18)
            self.detector_counts_plot = self.figure.add_subplot(grid[0, :])
            self.detector_row_profile_plot = self.figure.add_subplot(grid[1, 0])
            self.detector_plot = self.figure.add_subplot(grid[1, 1], sharey=self.detector_row_profile_plot)
            self.plot = self.figure.add_subplot(grid[2, 1], sharex=self.detector_plot)
            self.figure.subplots_adjust(left=0.018, right=0.994, top=0.985, bottom=0.095, wspace=0.075, hspace=0.18)
        else:
            self.detector_counts_plot = None
            self.detector_row_profile_plot = None
            self.detector_plot = None
            self.plot = self.figure.add_subplot(111)
            self.figure.subplots_adjust(left=0.07, right=0.992, top=0.985, bottom=0.12)

        self.figure_layout = target_layout


    def get_axis_edges(self, centers):
        centers = numpy.asarray(centers, dtype=numpy.float64)
        if centers.size == 0:
            return centers
        if centers.size == 1:
            return numpy.array([centers[0] - 0.5, centers[0] + 0.5], dtype=numpy.float64)

        midpoints = 0.5 * (centers[:-1] + centers[1:])
        edges = numpy.empty(centers.size + 1, dtype=numpy.float64)
        edges[1:-1] = midpoints
        edges[0] = centers[0] - (midpoints[0] - centers[0])
        edges[-1] = centers[-1] + (centers[-1] - midpoints[-1])
        return edges


    def set_plot_x_limits_to_data_range(self, axis, display_x):
        finite_display_x = numpy.asarray(display_x, dtype=numpy.float64)
        finite_display_x = finite_display_x[numpy.isfinite(finite_display_x)]
        if finite_display_x.size == 0:
            return

        left = float(numpy.nanmin(finite_display_x))
        right = float(numpy.nanmax(finite_display_x))
        if left == right:
            span = max(abs(left) * 0.01, 1.0)
            left -= span
            right += span

        axis.set_xlim(left, right)
        axis.margins(x=0)


    def sort_plot_data_by_x(self, display_x, display_y):
        x_values = numpy.asarray(display_x, dtype=numpy.float64).ravel()
        y_values = numpy.asarray(display_y, dtype=numpy.float64).ravel()
        length = min(x_values.size, y_values.size)
        if length == 0:
            return numpy.array([]), numpy.array([])

        x_values = x_values[:length]
        y_values = y_values[:length]
        finite_mask = numpy.isfinite(x_values) & numpy.isfinite(y_values)
        if numpy.count_nonzero(finite_mask) == 0:
            return numpy.array([]), numpy.array([])

        x_values = x_values[finite_mask]
        y_values = y_values[finite_mask]
        order = numpy.argsort(x_values, kind="mergesort")
        x_values = x_values[order]
        y_values = y_values[order]

        unique_x, first_indices = numpy.unique(x_values, return_index=True)
        if unique_x.size != x_values.size:
            counts = numpy.diff(numpy.append(first_indices, x_values.size))
            y_values = numpy.add.reduceat(y_values, first_indices) / counts
            x_values = unique_x

        return x_values, y_values


    def orient_detector_image_for_display(self, spectrometer, detector_image):
        image_data = numpy.asarray(detector_image, dtype=numpy.float64)
        if bool(getattr(spectrometer, "mirror_spectral_axis_for_display", False)):
            image_data = numpy.fliplr(image_data)
        return image_data


    def draw_detector_image(self, spectrometer, detector_image, display_x):
        if not display_x.size or not detector_image.size:
            return

        image_data = self.orient_detector_image_for_display(spectrometer, detector_image)
        finite_mask = numpy.isfinite(display_x)
        if image_data.shape[1] == display_x.size and numpy.count_nonzero(finite_mask) >= 2:
            x_values = numpy.asarray(display_x[finite_mask], dtype=numpy.float64)
            image_data = image_data[:, finite_mask]
            order = numpy.argsort(x_values)
            x_sorted = x_values[order]
            image_sorted = image_data[:, order]
            unique_mask = numpy.concatenate(([True], numpy.diff(x_sorted) != 0))
            x_sorted = x_sorted[unique_mask]
            image_sorted = image_sorted[:, unique_mask]

            if x_sorted.size >= 2:
                x_edges = self.get_axis_edges(x_sorted)
                y_edges = numpy.arange(image_sorted.shape[0] + 1, dtype=numpy.float64)
                self.detector_plot.pcolormesh(
                    x_edges,
                    y_edges,
                    image_sorted,
                    shading="auto",
                    cmap="gray",
                    rasterized=True,
                )
                self.detector_plot.set_xlim(float(x_edges[0]), float(x_edges[-1]))
                self.detector_plot.set_ylim(0, image_sorted.shape[0])
                return

        finite_display_x = display_x[finite_mask]
        image_left = float(numpy.nanmin(finite_display_x)) if finite_display_x.size else float(display_x[0])
        image_right = float(numpy.nanmax(finite_display_x)) if finite_display_x.size else float(display_x[-1])
        self.detector_plot.imshow(
            image_data,
            aspect="auto",
            origin="lower",
            cmap="gray",
            extent=[image_left, image_right, 0, image_data.shape[0]],
        )


    def render_plot(self, spectrometer, index, wavelengths=None, intensities=None):
        raw_wavelengths, raw_intensities, display_x, display_y = self.get_plot_series(spectrometer, index, wavelengths, intensities)
        x_label, y_label = self.get_axis_labels(spectrometer)
        plot_title = getattr(spectrometer, "detector_name", spectrometer.name)
        show_image_view = self.image_view_enabled and self.supports_image_view(spectrometer)
        self.ensure_figure_layout(show_image_view)

        if show_image_view:
            detector_image = spectrometer.build_detector_image(raw_intensities)
            histogram_x, histogram_y = self.get_detector_count_histogram(detector_image)
            row_axis, row_profile = self.get_detector_row_profile(detector_image)

            self.detector_counts_plot.clear()
            self.detector_row_profile_plot.clear()
            self.detector_plot.clear()
            self.plot.clear()

            self.draw_detector_image(spectrometer, detector_image, display_x)

            if histogram_x.size and histogram_y.size:
                self.detector_counts_plot.fill_between(histogram_x, histogram_y, color="#d9dee5", alpha=0.8, linewidth=0)
                self.detector_counts_plot.plot(histogram_x, histogram_y, color="#7f8b99", linewidth=1.0)
                self.detector_counts_plot.set_xlim(float(histogram_x[0]), float(histogram_x[-1]))
            self.detector_counts_plot.set_xlabel("Counts")
            self.detector_counts_plot.tick_params(axis="y", left=False, labelleft=False)
            self.detector_counts_plot.grid(axis="x", alpha=0.2)

            if row_axis.size and row_profile.size:
                self.detector_row_profile_plot.plot(row_profile, row_axis, color="#b67a00", linewidth=1.2)
                self.detector_row_profile_plot.set_ylim(0, detector_image.shape[0])
            self.detector_row_profile_plot.tick_params(axis="x", bottom=False, labelbottom=False)
            self.detector_row_profile_plot.tick_params(axis="y", left=False, labelleft=False)
            self.detector_row_profile_plot.grid(axis="y", alpha=0.12)
            self.detector_row_profile_plot.margins(x=0.08)

            self.detector_plot.tick_params(axis="x", labelbottom=False)

            plot_x, plot_y = self.sort_plot_data_by_x(display_x, display_y)
            self.plot.plot(plot_x, plot_y, color="#b67a00")
            self.set_plot_x_limits_to_data_range(self.plot, plot_x)
            self.plot.set_xlabel(x_label)
            self.plot.set_ylabel(y_label)
            self.plot.grid()
        else:
            self.plot.clear()
            plot_x, plot_y = self.sort_plot_data_by_x(display_x, display_y)
            self.plot.plot(plot_x, plot_y)
            self.set_plot_x_limits_to_data_range(self.plot, plot_x)
            self.plot.set_xlabel(x_label)
            self.plot.set_ylabel(y_label)
            self.plot.set_title(plot_title, loc="right")
            self.plot.grid()

            if self.reflectance_mode and not self.is_raman_spectrometer(spectrometer):
                self.plot.set_ylim(-20, 180)


    def render_cached_plot(self):
        if not self.connected_spectrometers:
            return

        index = self.get_active_index()
        if len(self.wavelengthsList) <= index or len(self.intensitiesList) <= index:
            return

        if numpy.size(self.wavelengthsList[index]) == 0 or numpy.size(self.intensitiesList[index]) == 0:
            return

        self.render_plot(self.connected_spectrometers[index], index)
        self.canvas.draw()


    # ------------------------------------------------------------------
    # Automated-routine plot ownership (e.g. Z-stack overlay)
    # ------------------------------------------------------------------

    def begin_routine_plot(self, title="Routine"):
        """Take over the spectrum plot for an automated routine.

        Stops live acquisition, marks the frame as routine-owned so the
        temperature watchdog will not auto-restart live view, and clears
        the spectrum subplot so the routine can build its own cumulative
        overlay. Must be called on the GUI thread.
        """
        self.routine_active = True
        self._routine_trace_count = 0
        try:
            self.stop_spectrometer(user_initiated=False)
        except Exception:
            pass
        # Force the single-axis spectrum layout so self.plot is the full
        # width axis (the image view splits the figure into sub-axes).
        try:
            self.image_view_enabled = False
            self.ensure_figure_layout(False)
            if self.plot is not None:
                self.plot.clear()
                self.plot.set_title(title, loc="right")
                self.plot.grid()
                self.canvas.draw()
        except Exception as error:
            debugp("spec", f"begin_routine_plot failed: {error}")


    def add_routine_trace(self, spectrometer, wavelengths, intensities,
                          label=None, offset_step=1.0, normalize=True):
        """Append one spectrum to the active routine overlay.

        Each trace is normalized to [0, 1] and shifted up by
        ``offset_step`` per trace so successive Z positions stack like a
        waterfall plot. Must be called on the GUI thread.
        """
        if not getattr(self, "routine_active", False) or self.plot is None:
            return
        try:
            if hasattr(spectrometer, "format_chart_data"):
                display_x, display_y = spectrometer.format_chart_data(wavelengths, intensities)
            else:
                display_x, display_y = wavelengths, intensities

            display_x = numpy.asarray(display_x, dtype=numpy.float64).ravel()
            display_y = numpy.asarray(display_y, dtype=numpy.float64).ravel()
            display_x, display_y = self.sort_plot_data_by_x(display_x, display_y)
            if display_x.size == 0:
                return

            index = getattr(self, "_routine_trace_count", 0)
            if normalize:
                y_min = float(numpy.nanmin(display_y))
                y_max = float(numpy.nanmax(display_y))
                if y_max > y_min:
                    display_y = (display_y - y_min) / (y_max - y_min)
                else:
                    display_y = display_y * 0.0
            plot_y = display_y + index * offset_step

            self.plot.plot(display_x, plot_y, linewidth=1.0, label=label)
            x_label, y_label = self.get_axis_labels(spectrometer)
            self.plot.set_xlabel(x_label)
            self.plot.set_ylabel("Normalized intensity + offset" if normalize else y_label)
            if label:
                try:
                    self.plot.legend(fontsize=7, loc="upper right", ncol=2)
                except Exception:
                    pass

            self._routine_trace_count = index + 1
            self.canvas.draw_idle()
        except Exception as error:
            debugp("spec", f"add_routine_trace failed: {error}")


    def end_routine_plot(self, resume_live=False):
        """Release plot ownership after a routine finishes.

        Must be called on the GUI thread. When ``resume_live`` is True the
        live view restarts if the detector is ready; otherwise the overlay
        is left on screen for inspection.
        """
        self.routine_active = False
        try:
            self.canvas.draw()
        except Exception:
            pass
        if resume_live:
            try:
                device = self.get_active_spectrometer()
                if device and self.is_live_ready_for_spectrometer(device):
                    self.start_spectrometer(device, user_initiated=False)
            except Exception:
                pass
        else:
            # Keep the overlay on screen: mark live view as user-paused so
            # the temperature watchdog does not auto-restart it (which would
            # clear the overlay on its next 1 s tick).
            self._user_paused_live = True
            try:
                if getattr(self, "play_button", None):
                    self.play_button.lift()
            except Exception:
                pass


    def update_plot(self, spectrometer, index):
        """Updates the plot of a spectrometer with raw data, 
        or calculates reflectance/transmittance if this mode is enabled.
        """
        if spectrometer.is_running :
            if not spectrometer.chart_queue.empty() :
                
                local_wavelengths, local_intensities = spectrometer.chart_queue.get()
                
                if len(self.wavelengthsList) >= index + 1 and len(self.intensitiesList) >= index + 1:
                    self.wavelengthsList[index] = local_wavelengths
                    self.intensitiesList[index] = local_intensities

                self.render_plot(spectrometer, index, local_wavelengths, local_intensities)
                return True
        return False


    def refresh_kymera_shutter_indicator_if_needed(self, spectrometer):
        if not self.supports_image_view(spectrometer):
            return

        shutter_state = (
            bool(getattr(spectrometer, "shutter_external_enabled", False)),
            bool(getattr(spectrometer, "shutter_is_open", False)),
            spectrometer.get_shutter_mode() if hasattr(spectrometer, "get_shutter_mode") else None,
        )
        if shutter_state == self._last_shutter_render_state:
            return

        self._last_shutter_render_state = shutter_state
        self.render_kymera_shutter_controls(spectrometer)


    def update_graph(self, first_launch):
        """Updates the graph (all plots) every 20ms.
        """
        
        if first_launch and not self.graph_updating:
            debugp("spec", "First time updating graph")
            self.graph_updating = True

        elif first_launch:
            debugp("spec", "Aborted updating graph")
            return
        
        update_interval = 20

        # While an automated routine owns the plot, do not pull frames or
        # redraw — the routine draws its own cumulative overlay. Keep the
        # after-loop alive so live view resumes cleanly when it releases.
        if getattr(self, "routine_active", False):
            self.after(update_interval, lambda: self.update_graph(False))
            return

        if self.connected_spectrometers:

            index = 0 if len(self.connected_spectrometers) == 1 else self.split - 1
            spec = self.connected_spectrometers[index]
            self.refresh_kymera_shutter_indicator_if_needed(spec)

            #Minimise useless spectrometer updates
            update_interval = max(20, int(spec.integration_time / 1000))

            if spec.is_running and not spec.chart_queue.empty():
                updated = False
                while not spec.chart_queue.empty():
                    updated = self.update_plot(spec, index) or updated
                if updated:
                    self.canvas.draw()

        #print(f"Finished updating graph {datetime.now():%H.%M.%S}")

        #THIS COULD BE THE SOURCE OF THE CAMERA LAG (update_graph could wait too long to acquire data)
        self.after(update_interval, lambda: self.update_graph(False))


    def get_signal_frame_count(self, spectrometer):
        if hasattr(spectrometer, "get_signal_frame_count"):
            try:
                return max(int(spectrometer.get_signal_frame_count()), 1)
            except Exception:
                pass

        if getattr(spectrometer, "selected_acquisition_mode", "Single") == "Kinetic":
            return max(int(getattr(spectrometer, "kinetic_series_length", 1)), 1)
        return 1


    def set_signal_recording_controls(self, recording, current=0, total=0, message=None):
        state = "disabled" if recording else "normal"
        for widget_name in (
            "save_button",
            "adv_save_button",
            "play_button",
            "pause_button",
            "view_button",
            "fullscreen_button",
            "import_button",
            "new_experiment_button",
        ):
            widget = getattr(self, widget_name, None)
            if widget:
                try:
                    widget.configure(state=state)
                except Exception:
                    pass

        for button in self.read_mode_buttons.values():
            try:
                button.configure(state=state)
            except Exception:
                pass

        for widget in self.kymera_control_widgets:
            try:
                widget.configure(state=state)
            except Exception:
                pass

        if self.signal_recording_label:
            if recording:
                label = message or f"Recording {current}/{total}"
                self.signal_recording_label.configure(text=label)
                self.signal_recording_label.grid()
            else:
                self.signal_recording_label.configure(text="")
                self.signal_recording_label.grid_remove()


    def update_signal_recording_progress(self, current, total):
        if self.signal_recording_label:
            self.signal_recording_label.configure(text=f"Recording {current}/{total}")


    def take_signal(self):
        spectrometer = self.get_active_spectrometer()
        if not spectrometer:
            self.notification("No spectrometer connected", color="#8e0101")
            return

        capture_series = getattr(spectrometer, "capture_signal_series", None)
        if not callable(capture_series):
            self.save_data()
            return

        if self.signal_recording_active:
            return

        if self.supports_image_view(spectrometer) and not self.is_live_ready_for_spectrometer(spectrometer):
            self.notification("Detector temperature is not stabilized", color="#8e0101")
            return

        self.signal_recording_active = True
        self.signal_recording_spectrometer = spectrometer
        self.signal_recording_resume_live = bool(getattr(spectrometer, "is_running", False)) and not self._user_paused_live
        self.signal_recorded_frames = []
        self.signal_recording_result = None
        self.signal_recording_error = None
        self.signal_recording_queue = queue.Queue()

        if getattr(spectrometer, "is_running", False):
            self.stop_spectrometer(user_initiated=False)

        total = self.get_signal_frame_count(spectrometer)
        self.set_signal_recording_controls(True, 0, total)
        self.notification("Signal acquisition started", color="#006bd2")

        self.signal_recording_thread = threading.Thread(
            target=self._signal_recording_worker,
            args=(spectrometer,),
            daemon=True,
        )
        self.signal_recording_thread.start()
        self.after(100, self.poll_signal_recording)


    def _signal_recording_worker(self, spectrometer):
        def progress_callback(current, total):
            self.signal_recording_queue.put(("progress", current, total))

        try:
            should_spool_sif = self.get_signal_frame_count(spectrometer) > 1
            try:
                frames = spectrometer.capture_signal_series(
                    progress_callback=progress_callback,
                    spool_sif=should_spool_sif,
                )
            except TypeError:
                frames = spectrometer.capture_signal_series(progress_callback=progress_callback)
            except Exception:
                if not should_spool_sif:
                    raise
                cleanup_spooled_sif = getattr(spectrometer, "cleanup_last_spooled_sif_files", None)
                if callable(cleanup_spooled_sif):
                    cleanup_spooled_sif()
                frames = spectrometer.capture_signal_series(progress_callback=progress_callback)

            if should_spool_sif and not frames:
                cleanup_spooled_sif = getattr(spectrometer, "cleanup_last_spooled_sif_files", None)
                if callable(cleanup_spooled_sif):
                    cleanup_spooled_sif()
                frames = spectrometer.capture_signal_series(progress_callback=progress_callback)
            self.signal_recording_queue.put(("done", frames, None))
        except Exception as error:
            self.signal_recording_queue.put(("done", None, error))


    def poll_signal_recording(self):
        done = False
        frames = None
        error = None

        while True:
            try:
                event = self.signal_recording_queue.get_nowait()
            except queue.Empty:
                break

            if event[0] == "progress":
                self.update_signal_recording_progress(event[1], event[2])
            elif event[0] == "done":
                done = True
                frames = event[1]
                error = event[2]

        if not done and self.signal_recording_thread and self.signal_recording_thread.is_alive():
            self.after(100, self.poll_signal_recording)
            return

        self.complete_signal_recording(frames, error)


    def complete_signal_recording(self, frames, error):
        spectrometer = self.signal_recording_spectrometer
        self.signal_recording_thread = None

        if error is not None:
            self.notification(f"Signal acquisition failed: {error}", color="#8e0101")
            self.restore_after_signal_workflow()
            return

        frames = frames or []
        if not frames:
            self.notification("No signal data was acquired", color="#8e0101")
            self.restore_after_signal_workflow()
            return

        self.signal_recorded_frames = frames
        self.set_signal_recording_controls(True, len(frames), len(frames), "Ready to save")

        if spectrometer in self.connected_spectrometers:
            index = self.connected_spectrometers.index(spectrometer)
            wavelengths, intensities = frames[-1]
            self.wavelengthsList[index] = wavelengths
            self.intensitiesList[index] = intensities
            self.render_plot(spectrometer, index, wavelengths, intensities)
            self.canvas.draw()

        self.open_signal_save_popup(spectrometer, frames)


    def restore_after_signal_workflow(self):
        spectrometer = self.signal_recording_spectrometer
        resume_live = self.signal_recording_resume_live

        self.signal_recording_active = False
        self.signal_recording_spectrometer = None
        self.signal_recording_resume_live = False
        self.signal_recording_result = None
        self.signal_recording_error = None
        self.set_signal_recording_controls(False)
        self.update_live_temperature_controls(auto_start=False)
        cleanup_spooled_sif = getattr(spectrometer, "cleanup_last_spooled_sif_files", None)
        if callable(cleanup_spooled_sif):
            cleanup_spooled_sif()

        if resume_live and spectrometer in self.connected_spectrometers and self.is_live_ready_for_spectrometer(spectrometer):
            self.start_spectrometer(spectrometer, user_initiated=False)


    def _center_toplevel(self, popup, width, height):
        x = int((self.master.winfo_width()/2) + self.master.winfo_x() - (width/2))
        y = int((self.master.winfo_height()/2) + self.master.winfo_y() - (height/2))
        popup.geometry(f"{width}x{height}+{x}+{y}")


    def open_signal_save_popup(self, spectrometer, frames):
        if self.signal_save_popup:
            self.signal_save_popup.focus_force()
            return

        popup = CTkToplevel(self)
        self.signal_save_popup = popup
        popup.title("Save data as ASCII XY format")
        popup.minsize(420, 360)
        self._center_toplevel(popup, 460, 420)
        popup.grid_columnconfigure((0, 1), weight=1)
        popup.protocol("WM_DELETE_WINDOW", self.cancel_signal_save_popup)
        popup.attributes("-topmost", True)
        self.after(50, lambda: popup.attributes("-topmost", False))

        title = CTkLabel(popup, text="Save Signal", font=("Arial", 20))
        title.grid(row=0, column=0, padx=24, pady=(22, 12), sticky="w", columnspan=2)

        default_name = self.master.directory_frame.spectrometer_backup_name.get() or "Spectrum"
        name_frame = CTkFrame(popup, fg_color="transparent")
        name_frame.grid(row=1, column=0, padx=24, pady=4, sticky="ew", columnspan=2)
        name_frame.grid_columnconfigure(1, weight=1)
        CTkLabel(name_frame, text="File name").grid(row=0, column=0, padx=(0, 10), sticky="w")
        self.signal_save_name_entry = CTkEntry(name_frame, textvariable=StringVar(value=default_name))
        self.signal_save_name_entry.grid(row=0, column=1, sticky="ew")

        separator_frame = CTkFrame(popup)
        separator_frame.grid(row=2, column=0, padx=(24, 12), pady=12, sticky="nsew")
        CTkLabel(separator_frame, text="Separator").pack(anchor="w", padx=12, pady=(10, 2))
        self.signal_save_separator_var = StringVar(value="Comma")
        for label in ("Comma", "Tab", "Semicolon", "Space"):
            CTkRadioButton(
                separator_frame,
                text=label,
                variable=self.signal_save_separator_var,
                value=label,
                border_color="#1F6AA5",
            ).pack(anchor="w", padx=12, pady=3)

        options_frame = CTkFrame(popup)
        options_frame.grid(row=2, column=1, padx=(12, 24), pady=12, sticky="nsew")
        CTkLabel(options_frame, text="Output").pack(anchor="w", padx=12, pady=(10, 2))
        self.signal_save_sif_entry = CTkCheckBox(
            options_frame,
            text="Also save .sif",
            border_width=2,
            border_color="#1F6AA5",
        )
        self.signal_save_sif_entry.pack(anchor="w", padx=12, pady=5)
        self.signal_save_separate_entry = CTkCheckBox(
            options_frame,
            text="Write each image to a separate file",
            border_width=2,
            border_color="#1F6AA5",
        )
        self.signal_save_separate_entry.pack(anchor="w", padx=12, pady=5)

        info_text = f"{len(frames)} frame{'s' if len(frames) != 1 else ''} will be written with acquisition information at the top."
        CTkLabel(popup, text=info_text, anchor="w", justify="left").grid(row=3, column=0, padx=24, pady=(0, 10), sticky="ew", columnspan=2)

        CTkButton(
            popup,
            text="Cancel",
            fg_color="transparent",
            border_width=2,
            border_color="#1F6AA5",
            command=self.cancel_signal_save_popup,
        ).grid(row=4, column=0, padx=(24, 12), pady=(8, 22), sticky="ew")
        CTkButton(
            popup,
            text="Ok",
            command=lambda: self.confirm_signal_save(spectrometer, frames),
        ).grid(row=4, column=1, padx=(12, 24), pady=(8, 22), sticky="ew")

        popup.focus_force()


    def cancel_signal_save_popup(self):
        if self.signal_save_popup:
            self.signal_save_popup.destroy()
            self.signal_save_popup = None
        self.restore_after_signal_workflow()


    def confirm_signal_save(self, spectrometer, frames):
        separator_label = self.signal_save_separator_var.get() if hasattr(self, "signal_save_separator_var") else "Comma"
        delimiter = {
            "Comma": ",",
            "Tab": "\t",
            "Semicolon": ";",
            "Space": " ",
        }.get(separator_label, ",")

        save_each = bool(self.signal_save_separate_entry.get()) if hasattr(self, "signal_save_separate_entry") else False
        save_sif = bool(self.signal_save_sif_entry.get()) if hasattr(self, "signal_save_sif_entry") else False
        name = self.signal_save_name_entry.get().strip() if hasattr(self, "signal_save_name_entry") else ""

        try:
            saved_paths = self.save_signal_recording(spectrometer, frames, delimiter, save_each, save_sif, name)
        except Exception as error:
            self.notification(f"Impossible to save signal: {error}", color="#8e0101")
            return

        if self.signal_save_popup:
            self.signal_save_popup.destroy()
            self.signal_save_popup = None

        if saved_paths:
            self.notification("Successfully saved signal as", saved_paths[0], "#1a8300", path=saved_paths[0])
        self.restore_after_signal_workflow()


    def build_signal_base_path(self, spectrometer, backup_name):
        backup_name = backup_name or self.master.directory_frame.spectrometer_backup_name.get() or "Spectrum"
        backup_name = os.path.splitext(backup_name)[0]
        counts = self.file_system.get_max_spectrum_number()
        file_path = self.file_system.get_spectrometer_directory(
            spectrometer.integration_time,
            spectrometer.name,
            backup_name,
        )
        timestamp = datetime.now()
        file_path = (
            file_path
            .replace("#", str(counts))
            .replace("@", f"{timestamp:%H.%M.%S}")
            .replace("$", spectrometer.name.split("-")[-1])
        )
        root, _extension = os.path.splitext(file_path)
        return root


    def selected_option_label(self, options, selected_key, fallback=""):
        for option in options or []:
            if option.get("key") == selected_key:
                return option.get("label", fallback)
        return fallback


    def build_signal_acquisition_header(self, spectrometer, frame_count):
        def line(label, value):
            return f"{label:<30}{value}"

        timings = spectrometer.get_acquisition_timings() if hasattr(spectrometer, "get_acquisition_timings") else {}
        exposure_s = timings.get("exposure", getattr(spectrometer, "integration_time", 0) / 1000000.0)
        accumulate_s = timings.get("accumulate", exposure_s)
        kinetic_s = timings.get("kinetic", exposure_s)
        frequency = (1.0 / kinetic_s) if kinetic_s else 0.0
        acquisition_mode = getattr(spectrometer, "selected_acquisition_mode", "Single")
        read_mode = getattr(spectrometer, "selected_read_mode", "")
        read_mode_label = {
            "FVB": "Full Vertical Binning",
            "Image": "Image",
            "Multi-track": "Multi-track",
        }.get(read_mode, read_mode)

        state, temperature = ("unavailable", None)
        if hasattr(spectrometer, "get_temperature_state"):
            state, temperature = spectrometer.get_temperature_state()
        elif hasattr(spectrometer, "get_temperature"):
            temperature = spectrometer.get_temperature()

        grating = spectrometer.get_active_grating() if hasattr(spectrometer, "get_active_grating") else {}
        vertical_shift = self.selected_option_label(
            getattr(spectrometer, "vertical_shift_speed_options", []),
            getattr(spectrometer, "selected_vertical_shift_speed_key", None),
        )
        vertical_amplitude = self.selected_option_label(
            getattr(spectrometer, "vertical_clock_amplitude_options", []),
            getattr(spectrometer, "selected_vertical_clock_amplitude_key", None),
        )
        readout_rate = self.selected_option_label(
            getattr(spectrometer, "readout_rate_options", []),
            getattr(spectrometer, "selected_readout_rate_key", None),
        )
        preamp_gain = self.selected_option_label(
            getattr(spectrometer, "preamp_gain_options", []),
            getattr(spectrometer, "selected_preamp_gain_key", None),
        )

        temperature_text = "" if temperature is None else f"{temperature:g}"
        shutter_mode = spectrometer.get_shutter_mode() if hasattr(spectrometer, "get_shutter_mode") else ""

        now = datetime.now()
        date_text = f"{now:%a %b %d %H:%M:%S}.{int(now.microsecond / 1000):03d} {now:%Y}"

        header = [
            line("Date and Time:", date_text),
            line("Software Version:", "MicroView"),
            line("Temperature (C):", temperature_text),
            line("Temperature State:", state),
            line("Model:", getattr(spectrometer, "detector_name", getattr(spectrometer, "name", ""))),
            line("Data Type:", "Counts"),
            line("Acquisition Mode:", acquisition_mode),
            line("Trigger Mode:", "Internal"),
            line("Exposure Time (secs):", f"{exposure_s:.6g}"),
            line("Accumulate Cycle Time (secs):", f"{accumulate_s:.6g}"),
            line("Number of Accumulations:", getattr(spectrometer, "number_accumulations", 1)),
            line("Kinetic Cycle Time (secs):", f"{kinetic_s:.6g}"),
            line("Frequency (Hz):", f"{frequency:.6g}"),
            line("Number in Kinetics Series:", frame_count if acquisition_mode == "Kinetic" else 1),
            line("Readout Mode:", read_mode_label),
            line("Horizontal binning:", getattr(spectrometer, "multi_track_horizontal_binning", 1)),
            line("Shutter Mode:", shutter_mode),
            line("Horizontal flipped:", str(bool(getattr(spectrometer, "multi_track_flip_horizontal", False))).lower()),
            line("Vertical Shift Speed (usecs):", vertical_shift),
            line("Pixel Readout Rate (MHz):", readout_rate),
            line("Baseline Clamp:", "ON" if getattr(spectrometer, "baseline_clamp_enabled", False) else "OFF"),
            line("Clock Amplitude:", vertical_amplitude),
            line("Output Amplifier:", getattr(spectrometer, "selected_output_amplifier", "")),
            line("Serial Number:", getattr(spectrometer, "serial", "")),
            line("Pre-Amplifier Gain:", preamp_gain),
            "KY328i:",
            line("Serial Number:", getattr(spectrometer, "serial", "")),
            line("Wavelength (nm):", getattr(spectrometer, "center_wavelength_nm", "")),
            line("Grating Groove Density (l/mm):", grating.get("lines_per_mm", "")),
            line("Grating Blaze:", grating.get("blaze", "")),
            line("Output Flipper Port:", "Direct"),
            line("Input Side Slit Width (um):", getattr(spectrometer, "side_input_slit_um", "")),
            line("Side Iris Steps:", getattr(spectrometer, "side_input_iris_steps", "")),
        ]
        return [str(item) for item in header]


    def prepare_signal_frames_for_ascii(self, spectrometer, frames):
        processed_frames = []
        for wavelengths, intensities in frames:
            raw_wavelengths = numpy.asarray(wavelengths, dtype=numpy.float64).ravel()
            raw_intensities = numpy.asarray(intensities, dtype=numpy.float64).ravel()

            if self.is_raman_spectrometer(spectrometer):
                display_x, display_y = spectrometer.format_chart_data(raw_wavelengths, raw_intensities)
            else:
                display_x, display_y = raw_wavelengths, raw_intensities

            display_x = numpy.asarray(display_x, dtype=numpy.float64).ravel()
            display_y = numpy.asarray(display_y, dtype=numpy.float64).ravel()
            display_x, display_y = self.sort_plot_data_by_x(display_x, display_y)
            if display_x.size and display_y.size:
                processed_frames.append((display_x, display_y))

        return processed_frames


    def format_ascii_value(self, value):
        try:
            value = float(value)
        except Exception:
            return str(value)

        if not numpy.isfinite(value):
            return ""
        if abs(value - round(value)) < 1e-9:
            return str(int(round(value)))
        return f"{value:.10g}"


    def write_signal_ascii_file(self, file_path, header, rows, delimiter):
        directory = os.path.dirname(file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        with open(file_path, mode="w", newline="") as file:
            for header_line in header:
                file.write(f"{header_line}\n")
            file.write("\n\n")
            writer = csv.writer(file, delimiter=delimiter, lineterminator="\n")
            writer.writerows(rows)


    def save_signal_recording(self, spectrometer, frames, delimiter=",", separate_files=False, save_sif=False, backup_name=""):
        processed_frames = self.prepare_signal_frames_for_ascii(spectrometer, frames)
        if not processed_frames:
            raise ValueError("No signal frames to save")

        base_path = self.build_signal_base_path(spectrometer, backup_name)
        header = self.build_signal_acquisition_header(spectrometer, len(processed_frames))
        saved_paths = []

        if separate_files:
            for frame_index, (display_x, display_y) in enumerate(processed_frames, start=1):
                suffix = f"_{frame_index:04d}" if len(processed_frames) > 1 else ""
                asc_path = f"{base_path}{suffix}.asc"
                rows = [
                    [self.format_ascii_value(x), self.format_ascii_value(y)]
                    for x, y in zip(display_x, display_y)
                ]
                self.write_signal_ascii_file(asc_path, header, rows, delimiter)
                saved_paths.append(asc_path)
        else:
            common_length = min(frame[0].size for frame in processed_frames)
            common_length = min(common_length, *(frame[1].size for frame in processed_frames))
            display_x = processed_frames[0][0][:common_length]
            intensity_columns = [frame[1][:common_length] for frame in processed_frames]
            rows = []
            for row_index in range(common_length):
                rows.append(
                    [self.format_ascii_value(display_x[row_index])]
                    + [self.format_ascii_value(column[row_index]) for column in intensity_columns]
                )

            asc_path = f"{base_path}.asc"
            self.write_signal_ascii_file(asc_path, header, rows, delimiter)
            saved_paths.append(asc_path)

        if save_sif:
            saved_paths.extend(
                self.save_signal_sif_files(
                    spectrometer,
                    base_path,
                    header,
                    len(processed_frames),
                    separate_files,
                )
            )

        return saved_paths


    def save_signal_sif_files(self, spectrometer, base_path, header, frame_count, separate_files):
        saved_paths = []
        if separate_files:
            spooled_files_getter = getattr(spectrometer, "get_last_spooled_sif_files", None)
            spooled_files = spooled_files_getter() if callable(spooled_files_getter) else []

            if len(spooled_files) >= frame_count:
                for frame_index, source_path in enumerate(spooled_files[:frame_count], start=1):
                    suffix = f"_{frame_index:04d}" if frame_count > 1 else ""
                    destination_path = f"{base_path}{suffix}.sif"
                    directory = os.path.dirname(destination_path)
                    if directory:
                        os.makedirs(directory, exist_ok=True)
                    shutil.copyfile(source_path, destination_path)
                    saved_paths.append(destination_path)
                return saved_paths

            sdk_split_paths = self.save_separate_sifs_with_sdk(spectrometer, base_path, header, frame_count)
            if sdk_split_paths:
                return sdk_split_paths

            self.notification("The SDK returned only one .sif for this kinetic series", color="#e17e00")

        sif_path = f"{base_path}.sif"
        save_sif_method = getattr(spectrometer, "save_last_signal_as_sif", None)
        if callable(save_sif_method):
            ok, status = save_sif_method(sif_path, "\n".join(header))
            if ok:
                saved_paths.append(sif_path)
            else:
                self.notification(f"Could not save .sif file (status={status})", color="#e17e00")
        else:
            self.notification(".sif export is not available for this spectrometer", color="#e17e00")

        return saved_paths


    def save_separate_sifs_with_sdk(self, spectrometer, base_path, header, frame_count):
        save_sif_method = getattr(spectrometer, "save_last_signal_as_sif", None)
        if not callable(save_sif_method):
            return []

        temp_dir = tempfile.mkdtemp(prefix="microview_sif_export_")
        try:
            temp_stem = os.path.join(temp_dir, "signal.sif")
            try:
                ok, status = save_sif_method(temp_stem, "\n".join(header), False)
            except TypeError:
                ok, status = save_sif_method(temp_stem, "\n".join(header))

            if not ok:
                self.notification(f"Could not save .sif file (status={status})", color="#e17e00")
                return []

            produced_files = [
                os.path.join(temp_dir, name)
                for name in os.listdir(temp_dir)
                if os.path.isfile(os.path.join(temp_dir, name))
                and name.lower().endswith((".sif", ".sifx"))
            ]
            produced_files = sorted(produced_files, key=lambda path: (os.path.getmtime(path), path))

            if len(produced_files) < frame_count:
                return []

            saved_paths = []
            for frame_index, source_path in enumerate(produced_files[:frame_count], start=1):
                suffix = f"_{frame_index:04d}" if frame_count > 1 else ""
                destination_path = f"{base_path}{suffix}.sif"
                directory = os.path.dirname(destination_path)
                if directory:
                    os.makedirs(directory, exist_ok=True)
                shutil.copyfile(source_path, destination_path)
                saved_paths.append(destination_path)
            return saved_paths
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


    def save_data(self, file_path=None, wavelengths=None, intensities=None, single_save=True, reference=False):
        """Saves the current raw data and reflectance/transmittance data if this mode is enabled.

        Notes
        ------------
        The saved file name always includes the iteration number, date, time, and spectrometer acquisition time. 
        Users can modify the file name in the directory frame. However, in the case of an advanced save, 
        the name specified in the associated popup takes priority. If no name is provided in the popup, 
        the one set in the directory frame will be used. If neither field is filled, the default name will be Spectrum

        Parameters
        ------------
        file_path : `str`, optional
            Path to the file save location, None by default
        wavelengths : `list(float)`, optional
            List of measured wavelengths, Empty by default
        intensities : `list(float)`, optional
            List of raw intensity data measured, Empty by default
        single_save : `bool`, optional
            Defines how files are named and whether or not a notification is returned after saving, True by default
        reference : `bool`, optional
            If this variable is true, then save the reflectance/transmittance data, False by default
        """
        #Used for Single Save 
        if single_save:
            
            counts = self.file_system.get_max_spectrum_number()
            for i in range(len(self.connected_spectrometers)):

                file_path = self.file_system.get_spectrometer_directory(self.connected_spectrometers[i].integration_time, self.connected_spectrometers[i].name)
                file_path = file_path.replace("#", str(counts)).replace("@", f"{datetime.now():%H.%M.%S}").replace("$", self.connected_spectrometers[i].name.split("-")[-1])                    
                
                ref_file_path = self.file_system.get_spectrometer_directory(self.connected_spectrometers[i].integration_time, self.connected_spectrometers[i].name, "")

                #Add save refs here
                self.save_references(ref_file_path, self.connected_spectrometers[i].integration_time, i, counts)
                
                self.single_save(file_path, wavelengths, intensities, single_save, reference, i)
        
        #Used for Advanced Save (Never)
        else:
            self.single_save(file_path, wavelengths, intensities, single_save, reference, self.split-1)
    
    def save_references(self, ref_file_path, acquisition_time, index, file_index):
       
        self.save_light_reference = False
        self.save_dark_reference = False
        
        if self.light_reference:
            # Get the relevant arrays
            curr_wavelengths = self.light_reference_wavelengths[index]
            curr_intensities = self.light_reference_intensities[index]
            prev_wavelengths = self.last_saved_light_reference_wavelengths[index]
            prev_intensities = self.last_saved_light_reference_intensities[index]

            # Check if the previous arrays are not empty and shapes match
            wavelengths_changed = (prev_wavelengths.shape != curr_wavelengths.shape) or not numpy.array_equal(curr_wavelengths, prev_wavelengths)
            intensities_changed = (prev_intensities.shape != curr_intensities.shape) or not numpy.array_equal(curr_intensities, prev_intensities)

            if wavelengths_changed or intensities_changed:
                self.save_light_reference = True
                self.last_saved_light_reference_wavelengths[index] = self.light_reference_wavelengths[index].copy()
                self.last_saved_light_reference_intensities[index] = self.light_reference_intensities[index].copy()
                debugp("MoveSave", f"Set save_light_reference")
        
        
        if self.dark_reference:
            # Get the relevant arrays
            curr_wavelengths = self.dark_reference_wavelengths[index]
            curr_intensities = self.dark_reference_intensities[index]
            prev_wavelengths = self.last_saved_dark_reference_wavelengths[index]
            prev_intensities = self.last_saved_dark_reference_intensities[index]

            # Check if the previous arrays are not empty and shapes match
            wavelengths_changed = (prev_wavelengths.shape != curr_wavelengths.shape) or not numpy.array_equal(curr_wavelengths, prev_wavelengths)
            intensities_changed = (prev_intensities.shape != curr_intensities.shape) or not numpy.array_equal(curr_intensities, prev_intensities)

            if wavelengths_changed or intensities_changed:
                self.save_dark_reference = True
                self.last_saved_dark_reference_wavelengths[index] = self.dark_reference_wavelengths[index].copy()
                self.last_saved_dark_reference_intensities[index] = self.dark_reference_intensities[index].copy()
                debugp("MoveSave", f"Set save_dark_reference")
        
        

        reference_path = os.path.dirname(ref_file_path)
        end_file = f"_{''}_{str(file_index)}_{self.connected_spectrometers[index].name.split('-')[-1]}__{datetime.now():%Y%m%d_%H.%M.%S}_{acquisition_time}ms.txt"
        if self.save_light_reference:
            name = f"reference{end_file}" 
            debugp("SaveRef", "Saving Light ref")
            self.single_save(f"{reference_path}/{name}", self.light_reference_wavelengths[index], self.light_reference_intensities[index], True, True, index)
            
            if self.light_ref_acquisition_time[index] != self.connected_spectrometers[index].integration_time:
                debugp("Acq Time L", f"{self.light_ref_acquisition_time[index]} {self.connected_spectrometers[index].integration_time}")
                self.notification(f"Light reference acquisition time differs from current", color="#e17e00")
        
        if self.save_dark_reference:
            name = f"dark{end_file}" 
            debugp("SaveRef", "Saving Dark ref")
            self.single_save(f"{reference_path}/{name}", self.dark_reference_wavelengths[index], self.dark_reference_intensities[index], True, True, index)
            
            if self.dark_ref_acquisition_time[index] != self.connected_spectrometers[index].integration_time:
                debugp("Acq Time D", f"{self.dark_ref_acquisition_time[index]} {self.connected_spectrometers[index].integration_time}")
                self.notification(f"Dark reference acquisition time differs from current", color="#e17e00")

    
    def single_save(self, file_path, wavelengths, intensities, single_save, reference, index, display_notification=True):    
        # Only pull from the spectrometer chart queue if caller did not provide arrays.
        if wavelengths is None or intensities is None:
            try:
                local_wavelengths, local_intensities = self.connected_spectrometers[index].chart_queue.get()
            except Exception:
                self.notification(f"No data to save", color="#8e0101")
                return
            wavelengths_to_write = local_wavelengths
            intensities_to_write = local_intensities
        else:
            wavelengths_to_write = wavelengths
            intensities_to_write = intensities
        if wavelengths_to_write is not None and intensities_to_write is not None:
            
            if file_path:
                try:
                    # ensure directory exists
                    directory = os.path.dirname(file_path)
                    if directory:
                        os.makedirs(directory, exist_ok=True)
                    with open(file_path, mode='w', newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow(['Wavelength [nm]', ' Intensity [counts]'])
                        writer.writerow(['>>>>>Begin Spectral Data<<<<<'])
                        writer.writerows(zip(wavelengths_to_write, intensities_to_write))
                        
                    if self.reflectance_mode and not reference:
                        denominator = self.light_reference_intensities[index] - self.dark_reference_intensities[index]
                        denominator = numpy.where(denominator == 0, numpy.nan, denominator)
                        intensities = (intensities - self.dark_reference_intensities[index]) / denominator * 100
                        directory, filename = os.path.split(file_path)
                        file_path = f"{directory}/relative_{filename}"
                        with open(file_path, mode='w', newline='') as file:
                            writer = csv.writer(file)
                            writer.writerow(['Wavelength [nm]', ' Relative intensity [%]'])
                            writer.writerow(['>>>>>Begin Spectral Data<<<<<'])
                            writer.writerows(zip(wavelengths_to_write, intensities_to_write))
                    if single_save and display_notification:
                        self.notification(f"Successfully saved as", file_path, "#1a8300", path=file_path)
                        print(f"Data saved successfully to {file_path}")
                except Exception as e:
                    print(f"Error saving data: {e}")
                    self.notification(f"Impossible to save as", file_path, "#8e0101")
            else:
                self.notification(f"No directory to save", color="#8e0101")
        else:
            self.notification(f"No data to save", color="#8e0101")
    
    
    #Brought back
    def advanced_save(self):
        """Handles the advanced save process for spectrometer data.
        Waits briefly to ensure the spectrometer is initialized with the correct integration time. 
        Then, for the number of iterations requested by the user, it waits for new data to arrive and saves it accordingly.
        """

        time.sleep((self.acquisition_time /1000) + 0.5)
        self.connected_spectrometers[self.split-1].save_queue.queue.clear()
        while self.backups_counts > 0:
            self.backups_counts -= 1
            self.wavelengthsList[self.split-1], self.intensitiesList[self.split-1] = self.connected_spectrometers[self.split-1].save_queue.get()
            file_name = self.file_path.replace("#", str(self.file_counts)).replace("@", f"{datetime.now():%H.%M.%S}").replace("$", self.connected_spectrometers[self.split-1].name.split("-")[-1])   
            self.save_data(file_name, single_save=False)
            self.file_counts += 1

        if self.stop_after_saves:
            self.stop_spectrometer()
        self.notification(f"Serial backup completed !", color="#1a8300")
        self.thread_finish = True

    def advanced_save_popup(self):
        """Displays the advanced save popup.
        Allows users to configure a data backup sequence
        """
        if not self.popup:
            self.popup = CTkToplevel(self)
            self.popup.title("Spectrometer - Advanced save")
            self.popup.minsize(405, 330)
            self.center_popup(600, 400)
            self.popup.grid_rowconfigure((1,2,3,4,5,6), weight=1)
            self.popup.grid_columnconfigure((0,1), weight=1)
            self.popup.protocol("WM_DELETE_WINDOW", self.close_popup)
            self.popup.attributes("-topmost", True)
            self.after(50, lambda: self.popup.attributes("-topmost", False))

            time = f"{datetime.now():%Y%m%d_%H.%M.%S}"
            acq = (self.connected_spectrometers[self.split-1].integration_time or 100000) /1000
            self.backup_name = self.backup_name or self.master.directory_frame.spectrometer_backup_name.get()

            title = CTkLabel(self.popup, text="Please define your backup settings :", font=("Arial", 20))
            title.grid(row=0, column=0, padx=(40,0), pady=(30,20), sticky="w", columnspan=2)

            frame = CTkFrame(self.popup, fg_color="transparent")
            frame.grid(row=1, column=0, sticky="nsew", columnspan=2)
            CTkLabel(frame, text="File name :").pack(side="left", padx=(40,0))
            name = self.connected_spectrometers[self.split-1].name.split("-")[-1]
            if self.backup_name:
                self.backup_name_entry = CTkEntry(frame, placeholder_text=f"Spectrum_n°_{name}__{time}_{acq}ms",textvariable=StringVar(value=self.backup_name))
            else:
                self.backup_name_entry = CTkEntry(frame, placeholder_text=f"Spectrum_n°_{name}__{time}_{acq}ms")
            self.backup_name_entry.pack(side="left", fill="x", expand=True, padx=(20,40))

            frame = CTkFrame(self.popup, fg_color="transparent")
            frame.grid(row=2, column=0, sticky="nsew", columnspan=2)
            CTkLabel(frame, text="Acquisition time :").pack(side="left", padx=(40,20))
            self.acquisition_time_entry = CTkEntry(frame, placeholder_text="100.0", textvariable=StringVar(value=acq))
            self.acquisition_time_entry.pack(side="left")
            CTkLabel(frame, text="ms").pack(side="left", padx=5)

            frame = CTkFrame(self.popup, fg_color="transparent")
            frame.grid(row=3, column=0, sticky="nsew", columnspan=2)
            CTkLabel(frame, text="Number of files to save :").pack(side="left", padx=(40,10))
            CTkButton(frame, text="-", width=10, fg_color="transparent", command=lambda: self.increment_entry("-",self.backups_counts_entry)).pack(side="left")
            self.backups_counts_entry = CTkEntry(frame, width=100, placeholder_text="10", textvariable=StringVar(value=self.backups_counts_memorie))
            self.backups_counts_entry.pack(side="left", padx=1)
            CTkButton(frame, text="+", width=10, fg_color="transparent", command=lambda: self.increment_entry("+",self.backups_counts_entry)).pack(side="left")
            CTkLabel(frame, text="files").pack(side="left", padx=5)

            frame = CTkFrame(self.popup, fg_color="transparent")
            frame.grid(row=4, column=0, sticky="nsew", columnspan=2)
            CTkLabel(frame, text="Save every").pack(side="left", padx=(40,5))
            CTkButton(frame, text="-", width=10, fg_color="transparent", command=lambda: self.increment_entry("-",self.save_frequency_entry)).pack(side="left")
            self.save_frequency_entry = CTkEntry(frame, width=100, placeholder_text="1", textvariable=StringVar(value=self.save_frequency))
            self.save_frequency_entry.pack(side="left")      
            CTkButton(frame, text="+", width=10, fg_color="transparent", command=lambda: self.increment_entry("+",self.save_frequency_entry)).pack(side="left")
            CTkLabel(frame, text="scan").pack(side="left", padx=5)

            frame = CTkFrame(self.popup, fg_color="transparent")
            frame.grid(row=5, column=0, sticky="nsew", columnspan=2)
            self.light_reference_entry = CTkCheckBox(frame, text="Light reference", border_width=2, border_color="#1F6AA5")
            self.light_reference_entry.pack(side="left", padx=40)
            self.dark_reference_entry = CTkCheckBox(frame, text="Dark reference", border_width=2, border_color="#1F6AA5")
            self.dark_reference_entry.pack(side="left", padx=0)
            if self.light_reference:
                self.light_reference_entry.select()
            elif self.light_reference_intensities[self.split-1] is None:
                self.light_reference_entry.configure(state="disabled", border_color="gray45")
            if self.dark_reference:
                self.dark_reference_entry.select()
            elif self.dark_reference_intensities[self.split-1] is None:
                self.dark_reference_entry.configure(state="disabled", border_color="gray45")

            self.stop_after_saves_entry = CTkCheckBox(self.popup, text="Stop spectrometer after saves", border_width=2, border_color="#1F6AA5")
            self.stop_after_saves_entry.grid(row=6, column=0, padx=40, sticky="nsew", columnspan=2)
            if self.stop_after_saves: self.stop_after_saves_entry.select()
            CTkButton(self.popup, text="Cancel", fg_color="transparent", border_width=2, border_color="#1F6AA5", command=self.close_popup).grid(row=7, column=0, padx=(40,20), pady=20, sticky="ew")
            CTkButton(self.popup, text="Save", command=self.start_save_thread).grid(row=7, column=1, padx=(20,40), pady=20, sticky="ew")

        self.popup.focus_force()


    def increment_entry(self, operator, entry):
        """Adjusts the value in a given entry field by incrementing or decrementing it.
        Returns a notification if the entry value is not a positive integer

        Parameters
        ------------
        operator : `str`
            Increments field value if “+” or decrements if “-”
        entry : `CTkEntry`
            User-modifiable field
        """
        try:
            val = int(entry.get())
            if operator == "+":
                val += 1
            elif operator == "-" and val > 1:
                val -= 1
            entry.configure(textvariable=StringVar(value=val))
        except:
            self.notification(f"Must be a positive integer", color="#8e0101")


    def center_popup(self, width, height):
        """Centers the popup window in the main window

        Parameters
        ------------
        width : `int`
            Popup width
        height : `int`
            Popup height
        """
        x = int((self.master.winfo_width()/2) + self.master.winfo_x() - (width/2))
        y = int((self.master.winfo_height()/2) + self.master.winfo_y() - (height/2))
        self.popup.geometry(f"{width}x{height}+{x}+{y}")


    def close_popup(self):
        """Closes the settings popup cleanly
        """
        if self.popup:
            self.popup.destroy()
            self.popup = None
    

    def is_thread_finished(self):
        """Checks every 500ms if the advanced save thread is finished. 
        If so, then the advanced save popup is cleanly closed
        """
        if self.thread_finish:
            self.connected_spectrometers[self.split-1].acquire_save_data = 0
            self.close_popup()
        else:
            self.after(500, self.is_thread_finished)
    
    ##Not in use anymore
    def start_save_thread(self):
        """Checks that all fields entered by the user are correct. 
        If so, initialize and start the advanced save thread
        """
        if not self.check_acquisition_time(): return
        if not self.check_backups_counts(): return
        if not self.check_save_frequency(): return

        self.thread_finish = False
        self.backup_name = self.backup_name_entry.get()
        self.stop_after_saves = self.stop_after_saves_entry.get()
        self.light_reference = self.light_reference_entry.get()
        self.dark_reference = self.dark_reference_entry.get()
        self.connected_spectrometers[self.split-1].acquire_save_data = self.save_frequency
        self.connected_spectrometers[self.split-1].set_integration_time(self.acquisition_time *1000)
        self.file_path = self.file_system.get_spectrometer_directory(self.connected_spectrometers[self.split-1].integration_time, self.connected_spectrometers[self.split-1].name, self.backup_name_entry.get())
        self.file_counts = self.file_system.get_max_spectrum_number()

        self.popup.withdraw()
        reference_path = os.path.dirname(self.file_path)
        end_file = f"_{self.backup_name}_{str(self.file_counts)}_{self.connected_spectrometers[self.split-1].name.split('-')[-1]}__{datetime.now():%Y%m%d_%H.%M.%S}_{self.acquisition_time}ms.txt"
        if self.light_reference:
            name = f"reference{end_file}" 
            self.save_data(f"{reference_path}/{name}", self.light_reference_wavelengths[self.split-1], self.light_reference_intensities[self.split-1], False, True)
            if self.light_ref_acquisition_time != self.connected_spectrometers[self.split-1].integration_time:
                self.notification(f"Light reference acquisition time differs from current", color="#e17e00")
        if self.dark_reference:
            name = f"dark{end_file}" 
            self.save_data(f"{reference_path}/{name}", self.dark_reference_wavelengths[self.split-1], self.dark_reference_intensities[self.split-1], False, True)
            if self.dark_ref_acquisition_time != self.connected_spectrometers[self.split-1].integration_time:
                self.notification(f"Dark reference acquisition time differs from current", color="#e17e00")

        if not self.connected_spectrometers[self.split-1].is_running: self.start_spectrometer()
        self.notification(f"Serial backup has begun...", color="#006bd2")
        self.save_thread = threading.Thread(target=self.advanced_save, daemon=True)
        self.save_thread.start()
        self.is_thread_finished()


    def check_acquisition_time(self):
        """Checks the validity of content entered by users before using it.
        If the content is inappropriate, an error notification is sent to the user

        Note that the acquisition time must be a positive float between 8 and 1600000
        
        Returns
        ------------
        check_acquisition_time : `bool`
            Whether or not valid
        """
        try:
            self.acquisition_time = float(self.acquisition_time_entry.get())
            if 8 <= self.acquisition_time <= 1600000:
                return True
            else:
                self.notification(f"Integration time must be between 8 ms and 1600000 ms", color="#8e0101")
                return False
        except:
            self.notification(f"Integration time must be a number", color="#8e0101")
            return False


    def check_backups_counts(self):
        """Checks the validity of content entered by users before using it.
        If the content is inappropriate, an error notification is sent to the user

        Note that the backups counts must be a positive integer
        
        Returns
        ------------
        check_backups_counts : `bool`
            Whether or not valid
        """
        try:
            self.backups_counts = int(self.backups_counts_entry.get())
            self.backups_counts_memorie = self.backups_counts
            result = self.backups_counts > 0
            if not result:
                self.notification(f"The number of backups must be higher than 0", color="#8e0101")
            return result
        except:
            self.notification(f"The number of backups must be an integer", color="#8e0101")
            return False


    def check_save_frequency(self):
        """Checks the validity of content entered by users before using it.
        If the content is inappropriate, an error notification is sent to the user

        Note that the save frequency must be a positive integer
        
        Returns
        ------------
        check_save_frequency : `bool`
            Whether or not valid
        """
        try:
            self.save_frequency = int(self.save_frequency_entry.get())
            result = self.save_frequency > 0
            if not result:
                self.notification(f"The number of scan must be higher than 0", color="#8e0101")
            return result
        except:
            self.notification(f"The number of scan must be an integer", color="#8e0101")
            return False


    def set_light_reference(self):
        """Stores light reference data
        """
        for i in range(len(self.connected_spectrometers)):
            try:
                wave, inten = self.connected_spectrometers[i].chart_queue.get(timeout=5)
            except Exception as e:
                debugp("SetLightRef", f"No data available from spectrometer {i}: {e}")
                self.notification(f"No spectrometer data for light reference", color="#8e0101")
                continue

            self.light_reference_wavelengths[i] = wave.copy()
            self.light_reference_intensities[i] = inten.copy()
            self.light_ref_acquisition_time[i] = self.connected_spectrometers[i].integration_time

            if self.light_reference_intensities[i] is not None:
                self.light_reference = True
                # Save light reference into the current experiment folder under "LightReferences/<spec_name>/"
                spec_name = self.connected_spectrometers[i].name.split("-")[-1]
                ref_dir = self.file_system.get_calibration_directory("LightReferences")
                spec_dir = os.path.join(ref_dir, spec_name)
                try:
                    os.makedirs(spec_dir, exist_ok=True)
                    file_name = f"light_{i}__{datetime.now():%Y%m%d_%H.%M.%S}_{self.connected_spectrometers[i].integration_time}ms.txt"
                    file_path = os.path.join(spec_dir, file_name)
                    self.single_save(file_path, self.light_reference_wavelengths[i], self.light_reference_intensities[i], True, True, i)
                    debugp("SetLightRef", f"Saved light reference to {file_path}")
                except Exception as e:
                    debugp("SetLightRef", f"Failed saving light reference: {e}")
                    self.notification(f"Failed to save light reference: {e}", color="#8e0101")
                self.notification(f"Light reference successfully recorded", color="#1a8300")
            else:
                self.light_reference = False
                self.notification(f"There is no data to save for the light reference", color="#8e0101")


    def set_dark_reference(self, display_notification=True):
        """Stores dark reference data
        """
        saved_dirs = []
        for i in range(len(self.connected_spectrometers)):
            try:
                wave, inten = self.connected_spectrometers[i].chart_queue.get(timeout=5)
            except Exception as e:
                debugp("SetDarkRef", f"No data available from spectrometer {i}: {e}")
                self.notification(f"No spectrometer data for dark reference", color="#8e0101")
                continue

            self.dark_reference_wavelengths[i] = wave.copy()
            self.dark_reference_intensities[i] = inten.copy()
            self.dark_ref_acquisition_time[i] = self.connected_spectrometers[i].integration_time

            if self.dark_reference_intensities[i] is not None:
                self.dark_reference = True
                # Save dark reference into the current experiment folder under "DarkReferences/<spec_name>/"
                spec_name = self.connected_spectrometers[i].name.split("-")[-1]
                ref_dir = self.file_system.get_calibration_directory("DarkReferences")
                spec_dir = os.path.join(ref_dir, spec_name)
                try:
                    os.makedirs(spec_dir, exist_ok=True)
                    file_name = f"dark_{i}__{datetime.now():%Y%m%d_%H.%M.%S}_{self.connected_spectrometers[i].integration_time}ms.txt"
                    file_path = os.path.join(spec_dir, file_name)
                    # pass display_notification through so callers can suppress per-file notifications
                    self.single_save(file_path, self.dark_reference_wavelengths[i], self.dark_reference_intensities[i], True, True, i, display_notification)
                    debugp("SetDarkRef", f"Saved dark reference to {file_path}")
                    saved_dirs.append(spec_dir)
                except Exception as e:
                    debugp("SetDarkRef", f"Failed saving dark reference: {e}")
                    if display_notification:
                        self.notification(f"Failed to save dark reference: {e}", color="#8e0101")
                if display_notification:
                    self.notification(f"Dark reference successfully recorded", color="#1a8300")
            else:
                self.dark_reference = False
                self.notification(f"There is no data to save for the dark reference", color="#8e0101")
        # return list of directories where dark references were stored (may be empty)
        return saved_dirs



    def import_chart(self):
        """Overloads the graph with data imported by users. 
        Adjusts axis titles according to the display mode selected. 
        Displays file names in the legend in a simplified version
        """
        
        file_paths = filedialog.askopenfilenames(initialdir=self.file_system.get_backup_directory() ,filetypes=[("CSV and TXT files", "*.csv *.txt"), ("CSV files", "*.csv"), ("Text files", "*.txt")])

        self.stop_spectrometer()
        if file_paths:
            if self.image_view_enabled and self.supports_image_view():
                self.image_view_enabled = False

            if len(self.plot.lines) == 1 or self.supports_image_view():
                self.render_cached_plot()
                if self.plot.lines:
                    self.plot.lines[0].set_label("Current")
            
            for file_path in file_paths:
                x, y = [], []
            
                if file_path.endswith(".csv"):
                    with open(file_path, newline='') as file:
                        reader = csv.reader(file)
                        next(reader)
                        for row in reader:
                            x.append(float(row[0]))
                            y.append(float(row[1]))
                
                else:
                    with open(file_path, 'r') as file:
                        for line in file:
                            if line.strip() == ">>>>>Begin Spectral Data<<<<<":
                                break
                        
                        for line in file:
                            parts = line.strip().split(',')
                            if len(parts) == 2: 
                                x.append(float(parts[0]))
                                y.append(float(parts[1]))


                legend = os.path.basename(file_path).split('__')[0]
                self.plot.plot(x, y, label=legend)

            self.plot.legend()
            self.canvas.draw()

# Could be implemented in the future
    def extend(self):
        """Not available.
        The purpose of this method is to open the spectrometer frame in a 
        new window in order to have a larger view of the spectrometer graph
        """
        self.notification(f"Coming soon !", color="#006bd2")

    def notification(self, head_message=None, message=None, color=None, path=""):
        """Creates notifications attached to the main window. 

        Parameters
        ------------
        head_message : `str`, optional
            Main content. None by default
        message : `str`, optional
            Sub-content used to display the path of the last saved file. None by default
        color : `str`, optional
            Notification border color. Grey by default
        """
        self.master.notification(head_message, message, color, path)

    def on_closing(self):
        """Stops the current thread and disconnects the spectrometer cleanly
        """
        for spec in getattr(self, 'connected_spectrometers', []):
            if spec:
                self.backups_counts = 0
                time.sleep(0.2)
                spec.disconnect()
            
            
    def toggle_split_screen(self):
        if self.supports_image_view():
            self.image_view_enabled = not self.image_view_enabled
            self.view_button.configure(image=img_split_right if self.image_view_enabled else img_split_left)
            self.render_cached_plot()
            return

        self.split = ((self.split ) % 2) + 1

        debugp("spec", "Split:" + str(self.split))
        self.plot.cla()
        
        if self.split == 0:
            self.view_button.configure(image=img_split)
        elif self.split == 1:
            self.view_button.configure(image=img_split_left)
        else:
            self.view_button.configure(image=img_split_right)
            
    def add_experiment(self):
        self.file_system.new_spectrometer_experiment()
        
    def set_unavailable(self, message):
        self.is_disabled = True
        self.toggle_features("disabled")

        if self.unavailable_message_label:
            self.unavailable_message_label.configure(text=message)
        else:
            # Create a rounded rectangle frame
            self.unavailable_message = CTkFrame(
                self, 
                corner_radius=0, 
                bg_color="transparent",
                width=300,  # Adjust width to fit text + padding
                height=150  # Adjust height to fit text + padding
            )  
            self.unavailable_message.place(relx=0.5, rely=0.5, anchor="center")  

            # Create a label inside the frame
            self.unavailable_message_label = CTkLabel(
                self.unavailable_message, 
                text=message, 
                font=("Arial", 34), 
                bg_color="transparent",
                fg_color="transparent"
            )
            self.unavailable_message_label.pack(padx=20, pady=20)
        
        
    def set_available(self):
        if self.unavailable_message:
            self.is_disabled = False
            self.unavailable_message.destroy()
            self.unavailable_message_label = None
            self.toggle_features("normal")
            print("Set enabled")
            
    def toggle_features(self, state):
        self.kymera_controls_enabled = state == "normal"
        
        if hasattr(self, 'view_button') and self.view_button:
            self.view_button.configure(state=state)
        self.fullscreen_button.configure(state=state)
        self.import_button.configure(state=state)
        self.light_reference_button.configure(state=state)
        self.dark_reference_button.configure(state=state)
        self.pause_button.configure(state=state)
        self.play_button.configure(state=state)
        self.save_button.configure(state=state)
        self.adv_save_button.configure(state=state)
        self.reflectance_data_button.configure(state=state)
        self.raw_data_button.configure(state=state)
        self.new_experiment_button.configure(state=state)

        for button in self.read_mode_buttons.values():
            try:
                button.configure(state=state)
            except Exception:
                pass

        for widget in self.kymera_control_widgets:
            try:
                widget.configure(state=state)
            except Exception:
                pass

        if self.supports_image_view():
            self.refresh_kymera_controls()
    
    def update_live_temperature_controls(self, device=None, temperature_state=None, auto_start=True):
        if self.signal_recording_active or getattr(self, "routine_active", False):
            return

        device = device or self.get_active_spectrometer()
        if not self.supports_image_view(device):
            return

        if temperature_state is None:
            try:
                temperature_state, _temperature = device.get_temperature_state()
            except Exception:
                temperature_state = "unavailable"

        ready = temperature_state in ("reached", "unavailable")
        watched_widgets = (
            getattr(self, "play_button", None),
            getattr(self, "pause_button", None),
            getattr(self, "save_button", None),
        )

        if ready:
            for widget in watched_widgets:
                if widget:
                    widget.configure(state="normal")
            if (
                device in self.connected_spectrometers
                and not getattr(device, "is_running", False)
                and not self._user_paused_live
                and auto_start
            ):
                self.start_spectrometer(device, user_initiated=False)
        else:
            if getattr(device, "is_running", False):
                self.stop_spectrometer(user_initiated=False)
            for widget in watched_widgets:
                if widget:
                    widget.configure(state="disabled")
            if getattr(self, "play_button", None):
                self.play_button.lift()


    def update_temperature(self):

        if self.temperature_display:
            text_color = "white"
            if len(self.connected_spectrometers) == 0:
                self.temperature_display.configure(text="∅", text_color=text_color)
            else:
                device = self.connected_spectrometers[self.split-1]
                temp = None
                if hasattr(device, "get_temperature_state"):
                    state, temp = device.get_temperature_state()
                    if state == "reached":
                        text_color = "#22c55e"   # green
                    elif state == "warming":
                        text_color = "#ef4444"   # red
                    elif state == "off":
                        text_color = "#f59e0b"   # amber - cooler off
                    else:
                        text_color = "gray60"
                else:
                    temp = device.get_temperature()

                if isinstance(temp, (int, float)) and temp == temp:  # not NaN
                    self.temperature_display.configure(text=f"{round(temp,3)}°c", text_color=text_color)
                else:
                    self.temperature_display.configure(text="∅", text_color=text_color)
                self.update_live_temperature_controls(device, state if hasattr(device, "get_temperature_state") else "unavailable")

        self.after(1000, self.update_temperature)
