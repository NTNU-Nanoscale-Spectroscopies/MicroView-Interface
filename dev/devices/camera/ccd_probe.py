"""Quick probe for Thorlabs TLCameraSDK (legacy CCD path).

Usage (PowerShell):
    python -m dev.devices.camera.ccd_probe

This is intended to be a minimal, non-GUI sanity check that:
- the managed assemblies load,
- the SDK opens,
- camera serials are discovered,
- a specific serial can be opened.

It does NOT start acquisition.
"""

from __future__ import annotations

import sys


def main(argv: list[str]) -> int:
    from dev.devices.camera import tl_dotnet_wrapper as t

    print("native_can_load:", t._native_can_load("thorlabs_tsi_camera_sdk1_cli.dll"))
    print("TLCameraSDK:", getattr(t, "TLCameraSDK", None))

    sdk = t.TL_SDK()
    cams = sdk.DiscoverAvailableCameras()
    serials = [str(x) for x in list(cams)]
    print("discovered:", serials)

    serial = argv[1] if len(argv) > 1 else (serials[0] if serials else None)
    if not serial:
        print("No cameras discovered.")
        return 2

    cam = sdk.OpenCamera(serial)
    print("opened:", cam)
    try:
        print("SerialNumber:", getattr(cam, "SerialNumber"))
    except Exception:
        pass
    try:
        print("Model:", getattr(cam, "Model"))
    except Exception:
        pass

    try:
        cam.Dispose()
    except Exception:
        pass

    try:
        sdk.sdk.Dispose()
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
