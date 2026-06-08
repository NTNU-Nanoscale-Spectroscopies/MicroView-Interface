"""
MyStage -- Thorlabs MCM3001 Z-axis controller (single motorised axis).

Based on the serial protocol from:
    https://github.com/amsikking/thorlabs_MCM3000

The MCM3001 uses the same command set as the MCM3000.  This class talks to
exactly *one* channel (default: channel 2 / ZFM2020 actuator) and exposes
a high-level API that the MicroView GUI already calls:

    connect() / disconnect()
    get_position()          -> float  (mm, relative to the user-defined zero)
    move_to(pos_mm)         -> float  (clamped, actual target in mm)
    move_by(delta_mm)       -> float
    step(delta_mm)          -> float  (alias for move_by)
    set_zero()              -> None   (resets encoder zero at the current position)

Safety
------
A configurable software limit (default +/-3 mm) is enforced on every move.
If a requested target exceeds the limit the move is *clamped* to the boundary
and a warning is printed -- the stage will NOT crash into the objective.
"""

import threading
import time

import serial
import serial.tools.list_ports

from dev.debugHelp import debugp

# ---------------------------------------------------------------------------
# Supported stage types: (um_per_encoder_count, +/- position_limit_um)
# ---------------------------------------------------------------------------
SUPPORTED_STAGES = {
    'ZFM2020': (0.2116667, 12_700.0),   # +/-12.7 mm travel
    'ZFM2030': (0.2116667, 12_700.0),
    'MMP-2XY': (0.5,       25_400.0),
}


class MyStage:
    """Thorlabs MCM3001 single-axis stage controller.

    Parameters
    ----------
    name : str
        Display name shown in the GUI.
    serial_port : str
        COM port *number* (e.g. ``"8"`` -> ``COM8``) **or** full port string
        (e.g. ``"COM8"``).
    enable : bool, optional
        If True the device is enabled after connection.
    stage_type : str, optional
        Actuator model string -- must be a key in ``SUPPORTED_STAGES``.
    channel : int, optional
        MCM3001 channel the Z actuator is wired to (0, 1 or 2).
    reverse : bool, optional
        Flip the positive direction of the encoder axis.
    safety_limit_mm : float, optional
        Software travel limit in **mm** (+/-).  Any commanded position outside
        this window is clamped.  Set to ``None`` to use the full mechanical
        range of the actuator.
    baudrate : int, optional
        Serial baud rate (default 460 800 -- the MCM3000/3001 factory value).
    """

    def __init__(
        self,
        name,
        serial_port,
        enable=False,
        stage_type='ZFM2020',
        channel=2,
        reverse=False,
        safety_limit_mm=3.0,
        baudrate=460800,
    ):
        self.name = name
        # normalise COM port specification
        port = str(serial_port).strip()
        if port.isdigit():
            port = f"COM{port}"
        self.serial = port                       # keep attribute name for compatibility
        self.enable = enable
        self.connected = False
        self.is_running = False

        # hardware config
        assert stage_type in SUPPORTED_STAGES, (
            f"Stage type '{stage_type}' not supported.  "
            f"Choose from {list(SUPPORTED_STAGES)}")
        self._stage_type = stage_type
        self._channel = channel
        self._reverse = reverse
        self._baudrate = baudrate

        # encoder conversion constants
        self._um_per_count = SUPPORTED_STAGES[stage_type][0]
        mechanical_limit_um = SUPPORTED_STAGES[stage_type][1]

        # safety limit (user-configurable, in um internally)
        if safety_limit_mm is not None:
            self._position_limit_um = min(safety_limit_mm * 1000.0,
                                          mechanical_limit_um)
        else:
            self._position_limit_um = mechanical_limit_um

        # runtime state
        self._port = None
        self._lock = threading.Lock()
        self._encoder_counts = 0
        self._target_encoder_counts = None
        self._encoder_counts_tol = 1          # counts

        # positions bookkeeping  (um internally, mm in public API)
        self._position_um = 0.0
        self.saved_positions = []
        self.saved_position = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------
    def connect(self):
        """Open the serial port and read the current encoder position.

        Returns
        -------
        bool
            Whether the connection was established successfully.
        """
        if self.connected:
            return True
        try:
            self._port = serial.Serial(
                port=self.serial, baudrate=self._baudrate, timeout=5)
            self._get_encoder_counts()
            self.connected = True
            debugp("Stage", f"Connected {self.name} on {self.serial} "
                   f"(ch{self._channel}, {self._stage_type}, "
                   f"pos={self._position_um:.1f} um)")
            return True
        except Exception as exc:
            debugp("Stage", f"Connection failed for {self.name}: {exc}")
            self.connected = False
            return False

    def disconnect(self):
        """Close the serial port."""
        if self._port is not None:
            try:
                self._port.close()
            except Exception:
                pass
        self._port = None
        self.connected = False
        debugp("Stage", f"Disconnected {self.name}")

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
                self._get_encoder_counts()
            return self._position_um / 1000.0

    def move_to(self, pos_mm):
        """Move to an absolute position in mm.

        Parameters
        ----------
        pos_mm : float
            Target position in millimetres.

        Returns
        -------
        float
            The actual (possibly clamped) target position in mm.
        """
        target_um = float(pos_mm) * 1000.0
        target_um = self._clamp(target_um)
        with self._lock:
            self._do_move(target_um)
        return target_um / 1000.0

    def move_by(self, delta_mm):
        """Move by a relative distance in mm.

        Parameters
        ----------
        delta_mm : float
            Distance to move in millimetres (positive or negative).

        Returns
        -------
        float
            The actual new position in mm.
        """
        with self._lock:
            if self.connected:
                self._get_encoder_counts()
            target_um = self._position_um + float(delta_mm) * 1000.0
            target_um = self._clamp(target_um)
            self._do_move(target_um)
        return target_um / 1000.0

    def step(self, delta_mm):
        """Alias for ``move_by`` -- used by the GUI +/- buttons.

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
        """Reset the encoder origin to the current physical position.

        After calling this the current position reads as 0.000 mm.
        """
        with self._lock:
            self._set_encoder_counts_to_zero()
        debugp("Stage", f"{self.name}: zero set at current position")

    # ------------------------------------------------------------------
    # Safety
    # ------------------------------------------------------------------
    def _clamp(self, target_um):
        """Clamp target to +/- safety limit.  Warns if clamping occurs."""
        limit = self._position_limit_um
        if target_um > limit:
            debugp("Stage",
                   f"SAFETY: target {target_um:.1f} um clamped to +{limit:.1f} um")
            return limit
        if target_um < -limit:
            debugp("Stage",
                   f"SAFETY: target {target_um:.1f} um clamped to -{limit:.1f} um")
            return -limit
        return target_um

    # ------------------------------------------------------------------
    # Low-level serial helpers  (call with self._lock held)
    # ------------------------------------------------------------------
    def _send(self, cmd, response_bytes=None):
        """Send a raw command and optionally read a response."""
        assert self._port is not None, "Serial port is not open"
        self._port.write(cmd)
        if response_bytes is not None:
            response = self._port.read(response_bytes)
            return response
        return None

    def _get_encoder_counts(self):
        """Query encoder position (updates ``self._position_um``)."""
        ch_byte = self._channel.to_bytes(1, 'little')
        cmd = b'\x0a\x04' + ch_byte + b'\x00\x00\x00'
        response = self._send(cmd, response_bytes=12)
        if response is None or len(response) < 12:
            return
        self._encoder_counts = int.from_bytes(
            response[-4:], byteorder='little', signed=True)
        self._position_um = self._encoder_to_um(self._encoder_counts)

    def _encoder_to_um(self, counts):
        um = counts * self._um_per_count
        if self._reverse:
            um = -um
        return um

    def _um_to_encoder(self, um):
        counts = int(round(um / self._um_per_count))
        if self._reverse:
            counts = -counts
        return counts

    def _set_encoder_counts_to_zero(self):
        """Set the controller's encoder counter to 0 at the current position."""
        ch_bytes = self._channel.to_bytes(2, 'little')
        enc_bytes = (0).to_bytes(4, 'little', signed=True)
        cmd = b'\x09\x04\x06\x00\x00\x00' + ch_bytes + enc_bytes
        self._send(cmd)
        # poll until the controller acknowledges the reset
        for _ in range(50):
            self._get_encoder_counts()
            if self._encoder_counts == 0:
                break
            time.sleep(0.05)
        self._position_um = 0.0

    def _move_to_encoder_count(self, encoder_counts, block=True):
        """Issue a move command to a specific encoder count."""
        # finish any pending move first
        if self._target_encoder_counts is not None:
            self._finish_move()
        self._target_encoder_counts = encoder_counts
        enc_bytes = encoder_counts.to_bytes(4, 'little', signed=True)
        ch_bytes = self._channel.to_bytes(2, 'little')
        cmd = b'\x53\x04\x06\x00\x00\x00' + ch_bytes + enc_bytes
        self._send(cmd)
        if block:
            self._finish_move()

    def _finish_move(self, poll_s=0.05):
        """Block until the stage reaches the target (within tolerance)."""
        if self._target_encoder_counts is None:
            return
        target = self._target_encoder_counts
        tol = self._encoder_counts_tol
        for _ in range(2000):                    # ~100 s max wait
            self._get_encoder_counts()
            if target - tol <= self._encoder_counts <= target + tol:
                break
            time.sleep(poll_s)
        self._target_encoder_counts = None

    def _do_move(self, target_um):
        """Translate um -> encoder counts and issue the move (blocking)."""
        if not self.connected:
            debugp("Stage", f"{self.name}: not connected -- move ignored")
            return
        enc = self._um_to_encoder(target_um)
        self._move_to_encoder_count(enc, block=True)
        self._position_um = self._encoder_to_um(self._encoder_counts)

    # ------------------------------------------------------------------
    # Dunder
    # ------------------------------------------------------------------
    def __repr__(self):
        return f"{self.name}, serial: {self.serial}"
