import seabreeze
import threading
import queue
import time

from dev.debugHelp import debugp


def _list_real_serials():
    """Return the serials the current backend can actually read right now.

    A device that enumerates but whose serial comes back empty or as ``'?'``
    is *seen* but not *reachable* -- typically because its USB driver binding
    no longer matches the active backend, or another process holds it open.
    cseabreeze does exactly this on the LM box (``seabreeze sees ['?']``),
    yet ``Spectrometer.from_serial_number()`` then fails with "No device
    attached". Such phantom entries must not count as a usable device, or the
    selector wrongly commits to a backend that can't open anything.
    """
    try:
        import seabreeze.spectrometers as _probe
        serials = []
        for dev in _probe.list_devices():
            serial = getattr(dev, "serial_number", None)
            if serial and str(serial).strip() not in ("", "?"):
                serials.append(str(serial))
        return serials
    except Exception:
        return []


def _teardown_seabreeze_probe():
    """Release any cached backend handles so the next access rebuilds clean.

    Switching backends after ``seabreeze.spectrometers`` has been imported
    only takes effect once the module's cached singletons (the API/library
    handle and the ``SeaBreezeDevice`` class) are dropped. We also shut the
    cached API down first so a ``'?'`` device cseabreeze is half-holding is
    released before pyseabreeze tries to enumerate it.
    """
    try:
        import seabreeze.spectrometers as _probe
    except Exception:
        return
    cached_api = getattr(_probe.list_devices, "_api", None)
    if cached_api is not None:
        for method_name in ("shutdown", "close"):
            method = getattr(cached_api, method_name, None)
            if callable(method):
                try:
                    method()
                except Exception:
                    pass
                break
    for cached in ("_lib", "SeaBreezeDevice"):
        _probe.__dict__.pop(cached, None)
    try:
        del _probe.list_devices._api
    except AttributeError:
        pass


def _select_seabreeze_backend():
    """Choose a seabreeze backend that can actually reach the spectrometer.

    On machines where Ocean Optics' OmniDriver has been installed, Windows
    binds the QE Pro to the libusb-win32 (``libusb0``) driver and the default
    ``cseabreeze`` backend (a compiled libseabreeze) finds it. On machines
    where Windows binds the device to its inbox ``WINUSB`` driver instead --
    e.g. a fresh laptop that's never had Ocean Optics software installed --
    libseabreeze sees nothing (or sees it with an unreadable ``'?'`` serial),
    but ``pyseabreeze`` (which talks via ``pyusb`` + ``libusb-1.0``) can reach
    a WINUSB-bound device.

    Try cseabreeze first to preserve the lab box's historical setup, but only
    keep it if it can read a *real* serial. If all it sees is a ``'?'`` phantom
    (the LM regression), tear it down and fall back to pyseabreeze. Whichever
    backend we land on, log what each one actually saw so a driver-level
    problem is obvious from the console/log.
    """
    try:
        seabreeze.use("cseabreeze")
        serials = _list_real_serials()
        print(f"[seabreeze] cseabreeze sees: {serials or '[] (none / unreadable)'}")
        if serials:
            return "cseabreeze"
    except Exception as e:
        print(f"[seabreeze] cseabreeze probe failed: {e}")

    # cseabreeze failed or only saw unreachable phantoms. Drop its cached
    # handles and try pyseabreeze, which reaches WINUSB-bound devices.
    try:
        _teardown_seabreeze_probe()
        seabreeze.use("pyseabreeze")
        serials = _list_real_serials()
        print(f"[seabreeze] pyseabreeze sees: {serials or '[] (none / unreadable)'}")
        return "pyseabreeze"
    except Exception as e:
        # pyseabreeze not importable (pyusb missing, etc.) -- fall back to
        # cseabreeze and let connect() surface a proper error.
        print(f"[seabreeze] pyseabreeze unavailable, keeping cseabreeze: {e}")
        try:
            seabreeze.use("cseabreeze")
        except Exception:
            pass
        return "cseabreeze"


_SEABREEZE_BACKEND = _select_seabreeze_backend()
print(f"[seabreeze] Using backend: {_SEABREEZE_BACKEND}")

import seabreeze.spectrometers as _sb_spec
from seabreeze.spectrometers import Spectrometer, list_devices


def _refresh_seabreeze_api():
    """Tear down the cached SeaBreezeAPI so the next list_devices() rebuilds it.

    seabreeze caches one SeaBreezeAPI instance at module scope
    (``list_devices._api``). If that instance was created before the USB
    device was ready, or its internal enumeration was invalidated by a
    previous close/reopen cycle, every subsequent call to list_devices()
    returns the same empty list. Recreating the API forces a fresh USB
    enumeration on the next call.
    """
    cached_api = getattr(_sb_spec.list_devices, "_api", None)
    if cached_api is None:
        return
    for method_name in ("shutdown", "close"):
        method = getattr(cached_api, method_name, None)
        if callable(method):
            try:
                method()
            except Exception:
                pass
            break
    try:
        del _sb_spec.list_devices._api
    except AttributeError:
        pass


class MySpectrometer():
    """Class for creating an object that communicates with and controls a spectrometer-type device"""

    def __init__(self, name, serial, enable=False, dark_correction=False, integration_time=100):
        """Create a new Spectrometer object for easy communication with the device concerned

        Parameters
        ------------
        name : `str`
            Visible name of this device in the graphical interface
        serial : `str`
            The unique device serial number enabling communication
        enable : `bool`, optional
            Allows or prevents the device from starting once it is connected. False by default
        dark_correction : `bool`, optional
            Whether to apply dark correction, False by default
        integration_time : `float`, optional
            Default spectrometer integration time in milliseconds, 100ms by default
        """
        self.name = name
        self.serial = serial
        self.enable = enable
        self.connected = False
        self.is_running = False
        
        self.chart_queue = queue.Queue(maxsize=1)
        self.save_queue = queue.Queue()
        self.integration_time = integration_time*1000
        self.acquire_save_data = 0
        self.dark_correction = dark_correction
        # If True, spectrometer will push data to save_queue when acquire_save_data > 0.
        # Can be temporarily disabled by callers (e.g. rotation mount sweeps) to avoid duplicate saves.
        self.auto_save_enabled = True


    def connect(self):
        """Try to establish communication with the device

        Retruns
        ------------
        connect : `bool`
            Whether communication is established
        """
        self.connected = False
        self.is_running = False
        try:
            self.spectrometer = self._open_seabreeze_device()

            # Enable the TEC (if the device has one) so it starts cooling, but
            # do NOT gate the connection on the current temperature. Requiring
            # temp < 0 caused the device to appear unreachable until the TEC
            # had fully cooled, which fails right after power-on. The user can
            # still monitor cooling progress via the temperature widget.
            try:
                self.get_temperature()
            except Exception:
                pass

            self.connected = True
            print(f"Connected to {self.name} ({self.serial})")
        except Exception as e:
            print(f"Failed to open {self.name} ({self.serial}): {e}")
            try:
                available = [d.serial_number for d in list_devices()]
                print(f"  seabreeze sees devices: {available}")
            except Exception as list_error:
                print(f"  seabreeze list_devices() also failed: {list_error}")
        return self.connected


    def _open_seabreeze_device(self):
        """Open the Spectrometer, recovering from common stuck-state failures.

        Two failures used to leave the device permanently unreachable until
        the whole process was restarted:
        1. seabreeze's cached SeaBreezeAPI returns an empty device list once
           it's seen one, even after the device is plugged back in or has
           recovered from a transient USB hiccup. We tear that cache down
           and let seabreeze rebuild it before retrying.
        2. seabreeze refuses to re-open a SeaBreezeDevice it still considers
           open (e.g. after a crash or an abnormal exit). We locate the
           matching cached handle, force-close it, and retry.
        """
        attempts = (
            (lambda: None,),
            (
                lambda: print(
                    f"{self.name} ({self.serial}) not found — refreshing seabreeze API and retrying"
                ),
                _refresh_seabreeze_api,
            ),
        )

        last_error = None
        for steps in attempts:
            for step in steps:
                step()
            try:
                return Spectrometer.from_serial_number(self.serial)
            except Exception as open_error:
                last_error = open_error
                message = str(open_error).lower()
                if "already open" in message or "already opened" in message:
                    print(
                        f"{self.name} ({self.serial}) reported already open — closing the stale handle"
                    )
                    for dev in list_devices():
                        if dev.serial_number == str(self.serial):
                            try:
                                dev.close()
                            except Exception:
                                pass
                            break
                    return Spectrometer.from_serial_number(self.serial)
                if "no device attached" not in message:
                    raise
        raise last_error


    def start(self):
        """Starts spectrometer data acquisition thread
        """
        if self.connected and not self.is_running:
            debugp("Thread", "Spectrometer thread started")
            #debugp("Thread", f"Spectrometer thread started - {self}")
            self.is_running = True
            self.data_thread = threading.Thread(target=self.acquire_data, daemon=True)
            self.data_thread.start()


    def acquire_data(self):
        """Spectrometer data acquisition loop with speed relative to acquisition time

        Notes
        ------------
        Data is added to two separate queues. These structures are thread-safe, ensuring data security and preventing loss.
        The first queue, `chart_queue`, is used for displaying the graph and operates independently of the second queue, 
        `save_queue`, which is dedicated to storing spectrometer save data
        """
        self.index = 0
        try:
            while self.is_running:
                try:
                    wavelengths, intensities = self.spectrometer.spectrum(correct_dark_counts=self.dark_correction)
                except Exception as e:
                    err_msg = str(e)
                    # pyseabreeze's OBP receive can lose framing if a read is
                    # interrupted or returns less than the full response. Its
                    # built-in recovery only drains 64 bytes after a header
                    # mismatch, but a QE Pro spectrum is ~4200 bytes, so the
                    # OS USB buffer stays poisoned for every subsequent read
                    # and we cascade into permanent failure. Manually drain
                    # any remaining bytes before retrying.
                    if (
                        "Header start_bytes wrong" in err_msg
                        or "Header protocol version wrong" in err_msg
                        or "remaining packet length mismatch" in err_msg
                    ):
                        self._drain_pyseabreeze_buffer()
                        continue
                    # A failed read used to break out of the whole loop, leaving
                    # is_running=True with a dead thread and a permanently blank
                    # canvas. Recover per-iteration instead. If dark correction is
                    # the unsupported feature, drop it and keep streaming.
                    if self.dark_correction:
                        print(f"Disabling dark correction for {self.name}: {e}")
                        self.dark_correction = False
                        continue
                    print(f"Error in spectrometer acquisition ({self.name}): {e}")
                    time.sleep(0.1)
                    continue

                if not self.chart_queue.empty():
                    try:
                        self.chart_queue.get_nowait()
                    except queue.Empty:
                        pass
                try:
                    self.chart_queue.put_nowait((wavelengths, intensities))
                except queue.Full:
                    pass

                # Only push into save_queue if automatic saving is enabled.
                if self.acquire_save_data > 0 and getattr(self, "auto_save_enabled", True):
                    self.index += 1
                    if self.index >= self.acquire_save_data:
                        self.index = 0
                        self.save_queue.put((wavelengths, intensities))
        except BaseException as fatal:
            # Anything escaping the inner handling kills the daemon thread
            # silently. Surface it so a dead acquisition is visible in the
            # console rather than appearing as a frozen canvas.
            import traceback
            print(f"Spectrometer acquisition thread for {self.name} died: {fatal!r}")
            traceback.print_exc()
            raise


    def _drain_pyseabreeze_buffer(self):
        """Drain leftover bytes from the spectrometer's USB read endpoint.

        When pyseabreeze's OBP receive() hits a malformed header it only
        reads 64 more bytes before raising. For a QE Pro one full spectrum
        is ~4200 bytes, so a single interrupted read leaves the OS USB
        buffer holding thousands of leftover bytes -- and every subsequent
        receive() picks one of them up as a "header" and fails again. We
        drain explicitly via the raw_usb_bus_access feature until reads
        time out (i.e. the buffer is genuinely empty), so the next
        spectrum request starts on a clean stream.
        """
        raw = getattr(getattr(self.spectrometer, "f", None), "raw_usb_bus_access", None)
        if raw is None:
            return 0
        total = 0
        while True:
            try:
                chunk = raw.raw_usb_read(endpoint="primary_in", buffer_length=4096)
            except Exception:
                break  # timeout => buffer is empty, we're done
            if not chunk:
                break
            total += len(chunk)
            if total > 200_000:
                break  # paranoia cap
        return total


    def stop(self):
        """Stops spectrometer data acquisition thread
        """
        self.is_running = False


    def disconnect(self):
        """Try to cleanly terminate communication with the device
        """
        if self.connected:
            self.stop()
            time.sleep(0.2)
            self.spectrometer.close() #Maybe we shouldn't use .close() ?
            self.connected = False
            print(f"{self.name} disconnected.")


    def set_integration_time(self, time_microseconds):
        """Sets the spectrometer integration time

        Parameters
        ------------
        time_microseconds : `float`
            The required spectrometer integration time
        """
        if self.connected:
            self.spectrometer.integration_time_micros(time_microseconds)
            self.integration_time = time_microseconds

    def get_temperature(self):
        # pyseabreeze's QE Pro device class doesn't expose the thermo_electric
        # feature at all (only cseabreeze does), so accessing it returns None
        # and every call would raise AttributeError. Short-circuit silently
        # here so the once-per-second update_temperature() poll doesn't spam
        # the console -- the temperature widget will just show "no reading".
        tec = getattr(getattr(self.spectrometer, "f", None), "thermo_electric", None)
        if tec is None:
            return None
        try:
            tec_status = tec.enable_tec(True)
            tec_temp = tec.read_temperature_degrees_celsius()
            debugp("TEC Enabled:", f"{self.name} : {tec_status}, temp : {tec_temp}c")
            return tec_temp
        except Exception as e:
            debugp("TEC", f"Tec not working : {e}")
        return

    def __repr__(self):
        return f"{self.name}, serial : {self.serial}"