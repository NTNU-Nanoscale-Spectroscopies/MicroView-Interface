"""
Minimal pythonnet-based wrapper scaffold for Thorlabs legacy CCD cameras (e.g. CCD8051).

This module provides a best-effort runtime adapter that tries to load Thorlabs CCD
DLLs shipped in `dev/devices/camera/dlls` using pythonnet (CLR) and reflection. The goal
is to provide `discover_available_cameras()` and `open_camera(serial)` methods similar to
the existing `TLCameraSDK` wrapper so the application can attempt to connect to older CCDs.

This is a scaffold: exact method and type names differ across Thorlabs driver versions, so
the code probes the loaded assemblies for plausible types and methods and logs useful
diagnostics. When the correct assembly and types are present the adapter should be able to
discover and open cameras; if not, the logs will indicate which reflection calls failed.

This file requires `pythonnet` (clr). It does not implement full streaming translation
—the returned camera object is a thin wrapper exposing only the small subset the app
currently uses (arm, issue_software_trigger, get_pending_frame_or_null, set exposure).

Hardware testing is required; iterate on the reflection helpers if Thorlabs shipped
different symbol names for your driver build.
"""
from pathlib import Path
import sys
import os
import traceback
import logging

_logger = logging.getLogger("thorlabs_ccd_adapter")

# Add a small RotatingFileHandler for easier on-site debugging. If logging
# cannot be configured (e.g., permission issues) we silently continue and
# rely on the application's central logging.
from logging.handlers import RotatingFileHandler
try:
    log_dir = Path(__file__).resolve().parent.parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "thorlabs_ccd_adapter.log"
    if not _logger.handlers:
        handler = RotatingFileHandler(str(log_file), maxBytes=5_000_000, backupCount=3)
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        handler.setFormatter(formatter)
        _logger.addHandler(handler)
    _logger.setLevel(logging.DEBUG)
except Exception:
    # If file logging setup fails, continue without it — app may configure logging.
    pass

try:
    import clr
    from System import Activator
    from System.Reflection import Assembly
except Exception:
    clr = None


def _dbg(msg):
    """Debug helper: print to stdout (for terminal visibility) and also log via logging."""
    try:
        print(msg)
    except Exception:
        pass
    try:
        _logger.debug(msg)
    except Exception:
        pass


class CCDAdapterError(Exception):
    pass


class CCDSDK:
    """Best-effort SDK loader for Thorlabs CCD DLLs.

    Usage:
      sdk = CCDSDK(dll_search_paths=[...])
      cams = sdk.discover_available_cameras()
      cam = sdk.open_camera(serial)
    """

    def __init__(self, dll_search_paths=None):
        self.dll_search_paths = dll_search_paths or []
        # default to bundled dlls folder next to this file
        default = Path(__file__).parent / "dlls"
        if default.exists():
            self.dll_search_paths.append(str(default))
        self._loaded_assemblies = []
        self._dotnet_sdk = None
        _dbg(f"CCDSDK init, dll_search_paths={self.dll_search_paths}")
        self._probe_assemblies()
        # After probing file-based assemblies, attempt to init the Thorlabs dotnet wrapper
        try:
            self._try_init_dotnet_wrapper()
        except Exception:
            _logger.debug("DotNet TLCamera wrapper init attempt failed")

    def _probe_assemblies(self):
        if not clr:
            _logger.debug("pythonnet (clr) not available; CCD adapter disabled")
            return

        def _should_load_as_managed(dll_path: Path) -> bool:
            """Only load managed Thorlabs assemblies here.

            Loading native DLLs or C++/CLI bridges (like `thorlabs_tsi_camera_sdk1_cli.dll`)
            during application startup can crash the process if their native dependencies
            aren't on the DLL search path yet.
            """
            name = dll_path.name
            if name.startswith("Thorlabs.TSI.") and name.lower().endswith(".dll"):
                return True
            return False

        for p in self.dll_search_paths:
            try:
                pth = Path(p)
                if pth.is_dir():
                    for dll in pth.iterdir():
                        if dll.suffix.lower() in ('.dll',):
                            if not _should_load_as_managed(dll):
                                continue
                            try:
                                # Use LoadFrom to avoid probing paths; Assembly.LoadFile is available
                                asm = Assembly.LoadFile(str(dll.resolve()))
                                self._loaded_assemblies.append(asm)
                                _logger.debug(f"Loaded assembly: {dll}")
                            except Exception as e:
                                _logger.debug(f"Failed to load assembly {dll}: {e}")
                elif pth.is_file() and pth.suffix.lower() == '.dll':
                    if not _should_load_as_managed(pth):
                        continue
                    try:
                        asm = Assembly.LoadFile(str(pth.resolve()))
                        self._loaded_assemblies.append(asm)
                        _logger.debug(f"Loaded assembly: {pth}")
                    except Exception as e:
                        _logger.debug(f"Failed to load assembly {pth}: {e}")
            except Exception as e:
                _logger.debug(f"Error scanning path {p}: {e}")

        try:
            _dbg(f"Loaded assemblies: {[a.FullName for a in self._loaded_assemblies]}")
        except Exception:
            pass

    def _try_init_dotnet_wrapper(self):
        """Attempt to import the Thorlabs .NET TLCamera wrapper used in their examples.
        This follows the pattern in Thorlabs' `tl_dotnet_wrapper.py` example: add CLR
        references for common Thorlabs assemblies and create an SDK instance.
        """
        # Prefer using the wrapper module we added (tl_dotnet_wrapper) which
        # implements the Thorlabs example TL_SDK/TL_Camera classes. This centralizes
        # the DOTNET-related code and makes runtime behavior more predictable.
        if not clr:
            _dbg("pythonnet not available; skipping dotnet wrapper init")
            return
        try:
            from . import tl_dotnet_wrapper
            try:
                sdk = tl_dotnet_wrapper.TL_SDK()
                self._dotnet_sdk = sdk
                _dbg("Initialized TL_SDK from tl_dotnet_wrapper")
            except Exception as e:
                _dbg(f"tl_dotnet_wrapper.TL_SDK init failed: {e}")
        except Exception as e:
            _dbg(f"Could not import tl_dotnet_wrapper: {e}")

    def _find_types(self, predicate):
        """Return list of CLR types matching predicate(type).

        `predicate` receives a System.Type object; we call its Name and FullName properties.
        """
        types = []
        if not clr:
            return types
        for asm in self._loaded_assemblies:
            try:
                for t in asm.GetTypes():
                    try:
                        if predicate(t):
                            types.append(t)
                    except Exception:
                        pass
            except Exception:
                pass
        return types

    def discover_available_cameras(self):
        """Probe loaded assemblies for a camera-discovery API and return serial list.

        This function tries several common method/property names used by Thorlabs SDKs.
        """
        if not clr:
            raise CCDAdapterError("pythonnet not available")

        # Prefer the .NET TLCameraSDK if available (matches Thorlabs example wrapper)
        if self._dotnet_sdk is not None:
            try:
                cams = self._dotnet_sdk.DiscoverAvailableCameras()
                try:
                    seq = list(cams)
                    _dbg(f"dotnet discovered cameras: {seq}")
                    return [str(s) for s in seq]
                except Exception:
                    s = str(cams).split()
                    _dbg(f"dotnet discovered cameras (fallback split): {s}")
                    return s
            except Exception as e:
                _dbg(f"dotnet DiscoverAvailableCameras failed: {e}")

        # try to find a type with a static 'DiscoverAvailableCameras' or 'DiscoverCameras' method
        candidates = self._find_types(lambda t: 'Camera' in t.Name or 'Manager' in t.Name)
        _logger.debug(f"CCD discovery: found candidate types: {[t.Name for t in candidates]}")
        serials = []
        for t in candidates:
            try:
                # look for static methods
                for meth_name in ('DiscoverAvailableCameras', 'DiscoverCameras', 'GetAvailableCameras'):
                    m = None
                    try:
                        m = t.GetMethod(meth_name)
                    except Exception:
                        m = None
                    if m is not None:
                        try:
                            result = m.Invoke(None, None)
                            # result may be an array of strings or a delimited string
                            if result is None:
                                continue
                            # try to convert to python list
                            try:
                                seq = list(result)
                                for s in seq:
                                    serials.append(str(s))
                            except Exception:
                                # fallback: single string
                                serials.extend(str(result).split())
                            if serials:
                                return serials
                        except Exception:
                            _logger.debug(f"Calling {t.FullName}.{meth_name} failed: {traceback.format_exc()}")
                # look for static property
                for prop_name in ('AvailableCameras', 'Cameras'):
                    try:
                        p = t.GetProperty(prop_name)
                        if p is None:
                            continue
                        result = p.GetValue(None, None)
                        if result is None:
                            continue
                        try:
                            seq = list(result)
                            for s in seq:
                                serials.append(str(s))
                        except Exception:
                            serials.extend(str(result).split())
                        if serials:
                            return serials
                    except Exception:
                        pass
            except Exception:
                pass

        # no candidates returned anything meaningful
        return serials

    def open_camera(self, serial):
        """Attempt to open a camera by serial. Returns a dynamic wrapper object on success.

        The returned object implements a minimal subset used by the rest of the app:
          - frames_per_trigger_zero_for_unlimited (settable)
          - arm(frames)
          - issue_software_trigger()
          - get_pending_frame_or_null() -> returns an object with `image_buffer` property as numpy array
          - exposure_time_us property (get/set)
          - dispose()/close() methods

        This adapter will attempt to find a suitable factory/open method on loaded assemblies.
        """
        if not clr:
            raise CCDAdapterError("pythonnet not available")

        # If the Thorlabs .NET wrapper initialized, prefer opening via that SDK
        if self._dotnet_sdk is not None:
            try:
                # The .NET API uses OpenCamera(serial, bool)
                try:
                    opened = self._dotnet_sdk.OpenCamera(str(serial), False)
                except TypeError:
                    opened = self._dotnet_sdk.OpenCamera(str(serial))
                if opened is not None:
                    _dbg("Opened camera via dotnet SDK")
                    return CCDCameraWrapper(opened)
            except Exception as e:
                _dbg(f"dotnet OpenCamera failed: {e}")

        # find candidate types again
        candidates = self._find_types(lambda t: 'Camera' in t.Name or 'Manager' in t.Name or 'Device' in t.Name)
        _logger.debug(f"open_camera: candidate types: {[t.Name for t in candidates]}")

        for t in candidates:
            try:
                # try common factory method names
                for open_name in ('OpenCamera', 'Open', 'CreateCamera', 'GetCamera'):
                    try:
                        m = t.GetMethod(open_name)
                    except Exception:
                        m = None
                    if m is None:
                        continue
                    try:
                        # try invoke: some methods expect serial as string parameter
                        res = None
                        try:
                            res = m.Invoke(None, [serial])
                        except Exception:
                            try:
                                res = m.Invoke(None, None)
                            except Exception:
                                res = None
                        if res is None:
                            continue
                        # Wrap the returned CLR object in a Python adapter
                        return CCDCameraWrapper(res)
                    except Exception:
                        _logger.debug(f"Failed to call {t.FullName}.{open_name}: {traceback.format_exc()}")
            except Exception:
                pass

        raise CCDAdapterError("No supported open_camera API found in loaded CCD assemblies")


class CCDCameraWrapper:
    """Minimal wrapper around a CLR camera object. Many methods are best-effort and may need
    adaptation to the concrete SDK present on the machine under test.
    """

    def __init__(self, clr_camera_obj):
        self._cam = clr_camera_obj

    def arm(self, frames):
        try:
            if hasattr(self._cam, 'Arm'):
                self._cam.Arm(frames)
            elif hasattr(self._cam, 'arm'):
                self._cam.arm(frames)
        except Exception:
            _logger.debug(f"arm() failed: {traceback.format_exc()}")

    def issue_software_trigger(self):
        try:
            if hasattr(self._cam, 'IssueSoftwareTrigger'):
                self._cam.IssueSoftwareTrigger()
            elif hasattr(self._cam, 'issue_software_trigger'):
                self._cam.issue_software_trigger()
        except Exception:
            _logger.debug(f"issue_software_trigger failed: {traceback.format_exc()}")

    @property
    def frames_per_trigger_zero_for_unlimited(self):
        try:
            if hasattr(self._cam, 'FramesPerTriggerZeroForUnlimited'):
                return int(self._cam.FramesPerTriggerZeroForUnlimited)
            elif hasattr(self._cam, 'frames_per_trigger_zero_for_unlimited'):
                return int(self._cam.frames_per_trigger_zero_for_unlimited)
        except Exception:
            pass
        return 0

    @frames_per_trigger_zero_for_unlimited.setter
    def frames_per_trigger_zero_for_unlimited(self, v):
        try:
            if hasattr(self._cam, 'FramesPerTriggerZeroForUnlimited'):
                self._cam.FramesPerTriggerZeroForUnlimited = int(v)
            elif hasattr(self._cam, 'frames_per_trigger_zero_for_unlimited'):
                self._cam.frames_per_trigger_zero_for_unlimited = int(v)
        except Exception:
            _logger.debug(f"setting frames_per_trigger failed: {traceback.format_exc()}")

    def get_pending_frame_or_null(self):
        """Attempt to retrieve a frame and convert to a numpy array buffer.

        Returns an object with `.image_buffer` property (numpy array) or None.
        """
        try:
            # try common polling method names
            for name in ('GetPendingFrameOrNull', 'get_pending_frame_or_null', 'PollFrame', 'GetFrame'):
                try:
                    if hasattr(self._cam, name):
                        fn = getattr(self._cam, name)
                        fr = fn()
                        # try to extract a raw buffer
                        if fr is None:
                            return None
                        # best-effort conversion
                        try:
                            # some SDKs expose ImageBuffer as a managed array
                            buf = getattr(fr, 'ImageBuffer', None) or getattr(fr, 'image_buffer', None)
                            if buf is None:
                                # try the frame object itself if it's already a numpy array-like
                                return SimpleFrame(self._to_numpy(fr))
                            return SimpleFrame(self._to_numpy(buf))
                        except Exception:
                            return None
                except Exception:
                    continue
        except Exception:
            _logger.debug(f"get_pending_frame_or_null failed: {traceback.format_exc()}")
        return None

    def _to_numpy(self, managed_buf):
        """Try to convert common CLR array/buffer types to a numpy array.

        This is highly dependent on the actual SDK. We try a few approaches and fall back to None.
        """
        try:
            import numpy as np
        except Exception:
            return None

        try:
            # If it's already an iterable of numbers, try to coerce
            seq = list(managed_buf)
            return np.array(seq)
        except Exception:
            pass
        try:
            # Some managed arrays expose a 'ToByteArray' or similar
            if hasattr(managed_buf, 'ToByteArray'):
                b = managed_buf.ToByteArray()
                return np.frombuffer(b, dtype=np.uint16)
        except Exception:
            pass
        return None

    @property
    def exposure_time_us(self):
        try:
            if hasattr(self._cam, 'ExposureTimeUs'):
                return int(self._cam.ExposureTimeUs)
            elif hasattr(self._cam, 'exposure_time_us'):
                return int(self._cam.exposure_time_us)
        except Exception:
            pass
        return None

    @exposure_time_us.setter
    def exposure_time_us(self, value):
        try:
            if hasattr(self._cam, 'ExposureTimeUs'):
                self._cam.ExposureTimeUs = int(value)
            elif hasattr(self._cam, 'exposure_time_us'):
                self._cam.exposure_time_us = int(value)
        except Exception:
            _logger.debug(f"Setting exposure failed: {traceback.format_exc()}")

    def dispose(self):
        try:
            if hasattr(self._cam, 'Dispose'):
                self._cam.Dispose()
            elif hasattr(self._cam, 'dispose'):
                self._cam.dispose()
        except Exception:
            pass


class SimpleFrame:
    def __init__(self, numpy_buffer):
        self.image_buffer = numpy_buffer


def test_loader():
    sdk = CCDSDK()
    try:
        cams = sdk.discover_available_cameras()
        print('CCD discovery result:', cams)
    except Exception as e:
        print('CCD discovery failed:', e)


if __name__ == '__main__':
    test_loader()
