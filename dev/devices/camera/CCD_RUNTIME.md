# CCD8051 / TLCameraSDK runtime notes (Windows)

This project supports Thorlabs cameras via two paths:

- **Zelux/TSI python SDK path** (ctypes wrapper under `dev/devices/camera/camera_sdk/`)
- **Legacy CCD path via pythonnet + TLCameraSDK** (wrapper: `dev/devices/camera/tl_dotnet_wrapper.py`)

This document is for the **legacy CCD path**.

## Quick sanity check

Run the minimal probe (no acquisition):

```powershell
python -m dev.devices.camera.ccd_probe 11499
```

Expected:
- `native_can_load: True`
- `TLCameraSDK: <class 'Thorlabs.TSI.TLCamera.TLCameraSDK'>`
- `discovered: ['11499']`
- `opened: ...`

## Required files (bundled next to the app)

The app expects Thorlabs SDK DLLs under:

- `dev/devices/camera/dlls/` (source tree)
- In the frozen exe, the same folder is extracted under `_MEI...\dev\devices\camera\dlls`.

At minimum, you need:
- Managed .NET assemblies: `Thorlabs.TSI.*.dll` (e.g. `Thorlabs.TSI.TLCamera.dll`, `Thorlabs.TSI.Core.dll`, etc.)
- The native / C++-CLI bridge and its dependency chain used by TLCameraSDK (commonly includes `thorlabs_tsi_camera_sdk1_cli.dll` and additional native DLLs installed with ThorCam/Thorlabs drivers).

`tl_dotnet_wrapper.py` adds this folder via `os.add_dll_directory()` and prepends it to `PATH` at runtime.

## Common prerequisites

If the camera is discovered but open/acquisition fails, it is usually due to missing prerequisites on the target machine:

- **Thorlabs driver/runtime install**: install the official Thorlabs camera software/driver package that matches the camera family (often distributed with ThorCam). This typically installs required native DLLs and device drivers.
- **Microsoft Visual C++ redistributables**:
  - VC++ **2015–2022 x64** is commonly required by modern Thorlabs native components.
  - If you see dependencies like **`MSVCR90.dll`** (VC++ 2008), install the **VC++ 2008** runtime as well (some legacy framegrabber components depend on it).

## Notes on diagnostics

- If the log shows `TLCameraSDK ... ITLCameraSDK` (an interface) and then fails to construct the SDK, you’re running an old build; rebuild the exe so it includes the fixed TLCameraSDK type-resolution logic.
- Messages like `EDT pdv open failed` indicate a lower-level transport/driver problem (board/driver/runtime), not a Python import problem. Verify the camera works in the vendor software on the same machine.
