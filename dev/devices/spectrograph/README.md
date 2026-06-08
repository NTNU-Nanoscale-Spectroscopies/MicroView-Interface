# Andor Kymera 328i setup

This package is the project-facing setup layer for the Andor Kymera 328i spectrograph.

MicroView is deployed on Windows machines only, so this setup keeps the Windows Andor SDK layout and DLL lookup paths.

## Layout

- `kymera_328i.py` defines `MyKymera328i`, a `MySpectrometer` subclass so the existing MicroView UI can discover it as a normal spectrometer.
- `sim_kymera_328i.py` defines `MySimKymera328i` for UI and save-flow testing without hardware.
- `andor_setup.py` adds the vendored SDK folder to `sys.path` and configures Windows DLL lookup for the current Python process.
- `andor_sdk/pyAndorSDK2/` is the Andor SDK2 Python wrapper for the attached detector/camera.
- `andor_sdk/pyAndorSpectrograph/` is the Andor spectrograph Python wrapper for gratings, wavelength, slits, mirrors, and related optics.

The native Windows DLLs are bundled inside the package folders. The 64-bit DLLs are also flattened directly into each `libs/` folder because the Andor wrappers search that location at import/runtime:

- `andor_sdk/pyAndorSDK2/libs/atmcd64d.dll`
- `andor_sdk/pyAndorSpectrograph/libs/atspectrograph.dll`

`microview.spec` also collects `andor_sdk/` and the flattened DLLs so frozen PyInstaller builds keep the same local SDK layout.

## Current status

This is a setup scaffold, not a finished device driver. `MyKymera328i.connect()` initializes the two Andor SDK wrappers and stores the handles, but continuous acquisition is intentionally left for the next implementation step.

For a detailed summary of the GUI-first Kymera/Newton work already completed, see `KYMERA_GUI_HANDOFF.md` in this same folder.

The methods already present for UI compatibility are:

- `connect()`
- `start()`
- `stop()`
- `disconnect()`
- `set_integration_time()`
- `acquire_data()`
- `get_temperature()`

## Enabling in `main.py`

`main.py` imports both classes and contains commented examples near the GM microscope configuration:

```python
#MyKymera328i("Kymera 328i", "KY328I-XXXX", enable=True, integration_time=100),
#MySimKymera328i("Kymera 328i (sim)", "SIM-KYMERA-328I", enable=True, integration_time=100),
```

Uncomment the real device line when the hardware serial/configuration is known. Use the simulator line for UI testing away from the lab.

## Next implementation steps

1. Confirm the detector model and working Andor initialization sequence in the lab.
2. Configure camera read mode/acquisition mode for full vertical binning or the desired detector readout.
3. Use `ATSpectrograph.GetCalibration(device_index, number_pixels)` for wavelengths.
4. Implement `acquire_data()` to push `(wavelengths, intensities)` into `chart_queue` and `save_queue`, matching `MySpectrometer`.
5. Add hardware smoke tests or a small diagnostic script once the real Kymera/detector pair is available.
