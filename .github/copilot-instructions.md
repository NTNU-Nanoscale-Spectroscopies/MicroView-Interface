# Copilot / AI Assistant Instructions for MicroView-Interface

Purpose: Help AI coding agents be immediately productive editing, building, and extending MicroView.

- **Big picture**: MicroView is a Python GUI (CustomTkinter) application that centralizes microscope devices. The GUI entrypoint is `main.py` which creates `MyMicroscope` instances and starts `MyApp` in `dev/application.py`.

- **Key components**:
  - `main.py`: application entry — constructs `MyMicroscope` objects using classes from `dev/devices/` and starts the GUI.
  - `dev/application.py`: main GUI class (`MyApp`) and `MyMicroscope` container. Shows how frames (`dev/widgets/*`) and device frames integrate.
  - `dev/devices/`: hardware wrappers and simulators. Real drivers (e.g. `camera`, `shutter`) and `sim_*` simulators live here.
  - `dev/file_system.py`: responsible for backup directory conventions and file naming (important when adding data export features).
  - `microview.spec`: PyInstaller spec used to build the distributable. It explicitly declares `datas` for images, themes and device dlls.
  - `requirements.txt`: pinned runtime dependencies (CustomTkinter, searbr eeze, pyinstaller, etc.).

- **Why this structure**: devices are isolated under `dev/devices` to separate hardware-specific code and provide simulators for development without hardware. GUI code lives in `dev/widgets` and is driven by `dev/application.py`.

- **Build / run / packaging**:
  - Local dev: create a venv and install deps: `python -m venv .venv` then `.venv\Scripts\activate` and `pip install -r requirements.txt` (see `README.md`).
  - Run: `python main.py` (uses simulator classes in `dev/devices/*` by default). Example usage in `main.py` shows constructing `MyMicroscope` with `MySimCamera` and `MySimSpectrometer`.
  - Packaging: create a standalone executable with PyInstaller using the included spec: `pyinstaller microview.spec`. The spec includes `dev/images`, `dev/themes`, and device DLLs under `dev/devices/*/dlls` — update `datas` in `microview.spec` if you add assets.
  - Git LFS: repository uses Git LFS for large assets. If you clone, run `git lfs install` and `git lfs pull` if files seem missing.

- **Project conventions & patterns (concrete)**:
  - Device naming: device classes follow `MyCamera`, `MySpectrometer`, `MyShutter`, `MyStage`, `MyRotationMount`. Simulators use `MySim*` and live alongside real drivers.
  - Device registration: `MyMicroscope(name, device1, device2, ...)` — devices are passed positionally and stored in `microscope.devices` list.
  - UI wiring: `dev/application.py` instantiates frames (e.g. `CameraFrame`) using helper constructors in `dev/widgets/*`. When adding UI, follow existing frame patterns (constructor → grid/place → public `on_closing` cleanup).
  - File paths / backups: `FileSystem` builds backup paths using `root\user\YYYY-MM-DD\Experiment_N`. Use `FileSystem` methods (`get_spectrometer_directory`, `get_calibration_directory`) when saving data.
  - Error/debugging: the codebase commonly uses a `debugp` helper (`dev/debugHelp.py`) and often catches exceptions broadly around hardware integration. Prefer adding targeted exception handling when modifying hardware code.

- **When you change resources**:
  - If you add images, themes, or DLLs, update `datas` in `microview.spec` so PyInstaller bundles them. Example datas entries: `('dev/images', 'dev/images')`.
  - If you add a new device DLL under `dev/devices/<device>/dlls`, add that path to `datas` too.

- **Hidden imports / packaging notes**:
  - `microview.spec` already lists `hiddenimports=['clr.style_builder', 'clr', 'colorama', 'clr.style']`. When adding new runtime-only imports (dynamically loaded modules), add them to `hiddenimports` or create a runtime hook.
  - Console vs windowed build: spec sets `console=False` (GUI). For debugging builds you may temporarily change to `console=True` to see stdout/stderr.

- **Testing & debugging tips specific to this repo**:
  - Use simulator classes (`dev/devices/*/sim_*`) to develop UI and logic without hardware.
  - To reproduce device connection flows, inspect `main.py` where example microscopes are constructed.
  - If packaging issues occur (missing files at runtime), check `build/microview/.../warn-microview.txt` and `build/microview/xref-microview.html` for hints.

- **Safe-edit guidance for AI**:
  - Do not change `main.py` entry signatures unless you update `microview.spec` and tests; many scripts and the spec assume `main.py` is the entrypoint.
  - When adding device classes, keep simulator variants alongside real drivers (`sim_*`), and keep device-specific DLLs in `dev/devices/<device>/dlls`.
  - Prefer adding small, focused changes and run the app locally (`python main.py`) before altering packaging.

- **Where to look for examples**:
  - Device simulators: `dev/devices/camera/sim_camera.py` and `dev/devices/sim_spectrometer.py` show how to implement device APIs used by GUI.
  - GUI patterns: `dev/widgets/camera_frame.py` and `dev/widgets/spectrometer_frame.py` show frame lifecycle and cleanup (`on_closing`).
  - File naming and export: `dev/file_system.py` contains the backup and filename conventions; reference it when adding export features.


