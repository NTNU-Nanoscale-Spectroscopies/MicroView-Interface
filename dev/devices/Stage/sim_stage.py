import threading
import time
from dev.debugHelp import debugp


class MySimStage:
    """Simple simulated stage for UI testing.

    Mimics the public API of ``MyStage`` so the GUI works identically
    without requiring real hardware or pyserial.

    Methods provided:
    - connect()/disconnect()
    - get_position()  -> float (mm)
    - move_to(pos)    -> float (mm)
    - move_by(delta)  -> float (mm)
    - step(delta)     -> float (mm)
    - set_zero()
    """
    def __init__(self, name="Sim Stage", serial="SIM-000", enable=False):
        self.name = name
        self.serial = serial
        self.enable = enable
        self.connected = False
        self.is_running = False
        self._position = 0.0
        self.saved_positions = []
        self.saved_position = None
        self._lock = threading.Lock()

    def connect(self):
        if not self.connected:
            debugp("SimStage", f"Connecting {self.name}")
            self.connected = True
        return self.connected

    def disconnect(self):
        if self.connected:
            debugp("SimStage", f"Disconnecting {self.name}")
            self.connected = False

    def get_position(self):
        with self._lock:
            return self._position

    def move_to(self, pos):
        try:
            pos = float(pos)
        except Exception:
            raise ValueError("Invalid position")
        with self._lock:
            self._position = pos
        debugp("SimStage", f"Moved to {self._position}")
        return self._position

    def move_by(self, delta):
        try:
            delta = float(delta)
        except Exception:
            raise ValueError("Invalid delta")
        with self._lock:
            self._position += delta
        debugp("SimStage", f"Moved by {delta}, new {self._position}")
        return self._position

    def step(self, delta):
        return self.move_by(delta)

    def set_zero(self):
        with self._lock:
            self._position = 0.0
        debugp("SimStage", "Zero set")

    def __repr__(self):
        return f"{self.name}, serial: {self.serial}"