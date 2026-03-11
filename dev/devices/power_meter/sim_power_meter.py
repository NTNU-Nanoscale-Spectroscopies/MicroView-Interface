"""Simulated power meter for GUI development and testing.

This class mimics the behaviour of :class:`MyPowerMeter` but generates
synthetic power readings instead of communicating with real hardware.
It is intended for use when a physical Thorlabs PM16-401 (or similar)
is not available.

Usage in ``main.py``::

    from dev.devices.power_meter.sim_power_meter import MySimPowerMeter

    MySimPowerMeter("Power meter (sim)", "SIM-PM-000", enable=True, model="PM16-401")
"""

import queue
import random
import threading
import time

from dev.debugHelp import debugp
from dev.devices.power_meter.power_meter import MyPowerMeter


class MySimPowerMeter(MyPowerMeter):
    """Simulated power meter that produces synthetic readings.

    The simulated output is a noisy baseline centred around *baseline_mw*
    milliwatts, sampled at approximately 20 Hz.  The class exposes the
    same public API as :class:`MyPowerMeter` so it can be used as a
    drop-in replacement.
    """

    def __init__(self, name, serial, enable=False, model=None,
                 baseline_mw=0.003, noise_mw=0.005):
        # bypass the real __init__ which imports TLPMX ctypes constants;
        # only replicate the fields we need
        self.name = name
        self.serial = serial
        self.enable = enable
        self.model = model
        self.connected = False

        # simulation parameters
        self._baseline = baseline_mw
        self._noise = noise_mw
        self._wavelength = 785  # nm

        # simulated device state
        self._auto_range = True
        self._power_range_W = 0.01       # 10 mW default range
        self._dark_offset = 0.0

        # acquisition state
        self.is_running = False
        self._power_queue: queue.Queue = queue.Queue(maxsize=1)
        self._data_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def is_available(self):
        """Simulated meter is always available."""
        return True

    def connect(self):
        if self.connected:
            return True
        self.connected = True
        self.is_running = False
        debugp("powermeter", f"Sim connected: {self}")
        return True

    def disconnect(self):
        self.stop()
        self.connected = False
        debugp("powermeter", f"Sim disconnected: {self}")

    # ------------------------------------------------------------------
    # Acquisition
    # ------------------------------------------------------------------

    def start(self):
        """Begin generating simulated power readings."""
        if self.connected and not self.is_running:
            self.is_running = True
            self._data_thread = threading.Thread(target=self._acquire, daemon=True)
            self._data_thread.start()

    def stop(self):
        """Stop the acquisition thread."""
        self.is_running = False
        if self._data_thread is not None:
            self._data_thread.join(timeout=1)
            self._data_thread = None
        # drain the queue
        while not self._power_queue.empty():
            try:
                self._power_queue.get_nowait()
            except queue.Empty:
                break

    def _acquire(self):
        """Background thread that pushes simulated readings."""
        while self.is_running:
            power = self._baseline + random.gauss(0, self._noise)
            # replace the single-slot queue with the newest reading
            if not self._power_queue.empty():
                try:
                    self._power_queue.get_nowait()
                except queue.Empty:
                    pass
            self._power_queue.put(power)
            time.sleep(0.05)  # ~20 Hz

    # ------------------------------------------------------------------
    # Measurement helpers
    # ------------------------------------------------------------------

    def get_power(self):
        """Return the latest simulated power reading (mW), or ``None``."""
        try:
            return self._power_queue.get_nowait()
        except queue.Empty:
            return None

    # ------------------------------------------------------------------
    # Wavelength
    # ------------------------------------------------------------------

    def get_wavelength(self):
        return self._wavelength

    def set_wavelength(self, nm):
        self._wavelength = int(nm)
        debugp("powermeter", f"Sim wavelength set to {nm} nm")

    # ------------------------------------------------------------------
    # Auto Range / Manual Range
    # ------------------------------------------------------------------

    def get_auto_range(self):
        return self._auto_range

    def set_auto_range(self, enabled: bool):
        self._auto_range = enabled
        debugp("powermeter", f"Sim auto-range {'ON' if enabled else 'OFF'}")

    def get_power_range(self):
        """Return current simulated range in watts."""
        return self._power_range_W

    def set_power_range(self, watts: float):
        """Set manual range (watts).  Disables auto-range."""
        self._auto_range = False
        self._power_range_W = watts
        debugp("powermeter", f"Sim range set to {watts} W")

    def get_power_ranges(self):
        """Return ``(min_W, max_W)`` simulated sensor spec."""
        return (1e-9, 0.5)  # 1 nW … 500 mW

    # ------------------------------------------------------------------
    # Zero / Dark Adjust
    # ------------------------------------------------------------------

    def zero_adjust(self):
        """Simulate dark-current zeroing (instant)."""
        self._dark_offset = self._baseline
        debugp("powermeter", "Sim zero-adjust complete")

    def get_zero_state(self):
        """Simulated zeroing always completes instantly."""
        return False

    def get_dark_offset(self):
        return self._dark_offset

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self):
        return f"Sim {self.name}, serial: {self.serial}"
