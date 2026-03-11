import os
import sys
import json

from ..filter import MyFilter

class MyFilterWheel(MyFilter):
    """Implementation for a Thorlabs FW212CNEB (and similar) filter wheel.

    This class wraps the Thorlabs FWxC_COMMAND_LIB SDK and provides a simple
    high‑level API that the GUI can use.  The filter wheel reports a fixed
    number of positions, and we maintain an optional mapping between position
    numbers and user‑friendly names.  Settings are persisted to disk so the
    mapping survives application restarts.
    """

    def __init__(self, name, serial, enable=False):
        super().__init__(name, serial, enable)
        self._handle = None
        self.position_count = None          # number of positions reported by HW
        self.current_position = None        # last known (1‑based) position
        self.filter_names = {}              # pos -> name
        # UI handles (attached by setup_frame)
        self._ui_left_btn = None
        self._ui_right_btn = None
        self._ui_dropdown = None
        self._ui_position_var = None
        self._ui_settings_btn = None

        # choose a directory where the application can write persistently.
        # when frozen by PyInstaller __file__ points inside a temporary extraction
        # folder, so we use %APPDATA% or home directory instead.
        appdata = os.environ.get('APPDATA') or os.path.expanduser('~')
        config_dir = os.path.join(appdata, 'MicroView')
        try:
            os.makedirs(config_dir, exist_ok=True)
        except Exception:
            config_dir = os.path.dirname(__file__)

        self._settings_file = os.path.join(
            config_dir, f"filterwheel_{self.serial}.json")
        # create a log file path in the same configuration directory
        self._log_file = os.path.join(config_dir, "filterwheel.log")
        # log startup
        self._log(f"initialized filter wheel '{self.name}' serial={self.serial}")
        self.load_settings()

    # ------------------------------------------------------------------
    # persistence helpers
    # ------------------------------------------------------------------
    def _log(self, *args, **kwargs):
        """Append a timestamped message to the filter wheel log file."""
        try:
            with open(self._log_file, "a", encoding="utf-8") as lf:
                import datetime
                ts = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
                lf.write(ts + ' ' + ' '.join(str(a) for a in args) + "\n")
        except Exception:
            # if logging fails there's not much we can do; avoid recursion
            pass

    def load_settings(self):
        try:
            if os.path.isfile(self._settings_file):
                with open(self._settings_file, "r") as f:
                    data = json.load(f)
                self.filter_names = {int(k): v for k, v in data.get("filter_names", {}).items()}
        except Exception as exc:
            self._log("could not load settings", exc)

    def save_settings(self):
        try:
            with open(self._settings_file, "w") as f:
                json.dump({"filter_names": self.filter_names}, f)
        except Exception as exc:
            self._log("could not save settings", exc)

    # ------------------------------------------------------------------
    # low‑level hardware interface
    # ------------------------------------------------------------------
    def connect(self):
        """Establish communication with the wheel.

        Returns ``True`` on success and ``False`` otherwise.  When the device is
        opened we also read the current and maximum position so that the UI can
        be initialised.
        """
        if self.connected:
            return True

        # when the application is frozen PyInstaller unpacks data files into
        # a temporary directory referenced by _MEIPASS; __file__ may or may not
        # point inside that directory depending on how the module was imported.
        # building the path relative to _MEIPASS is more reliable than using
        # __file__ when console mode differs.
        if getattr(sys, 'frozen', False):
            base = getattr(sys, '_MEIPASS', os.path.dirname(__file__))
            self._log("running frozen; _MEIPASS=", base)
        else:
            base = os.path.dirname(__file__)
            self._log("running non‑frozen; module path=", base)

        sdk_path = os.path.abspath(os.path.join(base, "dev", "devices", "filter_wheel", "dll_sdk"))
        self._log(f"computed sdk_path = {sdk_path}")
        if os.path.isdir(sdk_path):
            self._log("contents:", os.listdir(sdk_path))
        if sdk_path not in sys.path:
            sys.path.append(sdk_path)
        try:
            # make sure Windows can locate the DLL even if cwd != sdk_path
            os.add_dll_directory(sdk_path)
        except Exception as exc:
            # some environments don't support add_dll_directory (old Python)
            self._log("os.add_dll_directory failed:", exc)

        try:
            import FWxC_COMMAND_LIB as fw
        except Exception as exc:
            self._log("SDK import error:", exc)
            self.connected = False
            return False

        self._fw = fw

        devices = fw.FWxCListDevices()
        # first try exact match
        handle = None
        for d in devices:
            if d[0] == self.serial:
                handle = fw.FWxCOpen(self.serial, 115200, 3)
                break
        # if not found, try substring match (serial digits etc.)
        if handle is None:
            for d in devices:
                if self.serial in d[0]:
                    print(f"[FilterWheel] using partial match '{d[0]}' for provided serial '{self.serial}'")
                    handle = fw.FWxCOpen(d[0], 115200, 3)
                    break
        if handle is None:
            self._log("available devices:", devices)
            self._log("device not listed or serial did not match:", self.serial)
            return False

        if handle < 0:
            self._log("failed to open", self.serial)
            self.connected = False
            return False
        self._handle = handle
        # apply sane defaults
        fw.FWxCSetTriggerMode(handle, 0)
        fw.FWxCSetSpeedMode(handle, 0)
        fw.FWxCSetSensorMode(handle, 0)

        self.position_count = self.get_position_count()
        self.current_position = self.get_position()
        self.connected = True
        return True

    def disconnect(self):
        if self.connected and getattr(self, "_fw", None) and self._handle is not None:
            try:
                self._fw.FWxCClose(self._handle)
            except Exception:
                pass
        self.connected = False
        self._handle = None

    def get_position_count(self):
        if self.connected and hasattr(self, "_fw"):
            arr = [0]
            if self._fw.FWxCGetPositionCount(self._handle, arr) >= 0:
                return arr[0]
        return None

    def get_position(self):
        # The Thorlabs API reports the wheel position using 1‑based numbering
        # (the original example script passed "3" and read back "3").  Earlier
        # code mistakenly added 1 here; that produced the one‑off mismatch and
        # prevented the GUI from ever selecting position 1 (sending 0 to the
        # device).  Keep the value exactly as returned by the hardware.
        if self.connected and hasattr(self, "_fw"):
            arr = [0]
            if self._fw.FWxCGetPosition(self._handle, arr) >= 0:
                pos = arr[0]
                self.current_position = pos
                self._log("read hardware position", pos)
                return pos
        return None

    def set_position(self, pos):
        # Pass the position through directly; hardware expects 1‑based values.
        if not self.connected or not hasattr(self, "_fw") or pos is None:
            return False
        ret = self._fw.FWxCSetPosition(self._handle, pos)
        if ret >= 0:
            self.current_position = pos
            self._log("set hardware position to", pos)
            return True
        self._log("failed to set hardware position", pos, "ret", ret)
        return False

    def step(self, delta):
        count = self.position_count or self.get_position_count()
        if count is None:
            return None
        curr = self.current_position or self.get_position()
        if curr is None:
            return None
        new = ((curr - 1 + delta) % count) + 1
        if self.set_position(new):
            return new
        return None

    def set_filter_name(self, pos, name):
        self.filter_names[pos] = name

    # ------------------------------------------------------------------
    # UI helpers (called by setup_frame)
    # ------------------------------------------------------------------
    def update_ui(self):
        """Refresh attached widgets based on the current state."""
        count = self.position_count or self.get_position_count()
        self.position_count = count
        if self._ui_dropdown and count:
            vals = []
            for i in range(1, count + 1):
                name = self.filter_names.get(i, "")
                vals.append(f"{i}: {name}" if name else str(i))
            try:
                self._ui_dropdown.configure(values=vals)
                curr = self.current_position or self.get_position()
                if curr is None:
                    curr = 1
                self._ui_position_var.set(vals[curr - 1])
            except Exception:
                pass
        state = "normal" if self.connected else "disabled"
        if self._ui_left_btn:
            self._ui_left_btn.configure(state=state)
        if self._ui_right_btn:
            self._ui_right_btn.configure(state=state)
        # settings button is intentionally left non-disableable so the user can
        # configure names even if the hardware is offline.

    def post_connect_update(self):
        """Called by the GUI after a successful connection.

        In addition to the previous behaviour of fetching the position count and
        names, start a short polling loop that watches for external changes to
        the wheel (e.g. the two physical jog buttons).  When a change is
        detected the UI is refreshed automatically.
        """
        self.position_count = self.get_position_count()
        self.current_position = self.get_position()
        for i in range(1, (self.position_count or 0) + 1):
            self.filter_names.setdefault(i, "")
        self.update_ui()
        # begin polling cycle (widget responsible for scheduling)
        self._start_polling()

    def _start_polling(self):
        """Schedule the first poll if we have a UI widget to drive the loop."""
        # use the dropdown widget's event loop to avoid creating threads
        if self._ui_dropdown and not getattr(self, '_poll_job', None):
            # schedule immediately
            try:
                self._poll_job = self._ui_dropdown.after(200, self._poll_position)
            except Exception:
                pass

    def _poll_position(self):
        """Read hardware position and update UI if it has changed."""
        # clear stored job id (will be set again later)
        self._poll_job = None
        if not self.connected:
            return
        prev = self.current_position
        pos = self.get_position()
        # if the hardware reported a different value than we previously knew,
        # refresh the GUI
        if pos is not None and pos != prev:
            self.update_ui()
        # re‑schedule if still connected
        if self.connected and self._ui_dropdown:
            try:
                self._poll_job = self._ui_dropdown.after(200, self._poll_position)
            except Exception:
                pass
