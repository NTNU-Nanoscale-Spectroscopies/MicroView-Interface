from dev.debugHelp import debugp

# import the low-level Thorlabs driver wrapper
from .dll_sdk.TLPMX import TLPMX
from ctypes import (
    create_string_buffer, c_uint32, c_uint16, c_int16, c_double, byref,
)

import collections
import threading
import time

# SDK constants
_CH1 = c_uint16(1)
_ATTR_SET = c_int16(0)  # TLPM_ATTR_SET_VAL
_ATTR_MIN = c_int16(1)  # TLPM_ATTR_MIN_VAL
_ATTR_MAX = c_int16(2)  # TLPM_ATTR_MAX_VAL


class MyPowerMeter():
    """Thorlabs PM16-401 (or compatible) power meter driver.

    Uses the TLPMX wrapper in ``dll_sdk`` for all instrument
    communication.  A background acquisition thread appends timestamped
    ``(t_monotonic, mW)`` samples into a bounded buffer that the GUI
    drains in batches via :meth:`get_samples`.
    """

    def __init__(self, name, serial, enable=False, model=None):
        self.name = name
        self.serial = serial
        self.enable = enable
        self.model = model
        self.connected = False

        # internal handles
        self._tlpm = None
        self._wavelength = 785          # nm – local cache
        self._auto_range = True

        # acquisition state
        self.is_running = False
        # Timestamped (t_monotonic, mW) samples written by the acquisition
        # thread and drained by the GUI in batches via get_samples().
        self._sample_buffer: collections.deque = collections.deque(maxlen=1024)
        self._sample_lock = threading.Lock()
        self._latest_power: float | None = None
        self._data_thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def is_available(self):
        """Return ``True`` if at least one compatible powermeter is detected."""
        try:
            mgr = TLPMX()
            cnt = c_uint32()
            mgr.findRsrc(byref(cnt))
            return cnt.value > 0
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self):
        """Open communication with the device.

        Scans TLPMX resources for a matching serial/model and opens a
        dedicated session.  Returns ``True`` on success.
        """
        print(f"[PowerMeter] Attempting to connect {self}")
        if self.connected:
            print("[PowerMeter] Already connected")
            return True

        try:
            manager = TLPMX()
            count = c_uint32()
            manager.findRsrc(byref(count))
            print(f"[PowerMeter] findRsrc found {count.value} resources")
            if count.value == 0:
                print("[PowerMeter] no powermeter resources found")
                return False

            chosen = None
            for idx in range(count.value):
                name_buf = create_string_buffer(1024)
                manager.getRsrcName(idx, name_buf)
                model_buf = create_string_buffer(1024)
                serial_buf = create_string_buffer(1024)
                man_buf = create_string_buffer(1024)
                avail = c_int16()
                manager.getRsrcInfo(idx, model_buf, serial_buf, man_buf, byref(avail))
                print(f"[PowerMeter] resource {idx}: model={model_buf.value}, serial={serial_buf.value}, name={name_buf.value}")
                if self.serial and serial_buf.value.decode() == self.serial:
                    chosen = name_buf
                    break
                if self.model and model_buf.value.decode() == self.model:
                    chosen = name_buf
                    break
            if chosen is None:
                chosen = name_buf  # fall back to last resource

            print(f"[PowerMeter] opening session with resource: {chosen.value}")
            self._tlpm = TLPMX(chosen, True, True)
            self.connected = True
            print(f"[PowerMeter] connected successfully via resource {chosen.value}")

            # read back device state so the GUI matches
            self._sync_state_from_device()
            return True
        except Exception as e:
            print(f"[PowerMeter] connection failed: {e}")
            import traceback; traceback.print_exc()
            return False

    def disconnect(self):
        """Close the TLPMX session."""
        self.stop()
        if self.connected:
            debugp("powermeter", f"Disconnecting {self}")
            try:
                if self._tlpm:
                    self._tlpm.close()
            except Exception as e:
                debugp("powermeter", f"error closing session: {e}")
            self._tlpm = None
            self.connected = False

    def _sync_state_from_device(self):
        """Read wavelength, auto-range and range from the device."""
        try:
            wl = c_double()
            self._tlpm.getWavelength(_ATTR_SET, byref(wl), _CH1)
            self._wavelength = int(round(wl.value))
        except Exception:
            pass

        try:
            ar = c_int16()
            self._tlpm.getPowerAutorange(byref(ar), _CH1)
            self._auto_range = bool(ar.value)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Acquisition
    # ------------------------------------------------------------------

    def start(self):
        """Start background thread that continuously reads power."""
        print(f"[PowerMeter] start() called. connected={self.connected}, is_running={self.is_running}")
        if self.connected and not self.is_running:
            self.is_running = True
            self._data_thread = threading.Thread(
                target=self._acquire, daemon=True)
            self._data_thread.start()
            print("[PowerMeter] acquisition thread launched")
        else:
            print("[PowerMeter] start() skipped (not connected or already running)")

    def stop(self):
        """Stop the acquisition thread."""
        self.is_running = False
        if self._data_thread is not None:
            self._data_thread.join(timeout=2)
            self._data_thread = None
        with self._sample_lock:
            self._sample_buffer.clear()
            self._latest_power = None

    def _acquire(self):
        """Background thread: poll ``measPower`` and append (t, mW) samples."""
        print("[PowerMeter] acquisition thread started")
        while self.is_running and self._tlpm:
            try:
                power = c_double()
                self._tlpm.measPower(byref(power), _CH1)
                mw = power.value * 1000.0  # W → mW
                t = time.monotonic()
                with self._sample_lock:
                    self._sample_buffer.append((t, mw))
                    self._latest_power = mw
            except Exception as e:
                print(f"[PowerMeter] measPower error: {e}")
                time.sleep(0.5)  # back off on error
                continue
            time.sleep(0.05)  # ~20 Hz
        print("[PowerMeter] acquisition thread stopped")

    # ------------------------------------------------------------------
    # Measurement helpers
    # ------------------------------------------------------------------

    def get_power(self):
        """Return latest power reading (mW), or ``None``.

        Returns the latest cached value from the acquisition thread without
        draining the sample buffer.  Falls back to a synchronous
        ``measPower`` call when no sample has been produced yet.
        """
        with self._sample_lock:
            if self._latest_power is not None:
                return self._latest_power

        # Direct fallback: try a blocking read on the calling thread
        if self._tlpm and self.connected:
            try:
                power = c_double()
                self._tlpm.measPower(byref(power), _CH1)
                mw = power.value * 1000.0  # W → mW
                return mw
            except Exception as e:
                print(f"[PowerMeter] direct measPower fallback error: {e}")
        return None

    def get_samples(self):
        """Drain and return all buffered ``(t_monotonic, mW)`` samples.

        ``t_monotonic`` is ``time.monotonic()`` captured by the acquisition
        thread when the reading was taken.  Returned samples are removed
        from the internal buffer; the next call only sees newer samples.
        """
        with self._sample_lock:
            if not self._sample_buffer:
                return []
            out = list(self._sample_buffer)
            self._sample_buffer.clear()
        return out

    # ------------------------------------------------------------------
    # Wavelength
    # ------------------------------------------------------------------

    def get_wavelength(self):
        """Return the currently configured sensor wavelength (nm)."""
        if self._tlpm:
            try:
                wl = c_double()
                self._tlpm.getWavelength(_ATTR_SET, byref(wl), _CH1)
                self._wavelength = int(round(wl.value))
            except Exception:
                pass
        return self._wavelength

    def set_wavelength(self, nm):
        """Set sensor wavelength (nm)."""
        self._wavelength = int(nm)
        if self._tlpm:
            try:
                self._tlpm.setWavelength(c_double(float(nm)), _CH1)
            except Exception as e:
                debugp("powermeter", f"setWavelength error: {e}")

    # ------------------------------------------------------------------
    # Auto Range / Manual Range
    # ------------------------------------------------------------------

    def get_auto_range(self):
        """Return ``True`` if auto-range is enabled."""
        if self._tlpm:
            try:
                ar = c_int16()
                self._tlpm.getPowerAutorange(byref(ar), _CH1)
                self._auto_range = bool(ar.value)
            except Exception:
                pass
        return self._auto_range

    def set_auto_range(self, enabled: bool):
        """Enable or disable auto-ranging."""
        self._auto_range = enabled
        if self._tlpm:
            try:
                self._tlpm.setPowerAutoRange(
                    c_int16(1 if enabled else 0), _CH1)
            except Exception as e:
                debugp("powermeter", f"setPowerAutoRange error: {e}")

    def get_power_range(self):
        """Return the current power range in watts."""
        if self._tlpm:
            try:
                val = c_double()
                self._tlpm.getPowerRange(_ATTR_SET, byref(val), _CH1)
                return val.value
            except Exception:
                pass
        return None

    def set_power_range(self, watts: float):
        """Manually set the power range (watts).  Disables auto-range."""
        self._auto_range = False
        if self._tlpm:
            try:
                self._tlpm.setPowerRange(c_double(watts), _CH1)
            except Exception as e:
                debugp("powermeter", f"setPowerRange error: {e}")

    def get_power_ranges(self):
        """Return ``(min_W, max_W)`` for the sensor, or ``None``."""
        if self._tlpm:
            try:
                mn = c_double()
                mx = c_double()
                self._tlpm.getPowerRange(_ATTR_MIN, byref(mn), _CH1)
                self._tlpm.getPowerRange(_ATTR_MAX, byref(mx), _CH1)
                return (mn.value, mx.value)
            except Exception:
                pass
        return None

    # ------------------------------------------------------------------
    # Zero / Dark Adjust
    # ------------------------------------------------------------------

    def zero_adjust(self):
        """Initiate hardware dark-current zeroing (sensor must be covered).

        Returns immediately — the zeroing runs asynchronously on the
        device.  Use ``get_zero_state()`` to poll completion.
        """
        if self._tlpm:
            try:
                self._tlpm.startDarkAdjust(_CH1)
            except Exception as e:
                debugp("powermeter", f"startDarkAdjust error: {e}")

    def get_zero_state(self):
        """Return ``True`` if hardware zeroing is still running."""
        if self._tlpm:
            try:
                state = c_int16()
                self._tlpm.getDarkAdjustState(byref(state), _CH1)
                return bool(state.value)
            except Exception:
                pass
        return False

    def get_dark_offset(self):
        """Return the current dark-offset value (A or V)."""
        if self._tlpm:
            try:
                val = c_double()
                self._tlpm.getDarkOffset(byref(val), _CH1)
                return val.value
            except Exception:
                pass
        return 0.0

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self):
        return f"{self.name}, serial: {self.serial}"