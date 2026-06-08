# Kymera GUI Handoff

This document summarizes the Kymera 328i + Newton CCD GUI work already implemented in MicroView.

The goal is to help a later hardware-integration pass reuse the current GUI and simulator work instead of rediscovering the ownership model from scratch.

## Scope of what is already implemented

The work completed so far is GUI-first and simulator-first.

What is already in place:

- Kymera appears in the application as a spectrometer-backed device for the GM and Raman microscopes.
- The simulator path is wired and usable through `MySimKymera328i`.
- The shared spectrometer frame now supports a Kymera-specific Raman spectrum mode and a Kymera-specific image mode.
- The right-side spectrometer UI includes read-mode buttons, a mode toggle between spectrum and image view, and a Kymera-specific control strip.
- The device cogwheel opens a dedicated acquisition/settings popup with pages for `FVB`, `Multi-track`, `Image`, and `Temperature`.
- The settings popup supports `Single` and `Kinetic` acquisition modes only.
- The temperature page includes current temperature refresh, target temperature, cooler enable, and cooler-on-startup preference.
- The multi-track page opens a second popup for configuring tracks and horizontal range/binning.
- The Kymera device scaffold exposes SDK-backed option discovery helpers for several dropdown-like settings.

What is not finished yet:

- Real acquisition from the actual Newton CCD is not implemented.
- Real detector frames are not being retrieved from the camera.
- The simulator still supplies the live data used by the GUI.
- The actual correctness of SDK-backed settings application has not been validated in the lab.

## Main design decisions

### 1. Kymera stays a `MySpectrometer`

File:

- `dev/devices/spectrograph/kymera_328i.py`

`MyKymera328i` intentionally subclasses `MySpectrometer` so the rest of MicroView can discover it through the existing spectrometer plumbing.

That means the existing application wiring, setup panel, and spectrometer frame continue to work without introducing a separate device class path.

### 2. Kymera-specific UI is capability-based, not microscope-name-based

Primary file:

- `dev/widgets/spectrometer_frame.py`

The shared spectrometer frame branches on capabilities such as:

- `supports_image_view`
- `format_chart_data`
- `get_axis_labels`

That was done to avoid breaking the existing Ocean Optics VIS/NIR spectrometers used elsewhere in the app.

### 3. Settings state lives on the device, not only in popup widgets

Primary file:

- `dev/devices/spectrograph/kymera_328i.py`

The cogwheel popup reads from and writes to device-owned state such as:

- selected settings page
- selected acquisition mode
- selected read mode
- selected SDK option keys
- temperature settings
- multi-track settings

This is important for later hardware work because Claude should continue extending the device model rather than pushing more persistent logic into `setup_frame.py`.

## File map

### `main.py`

Current role:

- Wires `MySimKymera328i("Kymera 328i", "KY328I-XXXX", ...)` into the GM and Raman microscope device lists.
- Leaves the LM spectrometers unchanged.
- Uses the same serial string for the related rotation-mount associations in the simulator path.

Why it matters:

- This is the top-level place that currently decides where the simulator appears.
- A future hardware pass can swap the simulator entry for `MyKymera328i(...)` once the real device path is ready.

### `dev/devices/spectrograph/kymera_328i.py`

Current role:

- Project-facing Kymera/Newton device scaffold.
- Source of truth for Kymera UI state.
- Source of truth for simulator-compatible Raman formatting and pseudo-image behavior.
- Source of truth for settings popup option discovery and setting application.

Key things implemented here:

- `supports_image_view = True`
- `detector_name = "Newton CCD"`
- Raman axis conversion helpers
- pseudo-detector image generation
- acquisition mode state
- settings-page state
- SDK-backed option discovery for camera settings
- multi-track state and helpers
- temperature state and cooler-on-startup state
- `apply_camera_configuration()`

Important methods to inspect first in a future hardware pass:

- `connect()`
- `post_connect_update()`
- `refresh_sdk_capabilities()`
- `apply_camera_configuration()`
- `set_read_mode()`
- `build_detector_image()`
- `format_chart_data()`

### `dev/devices/spectrograph/sim_kymera_328i.py`

Current role:

- Simulator used during all GUI work so far.

What it does:

- Generates Raman-like 1D spectra.
- Pushes spectra into the standard `chart_queue` and `save_queue` flows.
- Provides a simulated detector temperature.

Why it matters:

- The GUI is currently proven against this simulator, not the real camera.
- A hardware pass should preserve its queue contract so the rest of the GUI keeps working.

### `dev/widgets/spectrometer_frame.py`

Current role:

- Shared spectrometer display used by both Ocean Optics and Kymera.
- Main owner of the right-side live plot UI.

Kymera-specific behavior implemented here:

- Raman shift axis for Kymera line plots.
- intensity-count y-axis for Kymera.
- spectrum/image toggle through the existing view button.
- right-sidebar read-mode icons.
- Kymera control strip under the plot.
- image-mode auxiliary plots:
  - top detector-count distribution plot
  - left row-profile plot
  - main detector image
  - bottom 1D spectrum plot

Key methods worth reading:

- `connect()`
- `supports_image_view()`
- `ensure_read_mode_sidebar()`
- `ensure_device_controls_placeholder()`
- `refresh_kymera_controls()`
- `set_kymera_read_mode()`
- `ensure_figure_layout()`
- `render_plot()`
- `toggle_split_screen()`

Important implementation notes:

- The read-mode hover tooltips are attached through a `CTkFrame` wrapper and canvas event bindings.
- Tk grid `weight` values must be integers.
- The image layout is a custom Matplotlib gridspec, not a stock toolbar layout.

### `dev/widgets/setup_frame.py`

Current role:

- Left-side device list and cogwheel popup owner.

Kymera-specific behavior implemented here:

- Kymera rows use a cogwheel instead of the generic integration-time widgets.
- `open_spectrograph_settings()` builds the acquisition/settings popup.
- The multi-track setup popup is nested inside this method.

This file owns the popup layout, but not the persistent settings state.

## Current GUI behavior in detail

### Device visibility and microscope placement

Current state:

- GM microscope contains the Kymera simulator.
- Raman microscope contains the Kymera simulator.
- LM microscope keeps the original VIS/NIR spectrometers unchanged.

This separation was requested explicitly and should be preserved unless the user asks otherwise.

### Spectrum mode

For the Kymera path, the shared spectrum plot now uses:

- x-axis: Raman shift `[cm^-1]`
- y-axis: Intensity `[counts]`

This is driven by device methods rather than hardcoded plot logic.

Relevant methods:

- `MyKymera328i.format_chart_data()`
- `MyKymera328i.get_axis_labels()`

### Image mode

Image mode is toggled using the existing view button in the spectrometer frame.

Current image mode contains:

- top counts-distribution plot
- left vertical row-profile plot
- central pseudo-CCD image
- bottom 1D Raman spectrum

Notes about interpretation:

- The top strip is a detector-count distribution view. It is not an interactive black/white-level control yet.
- The left strip is a vertical profile across CCD rows. It helps visualize vertical centering and stripe width.

### Read mode buttons

Supported read modes exposed in the GUI:

- `FVB`
- `Image`
- `Multi-track`

These are shown as small right-sidebar icons in the live spectrometer frame.

The settings popup does not expose a readout-mode dropdown. Instead, the top page row acts as the readout-mode selector.

### Control strip below the live plot

The Kymera-specific control strip currently includes UI for:

- wavelength band / center selection
- exposure and cycle time display
- slit
- shutter
- grating
- focus mirror
- side input iris

These controls were added to match the requested Solis-inspired layout, but they are not yet lab-validated against the real device.

## Acquisition/settings popup

Primary owner:

- `QuickSetupFrame.open_spectrograph_settings()` in `dev/widgets/setup_frame.py`

### Page row

Implemented pages:

- `FVB`
- `Multi-track`
- `Image`
- `Temperature`

Pages that were intentionally excluded:

- spooling
- auto save
- crop mode
- other Solis pages not requested

### Acquisition mode

Only these modes are exposed:

- `Single`
- `Kinetic`

Modes intentionally excluded from the GUI:

- accumulate
- fast kinetics
- run till abort
- other SDK modes

The popup changes the visible fields when switching between `Single` and `Kinetic`.

### Triggering

Triggering is intentionally not exposed in the popup because the user requested internal triggering only.

### Readout mode dropdown

This is intentionally not present.

The page row replaces the old readout-mode dropdown.

### SDK-backed dropdowns

The device class now attempts to fetch these dynamically from the SDK wrapper when connected:

- vertical shift speed
- vertical clock amplitude
- readout rates / HSS choices
- preamp gains
- detector size
- temperature range

Relevant SDK wrapper methods referenced from the vendored SDK:

- `GetNumberVSSpeeds()`
- `GetVSSpeed()`
- `GetNumberVSAmplitudes()`
- `GetVSAmplitudeString()`
- `GetNumberADChannels()`
- `GetBitDepth()`
- `GetNumberHSSpeeds()`
- `GetHSSpeed()`
- `GetNumberPreAmpGains()`
- `GetPreAmpGain()`
- `GetDetector()`
- `GetTemperatureRange()`
- `IsCoolerOn()`
- `GetBaselineClamp()`

If those calls are unavailable or fail, the device falls back to conservative default option lists so the GUI still renders.

## Multi-track popup

Current owner:

- nested helper inside `open_spectrograph_settings()`

What is implemented:

- track count
- track height
- track offset
- generated list of track rows
- editable start/end rows table
- horizontal binning
- horizontal start/end range
- flip-horizontal preference

What was intentionally excluded:

- standard/custom choice
- grayed-out Solis controls
- unrelated disabled controls

Important note:

The popup currently stores and applies a simplified multi-track model. It uses `SetMultiTrack`, `SetMultiTrackHBin`, and `SetMultiTrackHRange` in the current device apply path.

The editable table is currently useful for GUI state and later refinement, but a real hardware pass should verify whether the Newton workflow should stay on `SetMultiTrack(...)` or move to `SetRandomTracks(...)` for arbitrary row pairs.

## Temperature page

Current features:

- current temperature display
- refresh button
- target temperature entry
- cooler enabled switch
- cooler on at program startup switch

State ownership:

- `target_temperature_c`
- `cooler_enabled`
- `cooler_startup_enabled`

Startup behavior:

- `post_connect_update()` currently copies `cooler_startup_enabled` into `cooler_enabled` before applying camera configuration.

That means the startup checkbox is the persisted preference for automatic cooler state at connect time.

## SDK integration status

Current status:

- SDK wrappers are vendored locally and imported through `andor_setup.py`.
- The device initializes both the camera and the spectrograph wrapper.
- Several settings are already being queried dynamically from the camera wrapper.
- Several settings are already being pushed back through `apply_camera_configuration()`.

However, this is still not a finished hardware driver.

Areas that need real-device validation:

- whether the selected readout/acquisition modes are applied in the correct order
- whether `SetHSSpeed()` is being called with the right argument pattern for the Newton camera in practice
- whether multi-track should use `SetMultiTrack` or `SetRandomTracks`
- whether image-mode readout should configure the detector geometry differently
- whether the temperature page needs cooler startup persistence beyond runtime state
- whether additional timing calls should be used after every configuration change

## Known constraints and implementation notes

- The current work was validated with focused `py_compile` checks, not with the real Newton CCD in the lab.
- The simulator path is the only exercised runtime path so far.
- Tooltip support uses `CTkToolTip` and must attach to CustomTkinter widgets, not raw `Canvas` widgets.
- Tk grid weights must be integers or Tk throws `_tkinter.TclError`.
- The top image-mode counts view is not interactive yet.
- The popup intentionally excludes many Solis features the user did not want exposed.

## Suggested entry points for Claude

If Claude is going to implement the real device path next, the best reading order is:

1. `dev/devices/spectrograph/KYMERA_GUI_HANDOFF.md`
2. `dev/devices/spectrograph/README.md`
3. `dev/devices/spectrograph/kymera_328i.py`
4. `dev/devices/spectrograph/sim_kymera_328i.py`
5. `dev/widgets/spectrometer_frame.py`
6. `dev/widgets/setup_frame.py`
7. `main.py`

Suggested implementation order for hardware work:

1. Keep the current GUI intact and make the real device match the simulator contract.
2. Make `acquire_data()` produce real `(wavelengths, intensities)` queue outputs first.
3. Validate the mode-setting order and timing calls with the real camera.
4. Validate which multi-track API variant is actually correct for the Newton workflow.
5. Replace the pseudo-image path with real detector-frame retrieval once the 2D acquisition path is known.

## Quick summary

The GUI side is now substantially in place.

The next phase is mostly device-driver work, not new GUI invention.

The safest approach for Claude will be:

- preserve the current popup and spectrometer-frame interfaces
- preserve the simulator contract
- make the real `MyKymera328i` implementation conform to the same state and queue behavior
- validate SDK calls in the lab one feature at a time
