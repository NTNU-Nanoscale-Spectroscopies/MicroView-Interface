"""Power-meter display frame.

Provides a collapsible settings sidebar, a live matplotlib graph of
power vs. time, and a bottom information bar showing the most recent
power value, sample count and configured wavelength.

Toolbar buttons
---------------
* **Save**       – export the current data buffer to a CSV file.
* **Record** (●) – start a timed / sample-limited recording.
* **Play/Pause** – pause / resume the live data display.
* **Stop** (■)   – stop an active recording early.
* **Reset** (↻)  – clear all data and reset the graph.

Sidebar settings
----------------
* Wavelength, Auto Range, Range, Live window, Recording window,
  Zero Adjust.
"""

from dev.debugHelp import debugp
from ..images.images import *
from .notification import *

from customtkinter import *
from CTkToolTip import *
from tkinter import StringVar, IntVar
from tkinter import simpledialog

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from datetime import datetime
from collections import deque
import csv
import json
import os
import re
import numpy as np
import matplotlib
import matplotlib.pyplot as plt


class PowerMeterFrame(CTkFrame):
    """Frame for displaying and controlling a power meter device.

    Layout
    ------
    +--sidebar--+--------main area--------+
    |  settings | Save | Rec Pl St Rs     |
    |           |        Graph            |
    |           |   Power (mW) vs Time    |
    |           +-------+-------+---------+
    |           | Power | Samp. | Wavelen |
    +-----------+-------+-------+---------+
    """

    def __init__(self, master, power_meters):
        super().__init__(master)

        # prevent internal size changes (e.g. sidebar collapse) from
        # propagating upward and resizing sibling panels
        self.grid_propagate(False)

        self.is_disabled = False
        self.unavailable_message_label = None
        self.file_system = master.file_system

        self.power_meter_count = len(power_meters) if power_meters else 0

        if not power_meters:
            self.grid_columnconfigure(0, weight=1)
            self.grid_rowconfigure(0, weight=1)
            self.label = CTkLabel(self, text="No power meter", font=("Arial", 25))
            self.label.grid(row=0, column=0, padx=5, pady=5)
        else:
            self.power_meters = power_meters
            self.init()

    # ------------------------------------------------------------------
    # UI initialisation
    # ------------------------------------------------------------------

    def init(self):
        """Build (or rebuild) the full UI."""
        for w in self.winfo_children():
            w.destroy()

        # 2-column grid: sidebar (fixed width) | main area (stretches)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)  # sidebar
        self.grid_columnconfigure(1, weight=1)   # main area

        # --- Sidebar (always in the grid, collapse changes its width) ---
        self.sidebar_visible = True
        self._build_sidebar()

        # --- Main content area ---
        self._build_main_area()

        # Start in disconnected state: hide sidebar & main content,
        # show only the disconnected overlay.  connect() will reveal them.
        self.sidebar.grid_remove()
        self.main_area.grid_remove()
        self._disconnected_overlay = CTkFrame(self, fg_color="transparent")
        self._disconnected_overlay.grid(row=0, column=0, columnspan=2, sticky="nsew")
        self._disconnected_overlay.grid_rowconfigure(0, weight=1)
        self._disconnected_overlay.grid_columnconfigure(0, weight=1)
        self.disconnected_label = CTkLabel(self._disconnected_overlay, text="Disconnected", font=("Arial", 25))
        self.disconnected_label.grid(row=0, column=0, padx=5, pady=5)
        self.disconnected_button = CTkButton(
            self._disconnected_overlay, text="", width=30, height=40,
            image=img_retry, fg_color="transparent",
            command=self.reconnection,
        )
        self.disconnected_button.grid(row=0, column=0, pady=(60, 0))

        # internal state
        self.time_data: deque = deque(maxlen=10_000)
        self.power_data: deque = deque(maxlen=10_000)
        self.sample_count = 0
        self.start_time = None
        self._zero_offset = 0.0
        self._update_id = None
        self._line = None  # matplotlib Line2D for efficient updates
        self.connected_device = None
        self.popup = None
        self._paused = False  # live display pause state
        self._paused_at = None     # datetime when pause started
        self._paused_total = 0.0   # total seconds spent paused

        # recording state
        self._recording = False
        self._rec_time_data: list = []
        self._rec_power_data: list = []
        self._rec_start_time = None
        self._rec_limit = None       # seconds or sample count
        self._rec_mode = "Time"      # "Time" or "Samples"

        # pulsating recording overlay state
        self._rec_overlay = None       # CTkFrame overlay widget
        self._rec_overlay_label = None # CTkLabel inside overlay
        self._rec_pulse_id = None      # after() id for pulse animation
        self._rec_pulse_on = True      # current pulse state (visible toggle)

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    _SIDEBAR_EXPANDED = 200
    _SIDEBAR_COLLAPSED = 25

    def _build_sidebar(self):
        self.sidebar = CTkFrame(self, width=self._SIDEBAR_EXPANDED)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)   # don't let grid children override size
        self.sidebar.pack_propagate(False)   # don't let packed children override size

        # collapse / expand button — placed on the right edge, vertically centred
        self.collapse_btn = CTkButton(
            self.sidebar, text="<<", width=20, height=40,
            fg_color="transparent", command=self.toggle_sidebar,
        )
        self.collapse_btn.place(relx=1.0, rely=0.5, anchor="e", x=-2)

        # scrollable interior that fills the full sidebar height
        self.sidebar_content = CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.sidebar_content.pack(fill="both", expand=True, pady=(10, 0), padx=(0, 22))

        sc = self.sidebar_content  # shorthand

        CTkLabel(sc, text="Device Settings", font=("Arial", 16, "bold")).pack(
            anchor="w", padx=10, pady=(5, 10))

        # --- Wavelength ---
        CTkLabel(sc, text="Wavelength").pack(anchor="w", padx=10)
        self.wavelengths = self._load_wavelengths()
        self.wl_var = StringVar(value=self.wavelengths[0])
        self.wl_menu = CTkOptionMenu(
            sc, values=self.wavelengths, variable=self.wl_var,
            command=self._on_wavelength_changed,
        )
        self.wl_menu.pack(fill="x", padx=10, pady=2)

        # --- Auto Range ---
        self.auto_range_var = IntVar(value=1)
        CTkLabel(sc, text="Auto Range").pack(anchor="w", padx=10, pady=(10, 0))
        CTkSwitch(sc, text="", variable=self.auto_range_var,
                  command=self._on_auto_range_changed).pack(anchor="w", padx=10, pady=2)

        # --- Range ---
        CTkLabel(sc, text="Range").pack(anchor="w", padx=10, pady=(10, 0))
        self.range_var = StringVar(value="Auto")
        self._range_values_W = {}  # {"label": watts}  — populated on connect
        self.range_menu = CTkOptionMenu(
            sc, values=["Auto"], variable=self.range_var,
            command=self._on_range_changed)
        self.range_menu.pack(fill="x", padx=10, pady=2)

        # --- Live (graph x-axis span) ---
        CTkLabel(sc, text="Live").pack(anchor="w", padx=10, pady=(10, 0))
        live_frame = CTkFrame(sc, fg_color="transparent")
        live_frame.pack(fill="x", padx=10, pady=2)
        self.live_mode_var = StringVar(value="Time")
        CTkOptionMenu(
            live_frame, values=["Time", "Samples"],
            variable=self.live_mode_var, width=80,
            command=self._on_live_mode_changed,
        ).pack(side="left")
        self.live_value_entry = CTkEntry(live_frame, width=55)
        self.live_value_entry.pack(side="left", padx=(5, 0))
        self.live_value_entry.insert(0, "15")
        self.live_unit_label = CTkLabel(live_frame, text="s", width=15)
        self.live_unit_label.pack(side="left")

        # --- Recording (capture window) ---
        CTkLabel(sc, text="Recording").pack(anchor="w", padx=10, pady=(10, 0))
        rec_frame = CTkFrame(sc, fg_color="transparent")
        rec_frame.pack(fill="x", padx=10, pady=2)
        self.rec_mode_var = StringVar(value="Time")
        CTkOptionMenu(
            rec_frame, values=["Time", "Samples"],
            variable=self.rec_mode_var, width=80,
            command=self._on_rec_mode_changed,
        ).pack(side="left")
        self.rec_value_entry = CTkEntry(rec_frame, width=55)
        self.rec_value_entry.pack(side="left", padx=(5, 0))
        self.rec_value_entry.insert(0, "15")
        self.rec_unit_label = CTkLabel(rec_frame, text="s", width=15)
        self.rec_unit_label.pack(side="left")

        # --- Zero Adjust ---
        CTkLabel(sc, text="Zero Adjust").pack(anchor="w", padx=10, pady=(10, 0))
        zero_frame = CTkFrame(sc, fg_color="transparent")
        zero_frame.pack(fill="x", padx=10, pady=2)
        self.zero_entry = CTkEntry(zero_frame, width=80, state="readonly")
        self.zero_entry.pack(side="left")
        CTkButton(zero_frame, text="Zero", width=50,
                  command=self._zero_adjust).pack(side="left", padx=5)

    # ------------------------------------------------------------------
    # Main area (graph + info bar)
    # ------------------------------------------------------------------

    def _build_main_area(self):
        main = CTkFrame(self, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew")
        main.grid_rowconfigure(0, weight=0)   # toolbar
        main.grid_rowconfigure(1, weight=1)   # graph
        main.grid_rowconfigure(2, weight=0)   # info bar
        main.grid_columnconfigure(0, weight=1)
        self.main_area = main

        # --- Top toolbar ---
        self._build_toolbar(main)

        # --- Matplotlib figure ---
        self.figure = Figure(figsize=(6, 4), dpi=100)
        self.figure.patch.set_facecolor("#2b2b2b")
        self.ax = self.figure.add_subplot(111)
        self._style_axes()

        self.canvas = FigureCanvasTkAgg(self.figure, master=main)
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # --- Info bar (fixed-height cells to prevent jitter) ---
        info = CTkFrame(main, height=80)
        info.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 5))
        info.grid_propagate(False)
        info.grid_columnconfigure((0, 1, 2), weight=1, uniform="info")
        info.grid_rowconfigure(0, weight=1)

        # power
        pf = CTkFrame(info)
        pf.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        pf.pack_propagate(False)
        CTkLabel(pf, text="Most Recent Value", font=("Arial", 12)).pack(pady=(8, 0))
        self.power_display = CTkLabel(pf, text="--- mW", font=("Arial", 28, "bold"))
        self.power_display.pack(pady=(0, 8), expand=True)

        # samples
        sf = CTkFrame(info)
        sf.grid(row=0, column=1, sticky="nsew", padx=2, pady=2)
        sf.pack_propagate(False)
        CTkLabel(sf, text="Samples", font=("Arial", 12)).pack(pady=(8, 0))
        self.samples_display = CTkLabel(sf, text="0", font=("Arial", 28, "bold"))
        self.samples_display.pack(pady=(0, 8), expand=True)

        # wavelength
        wf = CTkFrame(info)
        wf.grid(row=0, column=2, sticky="nsew", padx=2, pady=2)
        wf.pack_propagate(False)
        CTkLabel(wf, text="Wavelength", font=("Arial", 12)).pack(pady=(8, 0))
        self.wl_display = CTkLabel(wf, text="785 nm", font=("Arial", 28, "bold"))
        self.wl_display.pack(pady=(0, 8), expand=True)



    def _build_toolbar(self, parent):
        """Build the thin top toolbar: save (left), record/play-pause/stop/reset (centred)."""
        tb = CTkFrame(parent, height=36)
        tb.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
        tb.grid_propagate(False)
        tb.grid_columnconfigure(0, weight=0)  # save
        tb.grid_columnconfigure(1, weight=1)  # centre spacer
        tb.grid_columnconfigure(2, weight=0)  # button group
        tb.grid_columnconfigure(3, weight=1)  # centre spacer
        tb.grid_rowconfigure(0, weight=1)

        # --- Left: Save ---
        self.save_btn = CTkButton(
            tb, text="", image=img_save, width=30, height=28,
            fg_color="transparent", command=self._on_save,
        )
        self.save_btn.grid(row=0, column=0, padx=(4, 0), sticky="w")

        # --- Centre: transport controls ---
        grp = CTkFrame(tb, fg_color="transparent")
        grp.grid(row=0, column=2, sticky="")

        self.record_btn = CTkButton(
            grp, text="\u25cf", width=30, height=28,
            fg_color="transparent", text_color="#FF4444",
            font=("Arial", 16),
            command=self._on_record,
        )
        self.record_btn.pack(side="left", padx=2)

        self.play_pause_btn = CTkButton(
            grp, text="", image=img_pause, width=30, height=28,
            fg_color="transparent",
            command=self._on_play_pause,
        )
        self.play_pause_btn.pack(side="left", padx=2)

        self.stop_btn = CTkButton(
            grp, text="\u25a0", width=30, height=28,
            fg_color="transparent",
            font=("Arial", 16),
            command=self._on_stop,
        )
        self.stop_btn.pack(side="left", padx=2)

        self.reset_btn = CTkButton(
            grp, text="\u21bb", width=30, height=28,
            fg_color="transparent",
            font=("Arial", 16),
            command=self._on_reset,
        )
        self.reset_btn.pack(side="left", padx=2)

    # ------------------------------------------------------------------
    # Sidebar callbacks
    # ------------------------------------------------------------------

    def toggle_sidebar(self):
        if self.sidebar_visible:
            self.sidebar.configure(width=self._SIDEBAR_COLLAPSED)
            self.collapse_btn.configure(text=">>")
            self.sidebar_visible = False
        else:
            self.sidebar.configure(width=self._SIDEBAR_EXPANDED)
            self.collapse_btn.configure(text="<<")
            self.sidebar_visible = True

    def _on_wavelength_changed(self, val):
        if val == "Custom":
            custom = simpledialog.askstring(
                "Wavelength", "Enter wavelength (nm)", parent=self)
            if custom:
                if custom not in self.wavelengths:
                    self.wavelengths.insert(len(self.wavelengths) - 1, custom)
                    self.wl_menu.configure(values=self.wavelengths)
                self.wl_var.set(custom)
                val = custom
                self._save_wavelengths()
            else:
                self.wl_var.set(self.wavelengths[0] if self.wavelengths else "785")
                return
        self.wl_display.configure(text=f"{val} nm")
        if self.connected_device and hasattr(self.connected_device, "set_wavelength"):
            try:
                self.connected_device.set_wavelength(int(val))
            except (ValueError, TypeError):
                pass

    def _on_auto_range_changed(self):
        enabled = bool(self.auto_range_var.get())
        if self.connected_device and hasattr(self.connected_device, "set_auto_range"):
            self.connected_device.set_auto_range(enabled)
        if enabled:
            self.range_var.set("Auto")

    def _on_range_changed(self, val):
        if val == "Auto":
            self.auto_range_var.set(1)
            self._on_auto_range_changed()
            return
        self.auto_range_var.set(0)
        watts = self._range_values_W.get(val)
        if watts is not None and self.connected_device and hasattr(self.connected_device, "set_power_range"):
            self.connected_device.set_power_range(watts)

    def _on_live_mode_changed(self, val):
        """Update the unit label next to the Live entry field."""
        self.live_unit_label.configure(text="s" if val == "Time" else "#")

    def _on_rec_mode_changed(self, val):
        """Update the unit label next to the Recording entry field."""
        self.rec_unit_label.configure(text="s" if val == "Time" else "#")

    def _populate_range_menu(self):
        """Build range dropdown values from the connected device."""
        ranges = {}
        if self.connected_device and hasattr(self.connected_device, "get_power_ranges"):
            bounds = self.connected_device.get_power_ranges()
            if bounds:
                min_W, max_W = bounds
                # build common ranges between min and max
                candidates = [
                    (1e-9, "1 nW"), (10e-9, "10 nW"), (100e-9, "100 nW"),
                    (1e-6, "1 µW"), (10e-6, "10 µW"), (100e-6, "100 µW"),
                    (1e-3, "1 mW"), (5e-3, "5 mW"), (10e-3, "10 mW"),
                    (50e-3, "50 mW"), (100e-3, "100 mW"), (150e-3, "150 mW"),
                    (500e-3, "500 mW"), (1.0, "1 W"), (2.4, "2.4 W"),
                    (5.0, "5 W"), (10.0, "10 W"),
                ]
                for watts, label in candidates:
                    if min_W <= watts <= max_W:
                        ranges[label] = watts
        if not ranges:
            # sensible defaults for PM16-401 (photodiode)
            ranges = {
                "100 µW": 100e-6,
                "1 mW": 1e-3,
                "10 mW": 10e-3,
                "100 mW": 100e-3,
                "500 mW": 500e-3,
            }
        self._range_values_W = ranges
        labels = ["Auto"] + list(ranges.keys())
        self.range_menu.configure(values=labels)
        if self.auto_range_var.get():
            self.range_var.set("Auto")

    def _zero_adjust(self):
        """Trigger hardware dark-adjust if available, else software offset."""
        if self.connected_device and hasattr(self.connected_device, "zero_adjust"):
            self.connected_device.zero_adjust()
            # poll until zeroing finishes, then read new offset
            self._poll_zero_state()
        else:
            # software zero
            if self.power_data:
                self._zero_offset = self.power_data[-1] + self._zero_offset
            self._show_zero_value(self._zero_offset, unit="mW")

    def _poll_zero_state(self):
        """Poll the device zero-adjust state; update display on completion."""
        if self.connected_device and hasattr(self.connected_device, "get_zero_state"):
            if self.connected_device.get_zero_state():
                self.zero_entry.configure(state="normal")
                self.zero_entry.delete(0, "end")
                self.zero_entry.insert(0, "zeroing…")
                self.zero_entry.configure(state="readonly")
                self.after(200, self._poll_zero_state)
                return
        # zeroing finished — read dark offset from device
        offset = 0.0
        if self.connected_device and hasattr(self.connected_device, "get_dark_offset"):
            offset = self.connected_device.get_dark_offset()
        self._zero_offset = 0.0  # hardware already applies offset
        self._show_zero_value(offset)

    @staticmethod
    def _format_si(value: float, unit: str = "W") -> str:
        """Format *value* (in base *unit*) with an appropriate SI prefix.

        Examples (unit="W"):
            0.005       -> "5.0000 mW"
            3.067e-07   -> "306.7000 nW"
        Examples (unit="A"):
            3.067e-07   -> "306.7000 nA"
        """
        abs_val = abs(value)
        if abs_val == 0:
            return f"0 {unit}"
        elif abs_val >= 1:
            return f"{value:.4f} {unit}"
        elif abs_val >= 1e-3:
            return f"{value * 1e3:.4f} m{unit}"
        elif abs_val >= 1e-6:
            return f"{value * 1e6:.4f} \u00b5{unit}"   # micro
        elif abs_val >= 1e-9:
            return f"{value * 1e9:.4f} n{unit}"
        else:
            return f"{value * 1e12:.4f} p{unit}"

    def _show_zero_value(self, value, unit: str = "W"):
        self.zero_entry.configure(state="normal")
        self.zero_entry.delete(0, "end")
        self.zero_entry.insert(0, self._format_si(value, unit))
        self.zero_entry.configure(state="readonly")

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def reconnection(self):
        self.master.quick_setup_frame.reconnection(self.power_meters[0])

    def connect(self, device):
        """Called by the setup frame to connect *device*.

        Returns ``True`` on success so the caller can update its switch.
        """
        print(f"[PowerMeterFrame] connect() called with device={device}, device.connected={device.connected}")
        if not device.connected:
            success = device.connect()
        else:
            success = True

        if not success:
            debugp("powermeter", f"failed to connect {device}")
            return False

        device.connected = True
        self.connected_device = device

        # hide disconnected overlay, show the real UI
        try:
            self._disconnected_overlay.destroy()
            self._disconnected_overlay = None
        except Exception:
            pass
        self.sidebar.grid()
        self.main_area.grid()

        # start acquisition if device supports it
        if hasattr(device, "start"):
            device.start()

        # reset data buffers
        self.time_data.clear()
        self.power_data.clear()
        self.sample_count = 0
        self.start_time = datetime.now()
        self._zero_offset = 0.0
        self._line = None  # force new Line2D on fresh axes

        # recording state
        self._recording = False
        self._rec_time_data = []
        self._rec_power_data = []

        # --- Sync sidebar controls from device state ---
        # wavelength
        if hasattr(device, "get_wavelength"):
            wl = device.get_wavelength()
            if wl is not None:
                wl_str = str(wl)
                if wl_str not in self.wavelengths:
                    self.wavelengths.insert(len(self.wavelengths) - 1, wl_str)
                    self.wl_menu.configure(values=self.wavelengths)
                self.wl_var.set(wl_str)
                self.wl_display.configure(text=f"{wl} nm")

        # auto-range
        if hasattr(device, "get_auto_range"):
            ar = device.get_auto_range()
            self.auto_range_var.set(1 if ar else 0)

        # populate range menu from device sensor spec
        self._populate_range_menu()

        self._paused = False
        self._paused_at = None
        self._paused_total = 0.0
        self.play_pause_btn.configure(image=img_pause)
        self.record_btn.configure(text_color="#FF4444")  # not recording

        # begin live graph updates
        self._start_update()
        return True

    def disconnect(self, device):
        """Cleanly stop acquisition, save any active recording, and reset the UI."""
        # stop active recording and save
        if self._recording:
            self._finish_recording()

        if device.connected:
            if hasattr(device, "stop"):
                device.stop()
            device.disconnect()
            device.connected = False

        self.connected_device = None
        self._stop_update()
        self.time_data.clear()
        self.power_data.clear()
        self.sample_count = 0

        # rebuild UI (will show disconnected state)
        self.init()

    # ------------------------------------------------------------------
    # Live graph updating
    # ------------------------------------------------------------------

    def _start_update(self):
        self._stop_update()
        self._update_graph()

    def _reset_and_start(self):
        """Clear stale data and restart the graph fresh.

        Called when the power-meter view becomes visible again after being
        hidden (e.g. switched to spectrometer view or window minimised).
        Prevents the graph from displaying a flat line for the hidden period.
        Respects the current pause state — if the user paused before
        switching away the graph stays paused when they come back.
        """
        self.time_data.clear()
        self.power_data.clear()
        self.sample_count = 0
        self.start_time = datetime.now()
        self._paused_total = 0.0
        if self._paused:
            self._paused_at = datetime.now()
        else:
            self._paused_at = None

        if self._line is not None:
            self._line.set_data([], [])
            self.ax.relim()
            self.ax.autoscale_view()
            self.canvas.draw_idle()
        self._line = None

        self.power_display.configure(text="--- mW")
        self.samples_display.configure(text="0")

        # keep whatever pause state the user set
        self._start_update()

    def _stop_update(self):
        if getattr(self, "_update_id", None):
            self.after_cancel(self._update_id)
            self._update_id = None

    def _update_graph(self):
        if not self.connected_device or not self.connected_device.connected:
            # device not (yet) ready – keep the loop alive so it picks
            # up the connection once it is established
            self._update_id = self.after(200, self._update_graph)
            return

        if self._paused:
            self._update_id = self.after(50, self._update_graph)
            return

        power = None
        if hasattr(self.connected_device, "get_power"):
            power = self.connected_device.get_power()

        if power is None:
            # occasionally log that we're polling but getting nothing
            if not hasattr(self, '_null_count'):
                self._null_count = 0
            self._null_count += 1
            if self._null_count % 40 == 1:  # every ~2 seconds at 50ms
                print(f"[PowerMeterFrame] get_power() returned None (count={self._null_count}, "
                      f"device.connected={self.connected_device.connected}, "
                      f"is_running={getattr(self.connected_device, 'is_running', '?')})")

        if power is not None:
            adjusted = power - self._zero_offset
            elapsed = (datetime.now() - self.start_time).total_seconds() - self._paused_total

            self.time_data.append(elapsed)
            self.power_data.append(adjusted)
            self.sample_count += 1

            # --- recording ---
            if self._recording:
                self._rec_time_data.append(elapsed)
                self._rec_power_data.append(adjusted)
                # check if limit reached
                if self._check_recording_limit():
                    self._finish_recording()

            # info bar
            self.power_display.configure(text=f"{adjusted:.3f} mW")
            self.samples_display.configure(text=str(self.sample_count))

            # --- apply live window ---
            t_list = list(self.time_data)
            p_list = list(self.power_data)

            live_mode = self.live_mode_var.get()
            try:
                live_val = float(self.live_value_entry.get())
            except (ValueError, TypeError):
                live_val = 0

            if live_val > 0:
                if live_mode == "Time":
                    # keep only points within the last `live_val` seconds
                    cutoff = elapsed - live_val
                    start_idx = 0
                    for i, t in enumerate(t_list):
                        if t >= cutoff:
                            start_idx = i
                            break
                    t_list = t_list[start_idx:]
                    p_list = p_list[start_idx:]
                else:
                    # keep the last `live_val` samples
                    n = int(live_val)
                    t_list = t_list[-n:]
                    p_list = p_list[-n:]

            # efficient redraw
            if self._line is None:
                self._line, = self.ax.plot(t_list, p_list,
                                           color="#1E90FF", linewidth=1)
            else:
                self._line.set_data(t_list, p_list)
            self.ax.relim()
            self.ax.autoscale_view()
            self.canvas.draw_idle()

        self._update_id = self.after(50, self._update_graph)

    def _style_axes(self):
        """Apply consistent styling to the matplotlib axes."""
        self.ax.set_facecolor("#2b2b2b")
        self.ax.set_xlabel("Time (s)", color="white")
        self.ax.set_ylabel("Power (mW)", color="white")
        self.ax.tick_params(colors="white")
        for spine in self.ax.spines.values():
            spine.set_color("#555555")
        self.ax.grid(True, alpha=0.3)

    # ------------------------------------------------------------------
    # Toolbar callbacks
    # ------------------------------------------------------------------

    def _on_save(self):
        """Save the current live data (or recorded data) into the experiment folder."""
        # prefer recorded data if it exists, otherwise use live buffer
        if self._rec_time_data:
            t_data = list(self._rec_time_data)
            p_data = list(self._rec_power_data)
        else:
            t_data = list(self.time_data)
            p_data = list(self.power_data)

        if not t_data:
            return  # nothing to save

        path = self._get_power_meter_save_path()
        self._write_csv(path, t_data, p_data)
        try:
            self.master.notification("Power data saved", path, "#1a8300", path=path)
        except Exception:
            pass

    def _on_record(self):
        """Start a recording session limited by time or sample count."""
        if self._recording:
            return  # already recording

        rec_mode = self.rec_mode_var.get()
        try:
            rec_val = float(self.rec_value_entry.get())
        except (ValueError, TypeError):
            rec_val = 0

        if rec_val <= 0:
            return  # need a positive limit

        self._rec_time_data.clear()
        self._rec_power_data.clear()
        self._rec_mode = rec_mode
        self._rec_limit = rec_val

        # reset the graph so recording always starts from t = 0
        self.time_data.clear()
        self.power_data.clear()
        self.sample_count = 0
        self.start_time = datetime.now()
        self._paused_total = 0.0
        self._paused_at = None
        if self._line is not None:
            self._line.set_data([], [])
            self.ax.relim()
            self.ax.autoscale_view()
            self.canvas.draw_idle()
        self._line = None

        # un-pause if currently paused so data flows immediately
        self._paused = False
        self.play_pause_btn.configure(image=img_pause)

        self._rec_start_time = 0.0
        self._recording = True
        self.record_btn.configure(text_color="#00FF00")  # green = recording active
        self._show_recording_overlay()

    def _on_play_pause(self):
        """Toggle between pausing and resuming the live display."""
        if self._paused:
            # resuming — accumulate pause duration
            if self._paused_at is not None:
                self._paused_total += (datetime.now() - self._paused_at).total_seconds()
                self._paused_at = None
            self._paused = False
            self.play_pause_btn.configure(image=img_pause)
        else:
            # pausing — record when we paused
            self._paused_at = datetime.now()
            self._paused = True
            self.play_pause_btn.configure(image=img_play)

    def _on_stop(self):
        """Stop an active recording and auto-save the data."""
        if not self._recording:
            return
        self._finish_recording()

    def _on_reset(self):
        """Clear all collected data and reset the graph.

        Preserves the current pause state — if the display was paused
        before the reset it stays paused afterwards.
        """
        # stop active recording without saving
        if self._recording:
            self._recording = False
            self.record_btn.configure(text_color="#FF4444")
            self._hide_recording_overlay()
        self._rec_time_data.clear()
        self._rec_power_data.clear()

        self.time_data.clear()
        self.power_data.clear()
        self.sample_count = 0
        self.start_time = datetime.now()
        self._zero_offset = 0.0

        # reset pause-time tracking (keep paused state itself)
        self._paused_total = 0.0
        if self._paused:
            # still paused — anchor to "now" so resumed time starts at 0
            self._paused_at = datetime.now()
        else:
            self._paused_at = None

        # reset graph
        if self._line is not None:
            self._line.set_data([], [])
            self.ax.relim()
            self.ax.autoscale_view()
            self.canvas.draw_idle()
        self._line = None

        # reset info bar
        self.power_display.configure(text="--- mW")
        self.samples_display.configure(text="0")

    # ------------------------------------------------------------------
    # Recording helpers
    # ------------------------------------------------------------------

    def _check_recording_limit(self) -> bool:
        """Return True when the recording limit has been reached."""
        if self._rec_mode == "Time":
            elapsed_since_start = (
                (datetime.now() - self.start_time).total_seconds()
                - self._paused_total
                - self._rec_start_time
            )
            return elapsed_since_start >= self._rec_limit
        else:  # Samples
            return len(self._rec_time_data) >= int(self._rec_limit)

    def _finish_recording(self):
        """Stop recording, auto-save the recorded data, and pause the graph."""
        self._recording = False
        self.record_btn.configure(text_color="#FF4444")
        self._hide_recording_overlay()

        if self._rec_time_data:
            self._auto_save_recording()

        # pause the live display so the user can inspect the recorded trace
        self._paused = True
        self._paused_at = datetime.now()
        self.play_pause_btn.configure(image=img_play)

    def _auto_save_recording(self):
        """Save recorded data into the experiment folder via the file system."""
        path = self._get_power_meter_save_path()
        self._write_csv(path, list(self._rec_time_data),
                        list(self._rec_power_data))
        try:
            self.master.notification("Recording saved", path, "#1a8300", path=path)
        except Exception:
            pass

    def _get_power_meter_save_path(self) -> str:
        """Return the next available file path inside ``<experiment>/PowerMeter/PM_N/``.

        Folder structure::

            <experiment>/PowerMeter/PM_1/PM_1__<date>_<time>.csv
            <experiment>/PowerMeter/PM_2/PM_2__<date>_<time>.csv
        """
        base = self.file_system.get_backup_directory()
        pm_root = os.path.join(base, "PowerMeter")
        os.makedirs(pm_root, exist_ok=True)

        # find next numeric index
        pattern = re.compile(r"PM_(\d+)$")
        max_idx = 0
        try:
            for name in os.listdir(pm_root):
                m = pattern.match(name)
                if m:
                    max_idx = max(max_idx, int(m.group(1)))
        except FileNotFoundError:
            pass
        idx = max_idx + 1

        folder = os.path.join(pm_root, f"PM_{idx}")
        os.makedirs(folder, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H.%M.%S")
        filename = f"PM_{idx}__{timestamp}.csv"
        return os.path.join(folder, filename)

    def _write_csv(self, path: str, times: list, powers: list):
        """Write time/power data with a 23-line metadata header.

        The data columns are stored as **Time (ms)** and **Power (W)** so that
        external analysis scripts (``np.loadtxt(f, delimiter=',', usecols=(0,1),
        skiprows=23)``) work without conversion.  Internally ``times`` are in
        seconds and ``powers`` in mW, so we convert before writing.
        """
        try:
            t_arr = np.array(times)    # seconds
            p_arr = np.array(powers)   # mW

            # convert to ms / W for the CSV
            t_ms = t_arr * 1000.0
            p_w  = p_arr / 1000.0

            # Gather metadata for the header
            wl = getattr(self, "wl_var", None)
            wavelength_nm = wl.get() if wl else "N/A"
            n_samples = len(t_arr)
            duration_s = (t_arr[-1] - t_arr[0]) if n_samples > 1 else 0.0
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            device_name = ""
            device_serial = ""
            if self.connected_device:
                device_name = getattr(self.connected_device, "name", "")
                device_serial = getattr(self.connected_device, "serial", "")

            # Build exactly 23 header lines (including the column-name line)
            header_lines = [
                f"# MicroView Power Meter Data",
                f"# Date: {timestamp}",
                f"# Device: {device_name}",
                f"# Serial: {device_serial}",
                f"# Wavelength (nm): {wavelength_nm}",
                f"# Samples: {n_samples}",
                f"# Duration (s): {duration_s:.4f}",
                f"# Zero offset (mW): {self._zero_offset:.6f}",
                f"# Auto-range: {getattr(self, 'auto_range_var', 'N/A')}",
                f"#",
                f"# Data format:",
                f"#   Column 0 – Time in milliseconds (ms)",
                f"#   Column 1 – Power in watts (W)",
                f"#",
                f"# To load in Python / NumPy:",
                f"#   data = np.loadtxt(file, delimiter=',', usecols=(0,1), skiprows=23)",
                f"#   time_s = data[:,0] / 1000",
                f"#   power_mW = data[:,1] * 1000",
                f"#",
                f"# --------------------------------------------------",
                f"#",
                f"#",
                f"Time (ms),Power (W)",
            ]

            with open(path, "w", newline="") as f:
                for line in header_lines:
                    f.write(line + "\n")
                writer = csv.writer(f)
                for t, p in zip(t_ms, p_w):
                    writer.writerow([f"{t:.4f}", f"{p:.9f}"])

            debugp("PowerMeterFrame", f"Saved: {path}")
        except Exception as e:
            debugp("PowerMeterFrame", f"CSV save error: {e}")
            return

        # auto-generate a plot image next to the CSV
        try:
            self._save_plot_image(path, times, powers)
        except Exception as e:
            debugp("PowerMeterFrame", f"Plot image error: {e}")

    def _save_plot_image(self, csv_path: str, times: list, powers: list):
        """Generate a power-vs-time plot image matching the standard analysis format.

        ``times`` are in seconds and ``powers`` in mW (internal units).
        The plot mirrors the external analysis workflow: convert to seconds
        on the x-axis and mW on the y-axis, then overlay average lines for
        the first and last 200 samples.
        """
        t_arr = np.array(times)    # already in seconds
        p_arr = np.array(powers)   # already in mW

        fig, ax = plt.subplots(1, 1, figsize=(5, 3))
        ax.plot(t_arr, p_arr, 'skyblue')
        ax.set_xlabel('Time [s]')
        ax.set_ylabel('Power [mW]')

        # average lines for first/last 200 points (or fewer if data is short)
        n_avg = min(200, len(p_arr))
        if n_avg > 0:
            vals_off = p_arr[:n_avg]
            vals_on  = p_arr[-n_avg:]
            time_off = t_arr[:n_avg]
            time_on  = t_arr[-n_avg:]

            avg_off = np.mean(vals_off)
            avg_on  = np.mean(vals_on)

            ax.plot(time_off, avg_off * np.ones(n_avg), 'red', linewidth=2, label='_')
            ax.plot(time_on,  avg_on  * np.ones(n_avg), 'green', linewidth=2, label='_')

        fig.tight_layout()

        img_path = os.path.splitext(csv_path)[0] + ".png"
        fig.savefig(img_path, dpi=150)
        plt.close(fig)
        debugp("PowerMeterFrame", f"Plot saved: {img_path}")

    # ------------------------------------------------------------------
    # Recording overlay (pulsating "● REC" badge)
    # ------------------------------------------------------------------

    def _show_recording_overlay(self):
        """Show a pulsating red recording indicator over the graph."""
        if self._rec_overlay is not None:
            return  # already visible

        self._rec_overlay = CTkFrame(
            self.main_area, width=100, height=32,
            corner_radius=6, fg_color="#CC0000",
        )
        self._rec_overlay.place(relx=0.98, rely=0.08, anchor="ne")
        self._rec_overlay.lift()  # ensure it's above the canvas

        self._rec_overlay_label = CTkLabel(
            self._rec_overlay, text="\u25cf  REC",
            font=("Arial", 14, "bold"), text_color="white",
        )
        self._rec_overlay_label.place(relx=0.5, rely=0.5, anchor="center")

        self._rec_pulse_on = True
        self._pulse_recording_overlay()

    def _pulse_recording_overlay(self):
        """Toggle the recording overlay visibility to create a pulsing effect."""
        if self._rec_overlay is None:
            return
        try:
            if self._rec_pulse_on:
                self._rec_overlay.configure(fg_color="#CC0000")
                self._rec_overlay_label.configure(text_color="white")
            else:
                self._rec_overlay.configure(fg_color="#550000")
                self._rec_overlay_label.configure(text_color="#884444")
            self._rec_pulse_on = not self._rec_pulse_on
            self._rec_pulse_id = self.after(600, self._pulse_recording_overlay)
        except Exception:
            pass

    def _hide_recording_overlay(self):
        """Remove the pulsating recording overlay."""
        if self._rec_pulse_id is not None:
            try:
                self.after_cancel(self._rec_pulse_id)
            except Exception:
                pass
            self._rec_pulse_id = None
        if self._rec_overlay is not None:
            try:
                self._rec_overlay.destroy()
            except Exception:
                pass
            self._rec_overlay = None
            self._rec_overlay_label = None

    # ------------------------------------------------------------------
    # Wavelength persistence
    # ------------------------------------------------------------------

    _WAVELENGTH_CONFIG = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "pm_wavelengths.json"
    )

    @classmethod
    def _load_wavelengths(cls) -> list:
        """Load saved wavelength list from disk, falling back to defaults."""
        try:
            path = os.path.normpath(cls._WAVELENGTH_CONFIG)
            if os.path.isfile(path):
                with open(path, "r") as f:
                    data = json.load(f)
                wls = data.get("wavelengths", [])
                if wls and isinstance(wls, list):
                    # ensure "Custom" is always last
                    wls = [w for w in wls if w != "Custom"]
                    wls.append("Custom")
                    return wls
        except Exception:
            pass
        return ["785", "Custom"]

    def _save_wavelengths(self):
        """Persist the current wavelength list to disk."""
        try:
            path = os.path.normpath(self._WAVELENGTH_CONFIG)
            with open(path, "w") as f:
                json.dump({"wavelengths": self.wavelengths}, f)
        except Exception as e:
            debugp("PowerMeterFrame", f"Failed to save wavelengths: {e}")

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------

    def set_unavailable(self, message):
        self.is_disabled = True
        if not self.unavailable_message_label:
            self.unavailable_message_label = CTkLabel(
                self, text=message, font=("Arial", 20))
            self.unavailable_message_label.place(relx=0.5, rely=0.5, anchor="center")

    def set_available(self):
        self.is_disabled = False
        if self.unavailable_message_label:
            self.unavailable_message_label.destroy()
            self.unavailable_message_label = None

    def on_closing(self):
        self._stop_update()
        # save active recording before closing
        if getattr(self, '_recording', False):
            self._finish_recording()
        if getattr(self, 'connected_device', None):
            try:
                self.connected_device.stop()
                self.connected_device.disconnect()
            except Exception:
                pass
