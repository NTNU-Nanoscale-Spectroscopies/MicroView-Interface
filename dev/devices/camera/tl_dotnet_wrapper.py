"""
Lightweight Thorlabs .NET wrapper (adapted from Thorlabs' examples).

This module exposes `TL_SDK` and `TL_Camera` classes that wrap the
Thorlabs managed TLCamera SDK using pythonnet. It's intentionally small and
focused on discovery, opening cameras, and converting frames to numpy arrays.

Note: This wrapper assumes the Thorlabs managed assemblies are available
via CLR (pythonnet). Hardware testing and small adjustments may be required
depending on the exact driver build installed on the lab machine.
"""
from pathlib import Path
import logging
import traceback
_log = logging.getLogger("thorlabs_tl_wrapper")


def _dbg(msg):
    try:
        print(msg)
    except Exception:
        pass
    try:
        _log.debug(msg)
    except Exception:
        pass

try:
    import clr
    from System import IntPtr
    from System.Runtime.InteropServices import Marshal
except Exception:
    clr = None

import os


try:
    import numpy as np
    import ctypes
except Exception:
    np = None
    ctypes = None


def _add_dll_search_path(path):
    try:
        if os.path.isdir(path):
            try:
                os.add_dll_directory(path)
                _dbg(f"Added DLL search directory: {path}")
            except Exception:
                pass
            try:
                os.environ["PATH"] = f"{path};{os.environ.get('PATH', '')}"
                _dbg(f"Prepended PATH with: {path}")
            except Exception:
                pass
    except Exception:
        pass


_DLL_DIRS = []
_ASSEMBLY_RESOLVE_HOOKED = False


def _hook_assembly_resolve():
    """Ensure CLR can resolve dependent assemblies from our bundled dlls folders."""
    global _ASSEMBLY_RESOLVE_HOOKED
    if _ASSEMBLY_RESOLVE_HOOKED or clr is None:
        return
    try:
        from System import AppDomain
        from System.Reflection import Assembly

        def _resolve(sender, args):
            try:
                simple_name = (args.Name or '').split(',')[0]
            except Exception:
                simple_name = None
            if not simple_name:
                return None

            for d in list(_DLL_DIRS):
                try:
                    candidate = os.path.join(d, simple_name + '.dll')
                    if os.path.exists(candidate):
                        return Assembly.LoadFrom(candidate)
                except Exception:
                    continue
            return None

        AppDomain.CurrentDomain.AssemblyResolve += _resolve
        _ASSEMBLY_RESOLVE_HOOKED = True
        _dbg("Registered AppDomain.AssemblyResolve handler")
    except Exception as e:
        _dbg(f"Failed to register AssemblyResolve handler: {e}")


def _native_can_load(dll_name: str) -> bool:
    """Try LoadLibrary via ctypes to detect missing native deps early.

    This prevents a partially-constructed Thorlabs SDK from later throwing
    an unhandled exception in a finalizer thread (which can terminate the process).
    """
    if ctypes is None:
        return True
    for d in list(_DLL_DIRS):
        candidate = os.path.join(d, dll_name)
        if not os.path.exists(candidate):
            continue
        try:
            ctypes.WinDLL(candidate)
            return True
        except Exception as e:
            _dbg(f"Native preflight failed loading {dll_name} from {d}: {e}")
            return False
    _dbg(f"Native preflight: {dll_name} not found in dll search dirs")
    return False

if clr:
    # Try to add references commonly used in Thorlabs examples
    # First, try loading any DLLs we bundled in the local `dlls` folder by full path.
    # This mirrors the working pattern used in `kst201_shutter.py` and helps
    # pythonnet find managed assemblies inside frozen / temp extraction folders.
    try:
        # Look for the `dlls` folder in several likely locations.
        candidates = []
        base_dir = os.path.dirname(__file__)
        candidates.append(os.path.join(base_dir, 'dlls'))
        # also try current working dir (useful when running from project root)
        candidates.append(os.path.join(os.getcwd(), 'dev', 'devices', 'camera', 'dlls'))
        # also walk up from cwd looking for dev/devices/camera/dlls
        p = Path(os.getcwd()).resolve()
        for parent in [p] + list(p.parents):
            cand = parent / 'dev' / 'devices' / 'camera' / 'dlls'
            if cand.exists():
                candidates.append(str(cand))
                break

        # dedupe while preserving order
        seen = set()
        dll_dirs = []
        for c in candidates:
            if c and c not in seen:
                seen.add(c)
                dll_dirs.append(c)

        # make available globally for TL_SDK init and resolver hook
        _DLL_DIRS = list(dll_dirs)
        _hook_assembly_resolve()

        found_any = False
        for dll_dir in dll_dirs:
            if not os.path.isdir(dll_dir):
                _dbg(f"dlls folder not found at: {dll_dir}")
                continue
            _add_dll_search_path(dll_dir)
            _dbg(f"Scanning dlls folder: {dll_dir}")
            for f in os.listdir(dll_dir):
                if not f.lower().endswith('.dll'):
                    continue
                # Only load managed Thorlabs assemblies here. Do NOT attempt to load native
                # or C++/CLI bridge DLLs during import/startup (can hard-crash if deps missing).
                if not f.startswith('Thorlabs.TSI.'):
                    continue
                p = os.path.join(dll_dir, f)
                try:
                    # Some pythonnet builds accept AddReference with full path
                    try:
                        clr.AddReference(p)
                        _dbg(f"clr.AddReference succeeded: {p}")
                    except Exception:
                        # older/newer variants may not accept AddReference with path; try AddReferenceToFileAndPath if present
                        if hasattr(clr, 'AddReferenceToFileAndPath'):
                            clr.AddReferenceToFileAndPath(p)
                            _dbg(f"clr.AddReferenceToFileAndPath succeeded: {p}")
                        else:
                            _dbg(f"clr has no AddReferenceToFileAndPath and AddReference(path) failed for: {p}")
                    found_any = True
                except Exception as e:
                    _dbg(f"Failed to add reference for {p}: {e}")
        if not found_any:
            _dbg("No DLLs were added from any candidate dlls folder")
    except Exception as e:
        _dbg(f"Error scanning dlls folder for AddReference: {e}")

    # Then attempt AddReference by simple assembly name (fallback)
    for ref in ("Thorlabs.TSI.TLCamera", "Thorlabs.TSI.TLCameraInterfaces", "Thorlabs.TSI.ImageData", "Thorlabs.TSI.ColorInterfaces"):
        try:
            clr.AddReference(ref)
            _dbg(f"Added CLR reference by name: {ref}")
        except Exception as e:
            _dbg(f"Could not add CLR reference {ref}: {e}")

    try:
        # Import the parent namespace first and then access submodules/types.
        # Different pythonnet builds can expose CLR namespaces as packages differently,
        # so we try a few safe fallbacks instead of assuming `import Thorlabs.TSI.TLCamera` works.
        import Thorlabs
        thorlabs_tsi = None
        try:
            # Preferred: import the TSI namespace as a module
            from Thorlabs import TSI as thorlabs_tsi
        except Exception:
            try:
                # Some pythonnet variants expose nested namespaces as attributes
                thorlabs_tsi = getattr(Thorlabs, 'TSI', None)
            except Exception:
                thorlabs_tsi = None

        thorlabs_tsi_tlcamera = None
        thorlabs_tsi_tlcamerainterfaces = None
        thorlabs_tsi_imagedata = None

        if thorlabs_tsi is not None:
            try:
                thorlabs_tsi_tlcamera = getattr(thorlabs_tsi, 'TLCamera', None)
            except Exception:
                thorlabs_tsi_tlcamera = None
            try:
                thorlabs_tsi_tlcamerainterfaces = getattr(thorlabs_tsi, 'TLCameraInterfaces', None)
            except Exception:
                thorlabs_tsi_tlcamerainterfaces = None
            try:
                thorlabs_tsi_imagedata = getattr(thorlabs_tsi, 'ImageData', None)
            except Exception:
                thorlabs_tsi_imagedata = None

        # Fallback: try importing submodules directly (some pythonnet setups allow this)
        if thorlabs_tsi_tlcamera is None:
            try:
                from Thorlabs.TSI import TLCamera as thorlabs_tsi_tlcamera
            except Exception:
                thorlabs_tsi_tlcamera = None
        if thorlabs_tsi_tlcamerainterfaces is None:
            try:
                from Thorlabs.TSI import TLCameraInterfaces as thorlabs_tsi_tlcamerainterfaces
            except Exception:
                thorlabs_tsi_tlcamerainterfaces = None
        if thorlabs_tsi_imagedata is None:
            try:
                from Thorlabs.TSI import ImageData as thorlabs_tsi_imagedata
            except Exception:
                thorlabs_tsi_imagedata = None

        # Alias the SDK type if found
        if thorlabs_tsi_tlcamera is not None:
            TLCameraSDK = getattr(thorlabs_tsi_tlcamera, 'TLCameraSDK', None)
        else:
            TLCameraSDK = None
        if TLCameraSDK is None:
            _dbg("Importing Thorlabs managed modules: could not resolve TLCameraSDK via namespace fallbacks")
            # Reflection fallback: search all loaded CLR assemblies for the concrete TLCameraSDK class.
            # NOTE: Some pythonnet setups expose interfaces (e.g. ITLCameraSDK) but not the concrete
            # implementation via namespace imports. We must avoid resolving to an interface.
            try:
                from System import AppDomain
                assemblies = list(AppDomain.CurrentDomain.GetAssemblies())
                _dbg(f"Reflection fallback: scanning {len(assemblies)} loaded assemblies")

                def _is_concrete_type(t):
                    try:
                        if getattr(t, 'IsInterface', False):
                            return False
                        if getattr(t, 'IsAbstract', False):
                            return False
                        # pythonnet exposes IsClass for CLR types; keep it permissive if unavailable
                        if hasattr(t, 'IsClass') and not getattr(t, 'IsClass', True):
                            return False
                    except Exception:
                        return False
                    return True

                def _iter_types(asm):
                    """Return as many types as possible.

                    In frozen builds, Assembly.GetTypes() can raise ReflectionTypeLoadException
                    if any dependent assembly is missing; that exception still contains a partial
                    Types array we can scan.
                    """
                    try:
                        return list(asm.GetTypes())
                    except Exception as e:
                        try:
                            from System.Reflection import ReflectionTypeLoadException

                            if isinstance(e, ReflectionTypeLoadException):
                                try:
                                    types = [t for t in list(e.Types) if t is not None]
                                except Exception:
                                    types = []
                                # Emit a small hint (first loader exception) to aid debugging.
                                try:
                                    loader_excs = list(e.LoaderExceptions)
                                    if loader_excs:
                                        _dbg(f"GetTypes() loader exception (first): {loader_excs[0]}")
                                except Exception:
                                    pass
                                return types
                        except Exception:
                            pass
                        return []

                wanted_fullname = 'Thorlabs.TSI.TLCamera.TLCameraSDK'
                candidate = None
                itlcamerasdk = None

                # 0) Try direct lookup by full name on already loaded assemblies.
                for asm in assemblies:
                    try:
                        asm_name = asm.GetName().Name
                        if 'Thorlabs.TSI' not in (asm_name or ''):
                            continue
                        t = None
                        try:
                            # Assembly.GetType(string, bool throwOnError) is the safest option here.
                            t = asm.GetType(wanted_fullname, False)
                        except Exception:
                            t = None
                        if t is not None and _is_concrete_type(t):
                            candidate = t
                            _dbg(f"Reflection direct resolved TLCameraSDK -> {getattr(t, 'FullName', t)} in {asm_name}")
                            break
                    except Exception:
                        pass

                # 1) Exact full name match first.
                for asm in assemblies:
                    try:
                        if (asm.GetName().Name or '').startswith('Thorlabs.TSI.TLCamera'):
                            for t in _iter_types(asm):
                                fn = getattr(t, 'FullName', '') or ''
                                if fn == wanted_fullname and _is_concrete_type(t):
                                    candidate = t
                                    break
                    except Exception:
                        pass
                    if candidate is not None:
                        break

                # 2) Name match (TLCameraSDK), but reject interfaces/abstract types.
                if candidate is None:
                    for asm in assemblies:
                        try:
                            asm_name = asm.GetName().Name
                            if 'Thorlabs.TSI' not in (asm_name or ''):
                                continue
                            for t in _iter_types(asm):
                                nm = getattr(t, 'Name', '') or ''
                                fn = getattr(t, 'FullName', '') or ''
                                if nm in ('ITLCameraSDK', 'ITLCameraSdk'):
                                    itlcamerasdk = t
                                if nm == 'TLCameraSDK' and _is_concrete_type(t):
                                    _dbg(f"Reflection candidate type: {fn} in {asm_name}")
                                    candidate = t
                                    break
                        except Exception:
                            pass
                        if candidate is not None:
                            break

                # 3) Find a concrete type that exposes OpenTLCameraSDK.
                if candidate is None:
                    for asm in assemblies:
                        try:
                            asm_name = asm.GetName().Name
                            if 'Thorlabs.TSI' not in (asm_name or ''):
                                continue
                            for t in _iter_types(asm):
                                if not _is_concrete_type(t):
                                    continue
                                try:
                                    for m in t.GetMethods():
                                        if getattr(m, 'Name', '') == 'OpenTLCameraSDK' and getattr(m, 'IsStatic', False):
                                            candidate = t
                                            _dbg(f"Reflection candidate type (has OpenTLCameraSDK): {getattr(t, 'FullName', t)} in {asm_name}")
                                            break
                                except Exception:
                                    continue
                                if candidate is not None:
                                    break
                        except Exception:
                            pass
                        if candidate is not None:
                            break

                # 4) If we only found the interface, find a class implementing it.
                if candidate is None and itlcamerasdk is not None:
                    for asm in assemblies:
                        try:
                            asm_name = asm.GetName().Name
                            if 'Thorlabs.TSI' not in (asm_name or ''):
                                continue
                            for t in _iter_types(asm):
                                if not _is_concrete_type(t):
                                    continue
                                try:
                                    if itlcamerasdk.IsAssignableFrom(t):
                                        candidate = t
                                        _dbg(f"Reflection candidate type (implements ITLCameraSDK): {getattr(t, 'FullName', t)} in {asm_name}")
                                        break
                                except Exception:
                                    continue
                            if candidate is not None:
                                break
                        except Exception:
                            pass
                        if candidate is not None:
                            break

                if candidate is not None:
                    TLCameraSDK = candidate
                    _dbg(f"Reflection fallback resolved TLCameraSDK -> {getattr(candidate, 'FullName', candidate)}")
                else:
                    _dbg("Reflection fallback: could not find concrete TLCameraSDK type")
            except Exception as e:
                _dbg(f"Reflection fallback failed: {e}")
    except Exception as e:
        _dbg(f"Importing Thorlabs managed modules failed: {e}")
        TLCameraSDK = None
else:
    TLCameraSDK = None


class TL_SDK:
    """Python wrapper around the Thorlabs .NET TLCameraSDK."""
    def __init__(self):
        if TLCameraSDK is None:
            raise RuntimeError("TLCameraSDK not available via pythonnet")

        # Preflight: ensure the native/C++-CLI bridge can be loaded from our dll directories.
        # If this fails, calling OpenTLCameraSDK can leave a partially-constructed object
        # whose finalizer throws an unhandled exception (terminating the process).
        _hook_assembly_resolve()
        if not _native_can_load('thorlabs_tsi_camera_sdk1_cli.dll'):
            raise RuntimeError(
                "Thorlabs native dependency not loadable: thorlabs_tsi_camera_sdk1_cli.dll (or one of its dependencies). "
                "Copy the full ThorCam/Thorlabs SDK x64 runtime DLL set into dev/devices/camera/dlls and ensure the VC++ 2015-2022 x64 redistributable is installed."
            )
        # Try strategies in order: static OpenTLCameraSDK, Activator.CreateInstance, direct call
        try:
            # 1) Try static OpenTLCameraSDK via MethodInfo or attribute
            try:
                open_method = None
                if hasattr(TLCameraSDK, 'GetMethod'):
                    try:
                        open_method = TLCameraSDK.GetMethod('OpenTLCameraSDK')
                    except Exception:
                        open_method = None
                elif hasattr(TLCameraSDK, 'OpenTLCameraSDK'):
                    open_method = getattr(TLCameraSDK, 'OpenTLCameraSDK')

                def _try_invoke_open(method_info):
                    if not hasattr(method_info, 'Invoke'):
                        return method_info()
                    try:
                        params = list(method_info.GetParameters())
                    except Exception:
                        params = None
                    if params is None or len(params) == 0:
                        return method_info.Invoke(None, None)
                    if len(params) == 1:
                        for arg in (False, True, None, 0, ""):
                            try:
                                return method_info.Invoke(None, [arg])
                            except Exception:
                                continue
                    if len(params) == 2:
                        for args in ((False, False), (False, True), (True, False), (True, True), (None, None)):
                            try:
                                return method_info.Invoke(None, list(args))
                            except Exception:
                                continue
                    try:
                        return method_info.Invoke(None, [None] * len(params))
                    except Exception:
                        raise

                if open_method is not None:
                    try:
                        if hasattr(open_method, 'Invoke'):
                            self.sdk = _try_invoke_open(open_method)
                        else:
                            self.sdk = open_method()
                        _dbg("TL_SDK initialized via OpenTLCameraSDK")
                        return
                    except Exception as e:
                        _dbg(f"OpenTLCameraSDK invocation failed; trying other strategies: {e}")

                # If TLCameraSDK is a CLR Type, scan all overloads of OpenTLCameraSDK
                try:
                    if hasattr(TLCameraSDK, 'GetMethods'):
                        for m in TLCameraSDK.GetMethods():
                            try:
                                if getattr(m, 'Name', '') == 'OpenTLCameraSDK':
                                    try:
                                        self.sdk = _try_invoke_open(m)
                                        _dbg("TL_SDK initialized via OpenTLCameraSDK overload")
                                        return
                                    except Exception:
                                        continue
                            except Exception:
                                continue
                except Exception:
                    pass
            except Exception:
                _dbg("Error while attempting OpenTLCameraSDK; continuing")

            # 2) Try Activator.CreateInstance for CLR Type
            try:
                from System import Activator
                try:
                    self.sdk = Activator.CreateInstance(TLCameraSDK)
                    _dbg("TL_SDK initialized via Activator.CreateInstance")
                    return
                except Exception:
                    try:
                        self.sdk = Activator.CreateInstance(TLCameraSDK, True)
                        _dbg("TL_SDK initialized via Activator.CreateInstance(non-public)")
                        return
                    except Exception:
                        _dbg("Activator.CreateInstance failed; trying direct call")
            except Exception:
                _dbg("Activator not available or create instance failed; continuing")

            # 3) Last resort: direct callable (pythonnet may expose a class-like object)
            try:
                if callable(TLCameraSDK):
                    self.sdk = TLCameraSDK()
                    _dbg("TL_SDK initialized via direct call")
                    return
            except Exception:
                _dbg("Direct call of TLCameraSDK failed")

            # Nothing worked
            raise RuntimeError("Could not construct TLCameraSDK instance via known strategies")
        except Exception as e:
            _dbg(f"TL_SDK init failed: {e}\n{traceback.format_exc()}")
            raise

    def DiscoverAvailableCameras(self):
        try:
            return self.sdk.DiscoverAvailableCameras()
        except Exception as e:
            _dbg(f"DiscoverAvailableCameras failed: {e}")
            raise

    def OpenCamera(self, camera_id, raw=False):
        """Open camera by serial or index. If raw=True return managed camera object,
        otherwise return the managed object (we keep TL_Camera as optional wrapper).
        """
        try:
            # Accept int index or serial string
            cam = camera_id
            if isinstance(camera_id, int):
                cams = self.sdk.DiscoverAvailableCameras()
                cam = cams[camera_id]
            opened = None
            try:
                opened = self.sdk.OpenCamera(str(cam), False)
            except TypeError:
                # older signatures may not accept the second arg
                opened = self.sdk.OpenCamera(str(cam))
            _dbg(f"OpenCamera returned: {opened}")
            return opened
        except Exception as e:
            _dbg(f"OpenCamera failed: {e}\n{traceback.format_exc()}")
            raise


class TL_Camera:
    """Thin wrapper around a managed TLCamera object exposing array conversion."""
    def __init__(self, sdk, camera):
        self.sdk = sdk
        self.camera = camera

    def GetPendingFrameOrNull(self):
        try:
            return self.camera.GetPendingFrameOrNull()
        except Exception as e:
            _dbg(f"GetPendingFrameOrNull failed: {e}")
            raise

    def frame_to_array(self, frame):
        """Convert a managed frame to a numpy uint16 array (mono) when possible."""
        if frame is None:
            return None
        if np is None or ctypes is None:
            raise RuntimeError("numpy/ctypes required for frame conversion")
        try:
            # Many Thorlabs frames expose ImageData.ImageData_monoOrBGR or ImageData
            image = None
            try:
                image = frame.ImageData.ImageData_monoOrBGR
            except Exception:
                try:
                    image = frame.ImageData
                except Exception:
                    image = frame

            length = None
            try:
                length = int(image.Length)
            except Exception:
                try:
                    length = int(len(image))
                except Exception:
                    length = None

            if length is None:
                _dbg("Could not determine managed image length")
                return None

            dest = np.zeros(length, dtype=np.uint16)
            ptr = IntPtr(dest.__array_interface__['data'][0])
            # Marshal.Copy(managedArray, startIndex, IntPtr, length)
            Marshal.Copy(image, 0, ptr, length)
            # Reshape if frame contains dimensions
            try:
                h = int(frame.ImageData.Height_pixels)
                w = int(frame.ImageData.Width_pixels)
                dest = dest.reshape((h, w))
            except Exception:
                pass
            return dest
        except Exception as e:
            _dbg(f"frame_to_array conversion failed: {e}\n{traceback.format_exc()}")
            return None


def test_wrapper():
    if clr is None:
        print("pythonnet not available")
        return
    sdk = TL_SDK()
    cams = sdk.DiscoverAvailableCameras()
    print('discovered:', cams)


if __name__ == '__main__':
    test_wrapper()
