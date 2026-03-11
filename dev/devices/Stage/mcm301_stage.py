"""
MyMCM301Stage -- Thorlabs MCM301 controller stage driver.

Uses the official Thorlabs MCM301 SDK (DLL) for communication.
Exposes the same high-level API that the MicroView GUI already calls:

    connect() / disconnect()
    get_position()          -> float  (mm, relative to the user-defined zero)
    move_to(pos_mm)         -> float  (clamped, actual target in mm)
    move_by(delta_mm)       -> float
    step(delta_mm)          -> float  (alias for move_by)
    set_zero()              -> None   (software zero at the current position)

Safety
------
A configurable software limit (default ±3 mm) is enforced on every move.
Targets exceeding the limit are clamped to the boundary.

Slot mapping
------------
The physical slots on the back of the MCM301 (labelled 1, 2, 3) map to
API slot numbers 4, 5, 6 respectively.
"""

import os
import sys
import platform
import threading
import time

from dev.debugHelp import debugp

# ---------------------------------------------------------------------------
# Ensure the DLL SDK directory is importable so MCM301_COMMAND_LIB can find
# MCM301_Type_Define and the DLLs.
# ---------------------------------------------------------------------------
_DLL_SDK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dll_sdk")
if _DLL_SDK_DIR not in sys.path:
    sys.path.insert(0, _DLL_SDK_DIR)

# We delay the actual import of MCM301 so the module can be imported even when
# the DLL is not present (e.g. on a dev machine without the hardware).
_MCM301_CLASS = None


def _get_mcm301_class():
    """Lazily import and return the MCM301 class from the SDK."""
    global _MCM301_CLASS
    if _MCM301_CLASS is None:
        from MCM301_COMMAND_LIB import MCM301 as _cls
        _MCM301_CLASS = _cls
    return _MCM301_CLASS


def _load_dll_if_needed():
    """Load the correct DLL (32- or 64-bit) if not yet loaded."""
    cls = _get_mcm301_class()
    if not cls.isLoad:
        bits = platform.architecture()[0]  # e.g. "64bit"
        if "64" in bits:
            dll_name = "MCM301Lib_x64.dll"
        else:
            dll_name = "MCM301Lib_Win32.dll"
        dll_path = os.path.join(_DLL_SDK_DIR, dll_name)
        debugp("MCM301Stage", f"Loading DLL: {dll_path}")
        cls.load_library(dll_path)


# Physical slot -> API slot
_SLOT_MAP = {1: 4, 2: 5, 3: 6}


class MyMCM301Stage:
    """Thorlabs MCM301 controller stage driver (DLL-based).

    Parameters
    ----------
    name : str
        Display name shown in the GUI.
    serial_number : str
        Serial number of the MCM301 controller (as printed on the device,
        or as returned by ``MCM301.list_devices()``).
    enable : bool, optional
        If True the device is enabled after connection.
    slot : int, optional
        **Physical** slot on the back of the MCM301 (1, 2 or 3).
    safety_limit_mm : float or None, optional
        Software travel limit in mm (±).  ``None`` uses the full hardware
        range reported by the stage.
    """

    def __init__(
        self,
        name,
        serial_number,
        enable=False,
        slot=1,
        safety_limit_mm=3.0,
    ):
        self.name = name
        self.serial = str(serial_number).strip()
        self.enable = enable
        self.connected = False
        self.is_running = False

        assert slot in _SLOT_MAP, f"Slot must be 1, 2, or 3 (got {slot})"
        self._physical_slot = slot
        self._api_slot = _SLOT_MAP[slot]

        self._safety_limit_mm = safety_limit_mm
        # _position_limit_um is read by the GUI for the slider range
        self._position_limit_um = (safety_limit_mm * 1000.0
                                   if safety_limit_mm else 25_000.0)

        # SDK handle
        self._mcm = None
        self._nm_per_count = None        # read from device at connect time
        self._lock = threading.Lock()

        # Position tracking (encoder counts)
        self._encoder_counts = 0
        self._zero_offset_counts = 0    # encoder value at user-defined zero

        # Saved positions (for GUI)
        self.saved_positions = []
        self.saved_position = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    def connect(self):
        """Open the MCM301, enable the channel, and read stage parameters.

        Returns
        -------
        bool
            Whether the connection was established successfully.
        """
        if self.connected:
            return True
        try:
            _load_dll_if_needed()
            cls = _get_mcm301_class()
            self._mcm = cls()

            # Attempt to open by the configured serial number
            hdl = self._mcm.open(self.serial, 115200, 3)

            # Fallback: auto-detect the first available device
            if hdl < 0:
                devs = cls.list_devices()
                debugp("MCM301Stage",
                       f"Could not open '{self.serial}', "
                       f"auto-detecting … found {devs}")
                for dev_info in devs:
                    sn = dev_info[0]
                    hdl = self._mcm.open(sn, 115200, 3)
                    if hdl >= 0:
                        self.serial = sn
                        debugp("MCM301Stage",
                               f"Auto-connected to {sn}")
                        break

            if hdl < 0:
                debugp("MCM301Stage",
                       f"Failed to open MCM301 ({self.serial})")
                self._mcm = None
                return False

            # Enable the stepper on our slot
            ret = self._mcm.set_chan_enable_state(self._api_slot, 1)
            if ret < 0:
                debugp("MCM301Stage",
                       f"Warning: could not enable slot {self._physical_slot} "
                       f"(ret={ret})")

            # Read stage parameters (nm_per_count, limits, etc.)
            params = [0]
            ret = self._mcm.get_stage_params(self._api_slot, params)
            if ret >= 0 and isinstance(params[0], (list, tuple)):
                # params[0] = [counts_per_unit, nm_per_count,
                #              min_pos, max_pos, max_speed, max_acc]
                self._nm_per_count = float(params[0][1])
                debugp("MCM301Stage",
                       f"Stage params: nm_per_count={self._nm_per_count}, "
                       f"range=[{params[0][2]}, {params[0][3]}]")
            else:
                # Reasonable fallback for PLSZ1
                self._nm_per_count = 20.0
                debugp("MCM301Stage",
                       "Could not read stage params – using default "
                       "nm_per_count=20")

            # Read current encoder position
            self._read_encoder()
            self._zero_offset_counts = 0  # start with hardware zero

            self.connected = True
            pos_mm = self._counts_to_mm(
                self._encoder_counts - self._zero_offset_counts)
            debugp("MCM301Stage",
                   f"Connected {self.name} ({self.serial}) "
                   f"slot {self._physical_slot}, pos={pos_mm:.4f} mm")
            return True

        except Exception as exc:
            debugp("MCM301Stage", f"Connection failed: {exc}")
            self.connected = False
            self._mcm = None
            return False

    def disconnect(self):
        """Disable the stepper and close the MCM301 connection."""
        if self._mcm is not None:
            try:
                self._mcm.set_chan_enable_state(self._api_slot, 0)
            except Exception:
                pass
            try:
                self._mcm.close()
            except Exception:
                pass
        self._mcm = None
        self.connected = False
        debugp("MCM301Stage", f"Disconnected {self.name}")

    # ------------------------------------------------------------------
    # Public high-level API  (values in **mm**)
    # ------------------------------------------------------------------
    def get_position(self):
        """Return current position in mm (relative to user-set zero).

        Returns
        -------
        float
            Current position in millimetres.
        """
        with self._lock:
            if self.connected:
                self._read_encoder()
            rel = self._encoder_counts - self._zero_offset_counts
            return self._counts_to_mm(rel)

    def move_to(self, pos_mm):
        """Move to an absolute position in mm.

        Parameters
        ----------
        pos_mm : float
            Target position in millimetres (relative to user zero).

        Returns
        -------
        float
            The actual (possibly clamped) target in mm.
        """
        target_mm = self._clamp_mm(float(pos_mm))
        with self._lock:
            target_counts = (self._mm_to_counts(target_mm)
                             + self._zero_offset_counts)
            self._do_move(target_counts)
        return target_mm

    def move_by(self, delta_mm):
        """Move by a relative distance in mm.

        Parameters
        ----------
        delta_mm : float
            Distance in millimetres (positive or negative).

        Returns
        -------
        float
            The actual new position in mm.
        """
        with self._lock:
            if self.connected:
                self._read_encoder()
            rel = self._encoder_counts - self._zero_offset_counts
            current_mm = self._counts_to_mm(rel)
            target_mm = self._clamp_mm(current_mm + float(delta_mm))
            target_counts = (self._mm_to_counts(target_mm)
                             + self._zero_offset_counts)
            self._do_move(target_counts)
        return target_mm

    def step(self, delta_mm):
        """Alias for ``move_by`` -- used by the GUI ± buttons.

        Parameters
        ----------
        delta_mm : float
            Step size in millimetres.

        Returns
        -------
        float
            The actual new position in mm.
        """
        return self.move_by(delta_mm)

    def set_zero(self):
        """Set the software zero at the current physical position.

        After calling this the current position reads as 0.000 mm.
        """
        with self._lock:
            if self.connected:
                self._read_encoder()
            self._zero_offset_counts = self._encoder_counts
        debugp("MCM301Stage", f"{self.name}: zero set at current position")

    def home(self):
        """Home the stage (move to hardware home position).

        After homing the software zero is reset to the new position.
        """
        if not self.connected or self._mcm is None:
            return
        with self._lock:
            ret = self._mcm.home(self._api_slot)
            if ret < 0:
                debugp("MCM301Stage", "Home command failed")
                return
            self._wait_for_move()
            self._read_encoder()
            self._zero_offset_counts = self._encoder_counts
        debugp("MCM301Stage", f"{self.name}: homed")

    # ------------------------------------------------------------------
    # Safety
    # ------------------------------------------------------------------
    def _clamp_mm(self, pos_mm):
        """Clamp target to ± safety limit.  Warns if clamping occurs."""
        limit = self._safety_limit_mm
        if limit is None:
            return pos_mm
        if pos_mm > limit:
            debugp("MCM301Stage",
                   f"SAFETY: {pos_mm:.4f} mm clamped to +{limit:.4f} mm")
            return limit
        if pos_mm < -limit:
            debugp("MCM301Stage",
                   f"SAFETY: {pos_mm:.4f} mm clamped to -{limit:.4f} mm")
            return -limit
        return pos_mm

    # ------------------------------------------------------------------
    # Unit conversion
    # ------------------------------------------------------------------
    def _counts_to_mm(self, counts):
        """Encoder counts → millimetres."""
        if self._nm_per_count is None:
            return 0.0
        nm = counts * self._nm_per_count
        return nm / 1_000_000.0        # nm → mm

    def _mm_to_counts(self, mm_val):
        """Millimetres → encoder counts."""
        if not self._nm_per_count:
            return 0
        nm = mm_val * 1_000_000.0      # mm → nm
        return int(round(nm / self._nm_per_count))

    # ------------------------------------------------------------------
    # Low-level SDK helpers  (call with self._lock held)
    # ------------------------------------------------------------------
    def _read_encoder(self):
        """Read encoder position from the controller."""
        if self._mcm is None:
            return
        encoder = [0]
        status = [0]
        ret = self._mcm.get_mot_status(self._api_slot, encoder, status)
        if ret >= 0:
            self._encoder_counts = encoder[0]

    def _do_move(self, target_counts):
        """Issue an absolute move and block until complete."""
        if not self.connected or self._mcm is None:
            debugp("MCM301Stage", "Not connected – move ignored")
            return
        ret = self._mcm.move_absolute(self._api_slot, target_counts)
        if ret < 0:
            debugp("MCM301Stage", "move_absolute failed")
            return
        self._wait_for_move()

    def _wait_for_move(self, timeout_s=60, poll_s=0.05):
        """Block until the stepper reports no motion."""
        # Status bits indicating the stage is still moving:
        #   0x10  Moving CW              0x20  Moving CCW
        #   0x40  Jogging CW             0x80  Jogging CCW
        #   0x200 Homing
        moving_bits = 0x10 | 0x20 | 0x40 | 0x80 | 0x200
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            encoder = [0]
            status = [0]
            ret = self._mcm.get_mot_status(self._api_slot, encoder, status)
            if ret >= 0:
                self._encoder_counts = encoder[0]
                if not (status[0] & moving_bits):
                    return
            time.sleep(poll_s)
        debugp("MCM301Stage", "Move timed out")

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------
    def __repr__(self):
        return f"{self.name}, serial: {self.serial}"
