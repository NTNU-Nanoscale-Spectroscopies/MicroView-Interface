import json
import os
import shutil
import tempfile
import threading
import time

from dev.debugHelp import debugp
from dev.devices.spectrometer import MySpectrometer
import numpy as np

from .andor_setup import configure_path


_SETTINGS_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "MicroView"
)
_SETTINGS_PATH = os.path.join(_SETTINGS_DIR, "kymera_settings.json")

# Tolerance only used as a fallback when the SDK does not return a temperature state.
_TEMPERATURE_TOLERANCE_C = 0.25

# Andor SDK temperature status codes (mirrored locally to avoid an import cycle).
_DRV_TEMP_OFF = 20034
_DRV_TEMP_NOT_STABILIZED = 20035
_DRV_TEMP_STABILIZED = 20036
_DRV_TEMP_NOT_REACHED = 20037
_DRV_TEMP_DRIFT = 20040

_DEFAULT_EXCITATION_WAVELENGTH_NM = 785.0


class MyKymera328i(MySpectrometer):
    """Project for an Andor Kymera 328i spectrograph.

    The Kymera setup uses two Andor wrappers:
    - pyAndorSpectrograph controls the spectrograph optics.
    - pyAndorSDK2 controls the attached detector/camera.

    """

    def __init__(
        self,
        name,
        serial,
        enable=False,
        dark_correction=False,
        integration_time=100,
        device_index=0,
    ):
        super().__init__(name, serial, enable, dark_correction, integration_time)
        self.device_index = device_index
        self.camera = None
        self.spectrograph = None
        self._last_sdk_status = {}
        self._last_error = None
        self._last_spooled_sif_dir = None
        self._last_spooled_sif_files = []
        self._sdk_success_code = None
        self._spectrograph_success_code = None
        self._wavelength_axis_cache = None
        self._last_detector_frame = None
        self._acquisition_thread = None
        self._no_new_data_code = 20024
        self._drv_acquiring_code = 20072
        self._drv_idle_code = 20073
        self._last_temperature_status = None
        self._last_temperature_value = None
        # Raman-shift axes depend on the configured laser/excitation line.
        # This default matches the 785 nm Raman line used for the SOLIS comparisons.
        self.excitation_wavelength_nm = _DEFAULT_EXCITATION_WAVELENGTH_NM
        self.detector_rows = 256
        self.detector_width_pixels = 1600
        self.detector_height_pixels = self.detector_rows
        self.detector_name = "Newton CCD"
        self.supports_image_view = True
        self.mirror_spectral_axis_for_display = False
        self.control_panel_title = "Kymera controls"
        self._fallback_wavelength_display_range_nm = (0.0, 1600.0)
        self.cycle_time_offset_s = 0.00305
        # User-controlled kinetic cycle time (seconds). None means use
        # ``exposure + cycle_time_offset_s`` as before.
        self.cycle_time_seconds = None
        # Axis mode for the live plot. 'raman' or 'wavelength'.
        self.axis_mode = "raman"
        self.available_settings_pages = ["FVB", "Multi-track", "Image", "Temperature"]
        self.available_acquisition_modes = ["Single", "Kinetic"]
        self.acquisition_mode_codes = {"Single": 1, "Kinetic": 3}
        self.internal_trigger_mode_code = 0
        self.available_read_modes = ["FVB", "Image", "Multi-track"]
        self.read_mode_codes = {"FVB": 0, "Multi-track": 1, "Image": 4}
        self.selected_read_mode = "FVB"
        self.selected_settings_page = "FVB"
        self.selected_acquisition_mode = "Single"
        self.available_gratings = [
            {"index": 1, "lines_per_mm": 85, "blaze": "1350nm", "bandwidth_nm": 892.46, "default_center_nm": 620.00},
            {"index": 2, "lines_per_mm": 150, "blaze": "800nm", "bandwidth_nm": 503.17, "default_center_nm": 620.00},
            {"index": 3, "lines_per_mm": 600, "blaze": "750nm", "bandwidth_nm": 119.87, "default_center_nm": 620.00},
            {"index": 4, "lines_per_mm": 1200, "blaze": "500nm", "bandwidth_nm": 53.83, "default_center_nm": 620.00},
        ]
        self.selected_grating_index = 0
        self.center_wavelength_nm = self.available_gratings[0]["default_center_nm"]
        self.side_input_slit_um = 10.0
        self.focus_mirror_steps = 237
        self.side_input_iris_steps = 60
        self.shutter_external_enabled = False
        self.shutter_is_open = False
        self._acquisition_shutter_closed = True
        self.available_shutter_modes = [
            "AUTO",
            "OPEN during spectra series",
            "OPEN during series",
        ]
        self.shutter_mode_codes = {
            "AUTO": 0,
            # The SDK2 SetShutter wrapper only documents camera shutter modes
            # 0=auto, 1=open, 2=closed. The spectrograph shutter is still
            # opened/closed explicitly around acquisition below.
            "OPEN during spectra series": 1,
            "OPEN during series": 1,
        }
        self.selected_shutter_mode_index = 0
        self.vertical_shift_speed_options = []
        self.selected_vertical_shift_speed_key = None
        self.vertical_clock_amplitude_options = []
        self.selected_vertical_clock_amplitude_key = None
        self.readout_rate_options = []
        self.selected_readout_rate_key = None
        self.preamp_gain_options = []
        self.selected_preamp_gain_key = None
        self.output_amplifier_options = ["Electron Multiplying", "Conventional"]
        self.selected_output_amplifier = "Conventional"
        self.number_accumulations = 1
        self.kinetic_series_length = 60
        self.baseline_clamp_enabled = False
        self.temperature_range_c = (-80, 20)
        self.target_temperature_c = -80
        self.cooler_enabled = True
        self.cooler_startup_enabled = True
        self.multi_track_count = 1
        self.multi_track_height = 51
        self.multi_track_offset = 0
        self.multi_track_horizontal_binning = 1
        self.multi_track_horizontal_start = 6
        self.multi_track_horizontal_end = self.detector_width_pixels
        self.multi_track_flip_horizontal = False
        self.multi_track_tracks = [(60, 110)]

        # Slit / iris port indices used when pushing to the spectrograph SDK.
        # The Kymera ATSpectrograph uses INPUT_SIDE=1, INPUT_DIRECT=2,
        # OUTPUT_SIDE=3, OUTPUT_DIRECT=4 for slits, and Direct=0, Side=1 for irises.
        self._side_slit_port = 1
        self._side_iris_port = 1

        # Load persisted settings (overrides defaults set above).
        self._load_persistent_settings()

    def connect(self):
        """Initialize the vendored Andor SDK wrappers and hardware handles."""
        self.connected = False
        self.is_running = False
        self._last_error = None

        try:
            atmcd, error_codes, ATSpectrograph = self._load_sdk_classes()

            try:
                self.camera = atmcd()
            except Exception as error:
                self._last_error = error
                print(f"[Kymera] FATAL: failed to load atmcd64d.dll (Newton CCD): {error}")
                print("[Kymera] Verify the Andor SDK USB driver is installed and atmcd64d.dll is reachable.")
                self._shutdown_sdk()
                return False

            try:
                self.spectrograph = ATSpectrograph()
            except Exception as error:
                self._last_error = error
                print(f"[Kymera] FATAL: failed to load atspectrograph.dll (Kymera optics): {error}")
                print("[Kymera] Verify the Andor SDK USB driver is installed and atspectrograph.dll is reachable.")
                self._shutdown_sdk()
                return False

            self._sdk_success_code = int(error_codes.DRV_SUCCESS)
            self._spectrograph_success_code = int(self.spectrograph.ATSPECTROGRAPH_SUCCESS)
            self._no_new_data_code = int(getattr(error_codes, "DRV_NO_NEW_DATA", 20024))
            self._drv_acquiring_code = int(getattr(error_codes, "DRV_ACQUIRING", 20072))
            self._drv_idle_code = int(getattr(error_codes, "DRV_IDLE", 20073))

            camera_status = self.camera.Initialize("")
            spectrograph_status = self.spectrograph.Initialize("")
            self._last_sdk_status = {
                "camera_initialize": camera_status,
                "spectrograph_initialize": spectrograph_status,
            }

            camera_ok = camera_status == int(error_codes.DRV_SUCCESS)
            spectrograph_ok = (
                spectrograph_status == self.spectrograph.ATSPECTROGRAPH_SUCCESS
            )
            self.connected = camera_ok and spectrograph_ok

            if self.connected:
                print(
                    f"[Kymera] Connected. Newton Initialize={camera_status} (DRV_SUCCESS={self._sdk_success_code}), "
                    f"Kymera Initialize={spectrograph_status} (ATSPECTROGRAPH_SUCCESS={self._spectrograph_success_code})."
                )
                self.set_integration_time(self.integration_time)
                self.refresh_sdk_capabilities()
                self.refresh_gratings_from_sdk()
            else:
                if not camera_ok:
                    print(
                        f"[Kymera] Newton CCD Initialize() returned {camera_status} (expected {self._sdk_success_code}). "
                        f"Camera not detected — check USB cable, power, and Andor driver."
                    )
                if not spectrograph_ok:
                    print(
                        f"[Kymera] Kymera optics Initialize() returned {spectrograph_status} "
                        f"(expected {self._spectrograph_success_code}). Spectrograph not detected — check USB cable and Andor driver."
                    )
                self._shutdown_sdk()

        except Exception as error:
            self._last_error = error
            print(f"[Kymera] Unexpected error during initialization: {error}")
            self._shutdown_sdk()

        return self.connected

    def start(self):
        """Launch the live acquisition thread."""
        if not self.connected or self.is_running:
            return
        if self.camera is None:
            print("[Kymera] start(): camera handle missing, cannot acquire.")
            return

        print(
            f"[Kymera] Starting REAL acquisition thread (class={type(self).__name__}, "
            f"serial={self.serial}, read_mode={self.selected_read_mode})."
        )
        self.is_running = True
        self._acquisition_thread = threading.Thread(target=self.acquire_data, daemon=True)
        self._acquisition_thread.start()

    def acquire_data(self):
        """Drive the Andor camera with a single-scan live loop.

        Live preview reuses the same Single-Scan acquisition path that the
        saved-measurement code relies on. Run Till Abort was previously used
        here, but it returned corrupted FVB frames on grating 2 (and could
        do so on any read mode where the SDK's circular buffer fell out of
        sync with our read cadence). One acquisition path now serves every
        grating / read-mode combination.
        """
        if self.camera is None or not self.connected:
            self.is_running = False
            return

        # Block acquisition until the detector has reached the requested cooling target.
        if not self._wait_until_temperature_reached():
            print("[Kymera] Acquisition aborted: detector did not reach target temperature.")
            self.is_running = False
            return

        self._configure_live_acquisition()
        self._push_shutter_for_acquisition()

        try:
            self.index = 0
            consecutive_failures = 0
            max_consecutive_failures = 5

            while self.is_running:
                if self._acquire_live_frame():
                    consecutive_failures = 0
                    # Yield briefly so the SDK and GUI thread get breathing room.
                    time.sleep(max(0.02, min(self.get_cycle_time_seconds() * 0.05, 0.15)))
                    continue

                if not self.is_running:
                    break

                consecutive_failures += 1
                if consecutive_failures >= max_consecutive_failures:
                    debugp("Kymera", "Live acquisition aborting after repeated failures.")
                    break
                time.sleep(0.1)
        finally:
            self._safe_camera_call("AbortAcquisition")
            self._close_acquisition_controlled_shutter()

    def _configure_live_acquisition(self):
        """Apply the shared camera configuration used for live single-scan frames."""
        self.apply_camera_configuration(self.selected_read_mode)
        self._safe_camera_call("SetAcquisitionMode", self.acquisition_mode_codes["Single"])
        self._safe_camera_call("SetTriggerMode", self.internal_trigger_mode_code)
        self._safe_camera_call("SetFrameTransferMode", 0)

    def _acquire_live_frame(self):
        """Run one Prepare/Start/Wait/Read cycle and queue the result. Returns False on failure."""
        pixel_count = self._compute_acquisition_pixel_count()

        prepare_result = self._safe_camera_call("PrepareAcquisition")
        if prepare_result is not None and not self._camera_call_succeeded(prepare_result):
            debugp("Kymera", f"PrepareAcquisition failed: {prepare_result}")
            return False

        start_result = self._safe_camera_call("StartAcquisition")
        if not self._camera_call_succeeded(start_result):
            debugp("Kymera", f"StartAcquisition failed: {start_result}")
            return False

        wait_result = self._wait_for_live_frame()
        if not self.is_running:
            return True
        if not self._camera_call_succeeded(wait_result):
            debugp("Kymera", f"WaitForAcquisition failed: {wait_result}")
            self._safe_camera_call("AbortAcquisition")
            return False

        image_result = self._safe_camera_call("GetMostRecentImage", pixel_count)
        if not self._camera_call_succeeded(image_result):
            debugp("Kymera", f"GetMostRecentImage failed: {image_result}")
            return False

        wavelengths, intensities = self._format_acquisition(image_result[1], pixel_count)
        self._queue_acquisition_frame(wavelengths, intensities)
        return True

    def _wait_for_live_frame(self):
        """Block until the current Single acquisition completes, with a soft deadline."""
        deadline = time.monotonic() + max(self.get_cycle_time_seconds() * 4.0, 5.0)
        while self.is_running:
            wait_result = self._wait_for_acquisition_event()
            if wait_result != self._no_new_data_code:
                return wait_result
            if time.monotonic() >= deadline:
                return wait_result
        return self._no_new_data_code

    def _wait_for_acquisition_event(self):
        timeout_ms = max(250, int(self.get_cycle_time_seconds() * 3000))
        if self.camera is not None and hasattr(self.camera, "WaitForAcquisitionTimeOut"):
            return self._safe_camera_call("WaitForAcquisitionTimeOut", timeout_ms)
        return self._safe_camera_call("WaitForAcquisition")

    def _queue_acquisition_frame(self, wavelengths, intensities):
        if not self.chart_queue.empty():
            try:
                self.chart_queue.get_nowait()
            except Exception:
                pass
        try:
            self.chart_queue.put_nowait((wavelengths, intensities))
        except Exception:
            pass

        if self.acquire_save_data > 0 and getattr(self, "auto_save_enabled", True):
            self.index += 1
            if self.index >= self.acquire_save_data:
                self.index = 0
                self.save_queue.put((wavelengths, intensities))

    def get_signal_frame_count(self):
        if self.selected_acquisition_mode == "Kinetic":
            return max(int(self.kinetic_series_length), 1)
        return 1

    def capture_signal_series(self, progress_callback=None, spool_sif=False):
        """Acquire the configured single scan or kinetic series for saving."""
        if self.camera is None or not self.connected:
            raise RuntimeError("Camera is not connected")
        if not self.is_temperature_at_target():
            raise RuntimeError("Detector temperature is not stabilized")

        self.apply_camera_configuration()
        self._push_shutter_for_acquisition()

        frames = []
        target_frames = self.get_signal_frame_count()
        pixel_count = self._compute_acquisition_pixel_count()
        timeout_seconds = max(self.get_cycle_time_seconds() * max(target_frames, 1) * 6.0, 30.0)
        deadline = time.monotonic() + timeout_seconds
        next_image = None
        spool_enabled = False

        try:
            if spool_sif:
                spool_enabled = self._enable_signal_sif_spooling(target_frames)

            prepare_result = self._safe_camera_call("PrepareAcquisition")
            if prepare_result is not None and not self._camera_call_succeeded(prepare_result):
                raise RuntimeError(f"PrepareAcquisition failed ({prepare_result})")

            start_result = self._safe_camera_call("StartAcquisition")
            if not self._camera_call_succeeded(start_result):
                raise RuntimeError(f"StartAcquisition failed ({start_result})")

            while len(frames) < target_frames:
                wait_result = self._wait_for_recording_frame()
                if wait_result == self._no_new_data_code:
                    if time.monotonic() > deadline:
                        break
                    continue
                if not self._camera_call_succeeded(wait_result):
                    status_result = self._safe_camera_call("GetStatus")
                    if (
                        self._camera_call_succeeded(status_result)
                        and len(status_result) > 1
                        and status_result[1] == self._drv_idle_code
                    ):
                        self._append_latest_recording_frame(frames, pixel_count, target_frames, progress_callback)
                        break
                    if time.monotonic() > deadline:
                        break
                    continue

                next_image = self._append_available_recording_frames(
                    frames,
                    pixel_count,
                    target_frames,
                    next_image,
                    progress_callback,
                )

                if len(frames) >= target_frames:
                    break

                status_result = self._safe_camera_call("GetStatus")
                if (
                    self._camera_call_succeeded(status_result)
                    and len(status_result) > 1
                    and status_result[1] == self._drv_idle_code
                ):
                    self._append_latest_recording_frame(frames, pixel_count, target_frames, progress_callback)
                    break

                if time.monotonic() > deadline:
                    break

            if not frames:
                self._append_latest_recording_frame(frames, pixel_count, target_frames, progress_callback)

            return frames[:target_frames]
        finally:
            status_result = self._safe_camera_call("GetStatus")
            if (
                self._camera_call_succeeded(status_result)
                and len(status_result) > 1
                and status_result[1] == self._drv_acquiring_code
            ):
                self._safe_camera_call("AbortAcquisition")
            if spool_enabled:
                self._disable_signal_sif_spooling(target_frames)
            self._close_acquisition_controlled_shutter()

    def _enable_signal_sif_spooling(self, target_frames):
        if self.camera is None or not hasattr(self.camera, "SetSpool"):
            return False

        self.cleanup_last_spooled_sif_files()
        spool_dir = tempfile.mkdtemp(prefix="microview_kymera_sif_")
        spool_stem = os.path.join(spool_dir, "signal.sif")
        result = self._safe_camera_call("SetSpool", 1, 6, spool_stem, max(int(target_frames), 10))
        if self._camera_call_succeeded(result):
            self._last_spooled_sif_dir = spool_dir
            self._last_spooled_sif_files = []
            return True

        try:
            shutil.rmtree(spool_dir, ignore_errors=True)
        except Exception:
            pass
        return False

    def _disable_signal_sif_spooling(self, target_frames):
        if self.camera is not None and hasattr(self.camera, "SetSpool"):
            self._safe_camera_call("SetSpool", 0, 6, "", max(int(target_frames), 10))

        self._last_spooled_sif_files = self._collect_spooled_sif_files(target_frames)

    def _collect_spooled_sif_files(self, target_frames, timeout_seconds=2.0):
        spool_dir = self._last_spooled_sif_dir
        if not spool_dir or not os.path.isdir(spool_dir):
            return []

        deadline = time.monotonic() + max(float(timeout_seconds), 0.0)
        files = []
        while True:
            files = [
                os.path.join(spool_dir, name)
                for name in os.listdir(spool_dir)
                if os.path.isfile(os.path.join(spool_dir, name))
            ]
            files = sorted(files, key=lambda path: (os.path.getmtime(path), path))
            sif_files = [path for path in files if path.lower().endswith((".sif", ".sifx"))]
            if len(sif_files) >= int(target_frames) or time.monotonic() >= deadline:
                return sif_files or files
            time.sleep(0.05)

    def get_last_spooled_sif_files(self):
        return list(self._last_spooled_sif_files)

    def cleanup_last_spooled_sif_files(self):
        spool_dir = self._last_spooled_sif_dir
        self._last_spooled_sif_files = []
        self._last_spooled_sif_dir = None
        if spool_dir and os.path.isdir(spool_dir):
            shutil.rmtree(spool_dir, ignore_errors=True)

    def _wait_for_recording_frame(self):
        timeout_ms = max(250, int(self.get_cycle_time_seconds() * 3000))
        if self.camera is not None and hasattr(self.camera, "WaitForAcquisitionTimeOut"):
            return self._safe_camera_call("WaitForAcquisitionTimeOut", timeout_ms)
        return self._safe_camera_call("WaitForAcquisition")

    def _append_available_recording_frames(self, frames, pixel_count, target_frames, next_image, progress_callback=None):
        available_result = self._safe_camera_call("GetNumberAvailableImages")
        if not self._camera_call_succeeded(available_result) or len(available_result) < 3:
            return next_image

        first_image = int(available_result[1])
        last_image = int(available_result[2])
        if last_image < first_image:
            return next_image

        start_image = max(first_image, int(next_image)) if next_image is not None else first_image
        if start_image > last_image:
            return next_image

        remaining = max(target_frames - len(frames), 0)
        if remaining <= 0:
            return next_image

        end_image = min(last_image, start_image + remaining - 1)
        image_count = end_image - start_image + 1
        images_result = self._safe_camera_call("GetImages", start_image, end_image, image_count * pixel_count)
        if not self._camera_call_succeeded(images_result) or len(images_result) < 2:
            return next_image

        raw_images = np.asarray(images_result[1], dtype=np.float64).copy()
        try:
            raw_images = raw_images.reshape((image_count, pixel_count))
        except ValueError:
            raw_images = raw_images.reshape((1, -1))

        for raw_frame in raw_images:
            if len(frames) >= target_frames:
                break
            wavelengths, intensities = self._format_acquisition(raw_frame, pixel_count)
            frames.append((wavelengths.copy(), intensities.copy()))
            if progress_callback:
                progress_callback(len(frames), target_frames)

        valid_last = int(images_result[3]) if len(images_result) > 3 else end_image
        return valid_last + 1

    def _append_latest_recording_frame(self, frames, pixel_count, target_frames, progress_callback=None):
        if len(frames) >= target_frames:
            return

        image_result = self._safe_camera_call("GetMostRecentImage", pixel_count)
        if not self._camera_call_succeeded(image_result) or len(image_result) < 2:
            return

        wavelengths, intensities = self._format_acquisition(image_result[1], pixel_count)
        frames.append((wavelengths.copy(), intensities.copy()))
        if progress_callback:
            progress_callback(len(frames), target_frames)

    def save_last_signal_as_sif(self, path, comment="", calibrated=True):
        if self.camera is None:
            return False, None

        if comment and hasattr(self.camera, "SetSifComment"):
            self._safe_camera_call("SetSifComment", comment)

        if (
            calibrated
            and self.spectrograph is not None
            and hasattr(self.camera, "SaveAsCalibratedSif")
            and hasattr(self.spectrograph, "GetPixelCalibrationCoefficients")
        ):
            coefficient_result = self._safe_spectrograph_call(
                "GetPixelCalibrationCoefficients", self.device_index
            )
            if (
                self._spectrograph_call_succeeded(coefficient_result)
                and isinstance(coefficient_result, tuple)
                and len(coefficient_result) >= 5
            ):
                coefficients = [float(value) for value in coefficient_result[1:5]]
                # SDK2 uses data_type=3 for Raman Shift and unit=1 for cm-1.
                result = self._safe_camera_call(
                    "SaveAsCalibratedSif",
                    path,
                    3,
                    1,
                    coefficients,
                    float(self.excitation_wavelength_nm),
                )
                if self._camera_call_succeeded(result):
                    return True, result

        result = self._safe_camera_call("SaveAsSif", path)
        return self._camera_call_succeeded(result), result

    def stop(self):
        """Halt the acquisition loop, abort the camera, and drain pending queues."""
        was_running = self.is_running
        self.is_running = False

        if self.camera is not None and was_running:
            try:
                self.camera.CancelWait()
            except Exception:
                pass
            try:
                self.camera.AbortAcquisition()
            except Exception as error:
                debugp("Kymera", f"AbortAcquisition failed: {error}")
            self._close_acquisition_controlled_shutter()

        if self._acquisition_thread is not None:
            self._acquisition_thread.join(timeout=2.0)
            self._acquisition_thread = None

        while not self.chart_queue.empty():
            try:
                self.chart_queue.get_nowait()
            except Exception:
                break
        while not self.save_queue.empty():
            try:
                self.save_queue.get_nowait()
            except Exception:
                break

    def disconnect(self):
        """Shut down SDK handles if they were initialized."""
        if self.connected or self.camera is not None or self.spectrograph is not None:
            self.stop()
            self._shutdown_sdk()
            self.connected = False
            debugp("Kymera", f"{self.name} disconnected.")

    def post_connect_update(self):
        self.refresh_sdk_capabilities()
        self.refresh_gratings_from_sdk()
        # Honour the persisted "cooler at startup" preference if the user has set it,
        # otherwise default to the saved cooler_enabled (which itself defaults to True).
        if self.cooler_startup_enabled:
            self.cooler_enabled = True
        self.apply_spectrograph_configuration()
        self.apply_camera_configuration()
        self._push_shutter_to_hardware()

    def _compute_acquisition_pixel_count(self):
        width = self._compute_readout_width()
        if self.selected_read_mode == "Image":
            return width * max(int(self.detector_height_pixels), 1)
        if self.selected_read_mode == "Multi-track":
            return width * max(int(self.multi_track_count), 1)
        return width

    def _compute_readout_width(self):
        if self.selected_read_mode == "Multi-track":
            horizontal_start = max(int(self.multi_track_horizontal_start), 1)
            horizontal_end = min(int(self.multi_track_horizontal_end), int(self.detector_width_pixels))
            if horizontal_end < horizontal_start:
                horizontal_start, horizontal_end = horizontal_end, horizontal_start
            binning = max(int(self.multi_track_horizontal_binning), 1)
            return max(((horizontal_end - horizontal_start + 1) // binning), 1)
        return max(int(self.detector_width_pixels), 1)

    def _format_acquisition(self, raw_array, expected_size):
        width = self._compute_readout_width()
        array = np.asarray(raw_array, dtype=np.float64).ravel()

        if array.size == 0:
            self._last_detector_frame = None
            return self._get_wavelength_axis(width), np.zeros(width, dtype=np.float64)

        if self.selected_read_mode == "Image":
            try:
                frame = array.reshape((-1, width))
            except ValueError:
                frame = array.reshape((1, -1))
            self._last_detector_frame = frame
            intensities = frame.sum(axis=0)
        elif self.selected_read_mode == "Multi-track":
            tracks = max(int(self.multi_track_count), 1)
            try:
                stacked = array.reshape((tracks, -1))
            except ValueError:
                stacked = array.reshape((1, -1))
            self._last_detector_frame = stacked
            intensities = stacked.sum(axis=0)
        else:
            self._last_detector_frame = None
            intensities = array

        wavelengths = self._get_wavelength_axis(intensities.size)
        return wavelengths, intensities

    def _get_wavelength_axis(self, n_pixels):
        n_pixels = int(n_pixels)
        if (
            self._wavelength_axis_cache is not None
            and self._wavelength_axis_cache.size == n_pixels
        ):
            return self._wavelength_axis_cache

        wavelengths = None
        if self.spectrograph is not None:
            try:
                calibration_pixels = (
                    int(self.detector_width_pixels)
                    if self.selected_read_mode == "Multi-track"
                    else n_pixels
                )
                result = self.spectrograph.GetCalibration(self.device_index, calibration_pixels)
                if isinstance(result, tuple) and len(result) >= 2:
                    status, calibration = result[0], result[1]
                    success = (
                        self._spectrograph_success_code is None
                        or status == self._spectrograph_success_code
                    )
                    if success and calibration is not None and len(calibration) == calibration_pixels:
                        wavelengths = np.asarray(calibration, dtype=np.float64)
                        if self.selected_read_mode == "Multi-track":
                            start = max(int(self.multi_track_horizontal_start), 1) - 1
                            end = min(int(self.multi_track_horizontal_end), int(self.detector_width_pixels))
                            binning = max(int(self.multi_track_horizontal_binning), 1)
                            wavelengths = wavelengths[start:end:binning]
            except Exception as error:
                self._last_error = error
                debugp("Kymera", f"GetCalibration failed: {error}")

        if wavelengths is None:
            half_bandwidth = self._fallback_bandwidth_nm() / 2.0
            center = float(self.center_wavelength_nm)
            wavelengths = np.linspace(
                center - half_bandwidth, center + half_bandwidth, n_pixels, dtype=np.float64
            )

        self._wavelength_axis_cache = wavelengths
        return wavelengths

    def _invalidate_wavelength_cache(self):
        self._wavelength_axis_cache = None

    def _safe_spectrograph_call(self, method_name, *args):
        if self.spectrograph is None or not hasattr(self.spectrograph, method_name):
            return None
        try:
            result = getattr(self.spectrograph, method_name)(*args)
            status = result[0] if isinstance(result, tuple) else result
            self._last_sdk_status[f"spectrograph_{method_name}"] = status
            return result
        except Exception as error:
            self._last_error = error
            debugp("Kymera", f"spectrograph.{method_name} failed: {error}")
            return None

    def _spectrograph_call_succeeded(self, result):
        if result is None:
            return False
        status = result[0] if isinstance(result, tuple) else result
        if self._spectrograph_success_code is None:
            return True
        return status == self._spectrograph_success_code

    def apply_spectrograph_configuration(self):
        """Push detector geometry, grating, wavelength, slit, focus and iris to the spectrograph."""
        if self.spectrograph is None:
            return

        self._safe_spectrograph_call(
            "SetNumberPixels", self.device_index, int(self.detector_width_pixels)
        )

        pixel_size_result = self._safe_camera_call("GetPixelSize")
        if self._camera_call_succeeded(pixel_size_result):
            _, x_size, _ = pixel_size_result
            if float(x_size) > 0:
                self._safe_spectrograph_call(
                    "SetPixelWidth", self.device_index, float(x_size)
                )

        grating = self.available_gratings[self.selected_grating_index]
        self._safe_spectrograph_call(
            "SetGrating", self.device_index, int(grating["index"])
        )
        self._safe_spectrograph_call(
            "SetWavelength", self.device_index, float(self.center_wavelength_nm)
        )

        self._push_slit_to_hardware()
        self._push_focus_mirror_to_hardware("startup")
        self._safe_spectrograph_call(
            "SetIris", self.device_index, self._side_iris_port, int(self.side_input_iris_steps)
        )

        self._invalidate_wavelength_cache()

    def refresh_gratings_from_sdk(self):
        """Replace the hard-coded grating list with what the spectrograph reports."""
        if self.spectrograph is None:
            return

        count_result = self._safe_spectrograph_call("GetNumberGratings", self.device_index)
        if not self._spectrograph_call_succeeded(count_result):
            print("[Kymera] GetNumberGratings failed - keeping fallback grating list.")
            return

        number_of_gratings = int(count_result[1])
        if number_of_gratings <= 0:
            print("[Kymera] GetNumberGratings returned 0 - keeping fallback grating list.")
            return

        gratings = []
        for grating_index in range(1, number_of_gratings + 1):
            info = self._safe_spectrograph_call(
                "GetGratingInfo", self.device_index, grating_index, 64
            )
            if not self._spectrograph_call_succeeded(info):
                continue

            _, lines_per_mm, blaze, _home, _offset = info
            try:
                lines_per_mm = float(lines_per_mm)
            except Exception:
                lines_per_mm = 0.0

            wavelength_limits = self._get_grating_wavelength_limits(grating_index)
            bandwidth_nm = self._estimate_spectral_window_nm(lines_per_mm)
            blaze_label = self._normalize_grating_blaze_label(blaze)

            gratings.append({
                "index": grating_index,
                "lines_per_mm": lines_per_mm,
                "blaze": blaze_label,
                "bandwidth_nm": round(bandwidth_nm, 2),
                "default_center_nm": 620.0,
                "wavelength_limits_nm": wavelength_limits,
            })

        if not gratings:
            return

        self.available_gratings = gratings
        if self.selected_grating_index >= len(gratings):
            self.selected_grating_index = 0

        active_result = self._safe_spectrograph_call("GetGrating", self.device_index)
        if self._spectrograph_call_succeeded(active_result):
            zero_based = int(active_result[1]) - 1
            if 0 <= zero_based < len(gratings):
                self.selected_grating_index = zero_based
                self._invalidate_wavelength_cache()

        labels = [
            f"{int(g['lines_per_mm'])} l/mm @ {g['blaze']}"
            for g in self.available_gratings
        ]
        print(f"[Kymera] Gratings reported by spectrograph: {labels}")
        self._refresh_current_wavelength_from_sdk()

    @staticmethod
    def _normalize_grating_blaze_label(blaze):
        if blaze is None:
            return ""
        if hasattr(blaze, "value"):
            blaze = blaze.value
        if isinstance(blaze, bytes):
            try:
                blaze = blaze.decode("utf-8")
            except UnicodeDecodeError:
                blaze = blaze.decode("ascii", errors="replace")

        text = str(blaze).strip()
        if not text:
            return ""
        if text.lower().endswith("nm"):
            return text
        try:
            return f"{float(text):g}nm"
        except Exception:
            return text

    @staticmethod
    def _default_center_for_grating(lines_per_mm):
        """Pick a sensible default centre wavelength for a grating based on its groove density."""
        if lines_per_mm <= 0:
            return 600.0
        if lines_per_mm < 120:
            return 600.0
        if lines_per_mm < 250:
            return 700.0
        if lines_per_mm < 500:
            return 650.0
        return 620.0

    def _get_grating_wavelength_limits(self, grating_index):
        result = self._safe_spectrograph_call("GetWavelengthLimits", self.device_index, int(grating_index))
        if self._spectrograph_call_succeeded(result) and isinstance(result, tuple) and len(result) >= 3:
            lower = float(result[1])
            upper = float(result[2])
            if upper < lower:
                lower, upper = upper, lower
            print(f"[Kymera] GetWavelengthLimits(grating={grating_index}) -> ({lower:.2f}, {upper:.2f}) nm")
            return (lower, upper)
        status = result[0] if isinstance(result, tuple) else result
        print(
            f"[Kymera] GetWavelengthLimits(grating={grating_index}) failed (status={status}); "
            f"using fallback range."
        )
        return self._fallback_wavelength_display_range_nm

    @staticmethod
    def _estimate_spectral_window_nm(lines_per_mm):
        """Return the SOLIS-like CCD wavelength window for common Kymera gratings."""
        if lines_per_mm <= 0:
            return 200.0
        known_windows = {
            85: 892.46,
            150: 503.17,
            300: 251.59,
            600: 119.87,
            1200: 53.83,
        }
        nearest_lines, nearest_window = min(
            known_windows.items(),
            key=lambda item: abs(float(lines_per_mm) - item[0]),
        )
        if abs(float(lines_per_mm) - nearest_lines) <= max(2.0, nearest_lines * 0.03):
            return nearest_window
        return 75500.0 / float(lines_per_mm)

    def _refresh_current_wavelength_from_sdk(self):
        result = self._safe_spectrograph_call("GetWavelength", self.device_index)
        if self._spectrograph_call_succeeded(result) and isinstance(result, tuple) and len(result) > 1:
            try:
                self.center_wavelength_nm = self.clamp_center_wavelength(float(result[1]))
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Persistence (settings survive between sessions)
    # ------------------------------------------------------------------

    _PERSISTENT_FIELDS = (
        "selected_settings_page",
        "selected_acquisition_mode",
        "selected_read_mode",
        "selected_vertical_shift_speed_key",
        "selected_vertical_clock_amplitude_key",
        "selected_readout_rate_key",
        "selected_preamp_gain_key",
        "selected_output_amplifier",
        "selected_grating_index",
        "selected_shutter_mode_index",
        "shutter_external_enabled",
        "center_wavelength_nm",
        "side_input_slit_um",
        "focus_mirror_steps",
        "side_input_iris_steps",
        "number_accumulations",
        "kinetic_series_length",
        "baseline_clamp_enabled",
        "target_temperature_c",
        "cooler_enabled",
        "cooler_startup_enabled",
        "multi_track_count",
        "multi_track_height",
        "multi_track_offset",
        "multi_track_horizontal_binning",
        "multi_track_horizontal_start",
        "multi_track_horizontal_end",
        "multi_track_flip_horizontal",
        "multi_track_tracks",
        "integration_time",
        "excitation_wavelength_nm",
        "cycle_time_seconds",
        "axis_mode",
    )

    def _load_persistent_settings(self):
        try:
            if not os.path.isfile(_SETTINGS_PATH):
                return
            with open(_SETTINGS_PATH, "r") as f:
                data = json.load(f)
        except Exception as error:
            print(f"[Kymera] Failed to load persisted settings: {error}")
            return

        saved = data.get(self.serial) if isinstance(data, dict) else None
        if not isinstance(saved, dict):
            return

        for field in self._PERSISTENT_FIELDS:
            if field not in saved:
                continue
            try:
                setattr(self, field, saved[field])
            except Exception:
                continue
        self._normalize_excitation_wavelength_setting()

    def _normalize_excitation_wavelength_setting(self):
        try:
            excitation_wavelength = float(self.excitation_wavelength_nm)
        except Exception:
            excitation_wavelength = _DEFAULT_EXCITATION_WAVELENGTH_NM

        self.excitation_wavelength_nm = max(excitation_wavelength, 1.0)

    def _save_persistent_settings(self):
        try:
            os.makedirs(_SETTINGS_DIR, exist_ok=True)
            existing = {}
            if os.path.isfile(_SETTINGS_PATH):
                try:
                    with open(_SETTINGS_PATH, "r") as f:
                        existing = json.load(f) or {}
                except Exception:
                    existing = {}

            snapshot = {}
            for field in self._PERSISTENT_FIELDS:
                value = getattr(self, field, None)
                if isinstance(value, (list, tuple)):
                    value = [list(item) if isinstance(item, tuple) else item for item in value]
                snapshot[field] = value

            existing[self.serial] = snapshot
            with open(_SETTINGS_PATH, "w") as f:
                json.dump(existing, f, indent=2)
        except Exception as error:
            print(f"[Kymera] Failed to save settings: {error}")

    def _safe_camera_call(self, method_name, *args):
        if self.camera is None or not hasattr(self.camera, method_name):
            return None

        try:
            result = getattr(self.camera, method_name)(*args)
            self._last_sdk_status[method_name] = result[0] if isinstance(result, tuple) else result
            return result
        except Exception as error:
            self._last_error = error
            debugp("Kymera", f"{method_name} failed: {error}")
            return None

    def _camera_call_succeeded(self, result):
        if result is None:
            return False

        status = result[0] if isinstance(result, tuple) else result
        if self._sdk_success_code is None:
            return True
        return status == self._sdk_success_code

    def _ensure_option_selection(self, attribute_name, options):
        keys = [option["key"] for option in options]
        current_value = getattr(self, attribute_name)
        if current_value not in keys:
            setattr(self, attribute_name, keys[0] if keys else None)

    @staticmethod
    def _decode_sdk_string(value):
        """Convert a ctypes string buffer (or bytes) returned by the Andor SDK into a Python str."""
        if value is None:
            return ""
        if hasattr(value, "value"):
            value = value.value
        if isinstance(value, bytes):
            try:
                value = value.decode("utf-8")
            except UnicodeDecodeError:
                value = value.decode("ascii", errors="replace")
        return str(value).strip()

    def _build_fallback_vertical_shift_speed_options(self):
        return [{"key": "vs:0", "index": 0, "label": "9.68 us"}]

    def _build_fallback_vs_amplitude_options(self):
        return [{"key": "vsa:0", "index": 0, "label": "Normal"}]

    def _build_fallback_readout_rate_options(self):
        return [
            {
                "key": "hss:conv:0:0",
                "channel": 0,
                "amp_type": 1,
                "speed_index": 0,
                "bit_depth": 16,
                "label": "3.00 MHz at 16-bit",
            },
            {
                "key": "hss:em:0:0",
                "channel": 0,
                "amp_type": 0,
                "speed_index": 0,
                "bit_depth": 16,
                "label": "1.00 MHz at 16-bit",
            },
        ]

    def _build_fallback_preamp_gain_options(self):
        return [{"key": "preamp:0", "index": 0, "label": "1x"}]

    def _refresh_preamp_gain_options(self):
        preamp_gain_options = []
        preamp_count_result = self._safe_camera_call("GetNumberPreAmpGains")
        if self._camera_call_succeeded(preamp_count_result):
            for index in range(int(preamp_count_result[1])):
                gain_result = self._safe_camera_call("GetPreAmpGain", index)
                if self._camera_call_succeeded(gain_result):
                    preamp_gain_options.append(
                        {"key": f"preamp:{index}", "index": index, "label": f"{float(gain_result[1]):g}x"}
                    )
        if preamp_gain_options:
            self.preamp_gain_options = preamp_gain_options
        elif not self.preamp_gain_options:
            self.preamp_gain_options = self._build_fallback_preamp_gain_options()
        self._ensure_option_selection("selected_preamp_gain_key", self.preamp_gain_options)

    def refresh_sdk_capabilities(self):
        detector_result = self._safe_camera_call("GetDetector")
        if self._camera_call_succeeded(detector_result):
            _, width_pixels, height_pixels = detector_result
            if width_pixels > 0:
                self.detector_width_pixels = int(width_pixels)
                self.multi_track_horizontal_end = max(self.multi_track_horizontal_end, self.detector_width_pixels)
            if height_pixels > 0:
                self.detector_height_pixels = int(height_pixels)
                self.detector_rows = int(height_pixels)

        vertical_shift_options = []
        vertical_count_result = self._safe_camera_call("GetNumberVSSpeeds")
        if self._camera_call_succeeded(vertical_count_result):
            for index in range(int(vertical_count_result[1])):
                speed_result = self._safe_camera_call("GetVSSpeed", index)
                if self._camera_call_succeeded(speed_result):
                    vertical_shift_options.append(
                        {"key": f"vs:{index}", "index": index, "label": f"{float(speed_result[1]):.2f} us"}
                    )
        if vertical_shift_options:
            self.vertical_shift_speed_options = vertical_shift_options
        elif not self.vertical_shift_speed_options:
            self.vertical_shift_speed_options = self._build_fallback_vertical_shift_speed_options()
        self._ensure_option_selection("selected_vertical_shift_speed_key", self.vertical_shift_speed_options)

        vs_amplitude_options = []
        amplitude_count_result = self._safe_camera_call("GetNumberVSAmplitudes")
        if self._camera_call_succeeded(amplitude_count_result):
            for index in range(int(amplitude_count_result[1])):
                label_result = self._safe_camera_call("GetVSAmplitudeString", index)
                if self._camera_call_succeeded(label_result):
                    label_text = self._decode_sdk_string(label_result[1]) or f"Level {index}"
                    vs_amplitude_options.append({"key": f"vsa:{index}", "index": index, "label": label_text})
        if vs_amplitude_options:
            self.vertical_clock_amplitude_options = vs_amplitude_options
        elif not self.vertical_clock_amplitude_options:
            self.vertical_clock_amplitude_options = self._build_fallback_vs_amplitude_options()
        self._ensure_option_selection("selected_vertical_clock_amplitude_key", self.vertical_clock_amplitude_options)

        number_amp_result = self._safe_camera_call("GetNumberAmp")
        if self._camera_call_succeeded(number_amp_result) and int(number_amp_result[1]) <= 1:
            self.output_amplifier_options = ["Conventional"]
            self.selected_output_amplifier = "Conventional"
        else:
            self.output_amplifier_options = ["Electron Multiplying", "Conventional"]
            if self.selected_output_amplifier not in self.output_amplifier_options:
                self.selected_output_amplifier = "Conventional"

        readout_rate_options = []
        number_channels_result = self._safe_camera_call("GetNumberADChannels")
        channel_count = int(number_channels_result[1]) if self._camera_call_succeeded(number_channels_result) else 1
        amp_type_pairs = [(0, "em"), (1, "conv")]
        if self.output_amplifier_options == ["Conventional"]:
            amp_type_pairs = [(1, "conv")]

        for amp_type, amp_slug in amp_type_pairs:
            for channel in range(channel_count):
                bit_depth_result = self._safe_camera_call("GetBitDepth", channel)
                bit_depth = int(bit_depth_result[1]) if self._camera_call_succeeded(bit_depth_result) else 16
                speed_count_result = self._safe_camera_call("GetNumberHSSpeeds", channel, amp_type)
                if not self._camera_call_succeeded(speed_count_result):
                    continue

                for speed_index in range(int(speed_count_result[1])):
                    speed_result = self._safe_camera_call("GetHSSpeed", channel, amp_type, speed_index)
                    if not self._camera_call_succeeded(speed_result):
                        continue

                    readout_rate_options.append(
                        {
                            "key": f"hss:{amp_slug}:{channel}:{speed_index}",
                            "channel": channel,
                            "amp_type": amp_type,
                            "speed_index": speed_index,
                            "bit_depth": bit_depth,
                            "label": f"{float(speed_result[1]):.2f} MHz at {bit_depth}-bit",
                        }
                    )

        if readout_rate_options:
            self.readout_rate_options = readout_rate_options
        elif not self.readout_rate_options:
            self.readout_rate_options = self._build_fallback_readout_rate_options()
        self._ensure_option_selection("selected_readout_rate_key", self.get_readout_rate_options())

        self._refresh_preamp_gain_options()

        temperature_range_result = self._safe_camera_call("GetTemperatureRange")
        if self._camera_call_succeeded(temperature_range_result):
            _, minimum_temperature, maximum_temperature = temperature_range_result
            self.temperature_range_c = (int(minimum_temperature), int(maximum_temperature))
            self.target_temperature_c = min(max(self.target_temperature_c, self.temperature_range_c[0]), self.temperature_range_c[1])

        cooler_result = self._safe_camera_call("IsCoolerOn")
        if self._camera_call_succeeded(cooler_result):
            self.cooler_enabled = bool(cooler_result[1])

        baseline_result = self._safe_camera_call("GetBaselineClamp")
        if self._camera_call_succeeded(baseline_result):
            self.baseline_clamp_enabled = bool(baseline_result[1])

        self.multi_track_horizontal_end = max(self.multi_track_horizontal_start, min(self.multi_track_horizontal_end, self.detector_width_pixels))
        if not self.multi_track_tracks:
            self.generate_multi_track_tracks(self.multi_track_count, self.multi_track_height, self.multi_track_offset)

    def get_settings_pages(self):
        return list(self.available_settings_pages)

    def set_settings_page(self, page):
        if page in self.available_settings_pages:
            self.selected_settings_page = page
            self._save_persistent_settings()
        return self.selected_settings_page

    def get_acquisition_mode_options(self):
        return list(self.available_acquisition_modes)

    def set_acquisition_mode(self, mode):
        if mode in self.available_acquisition_modes:
            self.selected_acquisition_mode = mode
            self._save_persistent_settings()
        return self.selected_acquisition_mode

    def get_vertical_shift_speed_options(self):
        return list(self.vertical_shift_speed_options)

    def set_vertical_shift_speed(self, option_key):
        if option_key in {option["key"] for option in self.vertical_shift_speed_options}:
            self.selected_vertical_shift_speed_key = option_key
            self._save_persistent_settings()
        return self.selected_vertical_shift_speed_key

    def get_vertical_clock_amplitude_options(self):
        return list(self.vertical_clock_amplitude_options)

    def set_vertical_clock_amplitude(self, option_key):
        if option_key in {option["key"] for option in self.vertical_clock_amplitude_options}:
            self.selected_vertical_clock_amplitude_key = option_key
            self._save_persistent_settings()
        return self.selected_vertical_clock_amplitude_key

    def get_output_amplifier_options(self):
        return list(self.output_amplifier_options)

    def set_output_amplifier(self, amplifier_name):
        if amplifier_name in self.output_amplifier_options:
            self.selected_output_amplifier = amplifier_name
        filtered_options = self.get_readout_rate_options()
        self._ensure_option_selection("selected_readout_rate_key", filtered_options)
        self._save_persistent_settings()
        return self.selected_output_amplifier

    def get_readout_rate_options(self):
        amplifier_slug = "conv" if self.selected_output_amplifier == "Conventional" else "em"
        filtered_options = [
            option
            for option in self.readout_rate_options
            if option["key"].split(":")[1] == amplifier_slug
        ]
        return filtered_options or list(self.readout_rate_options)

    def set_readout_rate(self, option_key):
        if option_key in {option["key"] for option in self.readout_rate_options}:
            self.selected_readout_rate_key = option_key
            self._save_persistent_settings()
        return self.selected_readout_rate_key

    def get_preamp_gain_options(self):
        return list(self.preamp_gain_options)

    def set_preamp_gain(self, option_key):
        if option_key in {option["key"] for option in self.preamp_gain_options}:
            self.selected_preamp_gain_key = option_key
            self._save_persistent_settings()
        return self.selected_preamp_gain_key

    def set_baseline_clamp(self, enabled):
        self.baseline_clamp_enabled = bool(enabled)
        self._save_persistent_settings()
        return self.baseline_clamp_enabled

    def get_temperature_range(self):
        return self.temperature_range_c

    def set_target_temperature(self, target_temperature):
        minimum_temperature, maximum_temperature = self.temperature_range_c
        self.target_temperature_c = int(min(max(float(target_temperature), minimum_temperature), maximum_temperature))
        if self.connected and self.camera is not None:
            self._safe_camera_call("SetTemperature", self.target_temperature_c)
        self._save_persistent_settings()
        return self.target_temperature_c

    def set_cooler_enabled(self, enabled):
        self.cooler_enabled = bool(enabled)
        if self.connected and self.camera is not None:
            self._safe_camera_call("CoolerON" if self.cooler_enabled else "CoolerOFF")
        self._save_persistent_settings()
        return self.cooler_enabled

    def set_cooler_startup_enabled(self, enabled):
        self.cooler_startup_enabled = bool(enabled)
        self._save_persistent_settings()
        return self.cooler_startup_enabled

    def _wait_until_temperature_reached(self, timeout_seconds=600.0, poll_interval_s=2.0):
        """Block while the detector cools to the requested target.

        Returns True when the target is reached (or when no cooler is engaged), False if
        ``self.is_running`` is cleared before the target is met or the timeout elapses.
        """
        if not self.cooler_enabled:
            # User has explicitly disabled the cooler; respect that and proceed.
            return True

        deadline = time.monotonic() + max(float(timeout_seconds), 0.0)
        last_announced = None
        while self.is_running:
            if self.is_temperature_at_target():
                state, current = self.get_temperature_state()
                print(
                    f"[Kymera] Detector at target ({current} C, state={state}). "
                    f"Starting acquisition."
                )
                return True

            state, current = self.get_temperature_state()
            if current is not None and current != last_announced:
                last_announced = current
                print(
                    f"[Kymera] Waiting for cooler... current={current} C, "
                    f"target={self.target_temperature_c} C (state={state})"
                )

            if time.monotonic() > deadline:
                print(
                    f"[Kymera] Cooler timeout after {timeout_seconds:.0f}s; "
                    f"current={current} C, target={self.target_temperature_c} C."
                )
                return False

            time.sleep(poll_interval_s)

        return False

    def set_number_accumulations(self, number):
        self.number_accumulations = max(int(float(number)), 1)
        self._save_persistent_settings()
        return self.number_accumulations

    def set_kinetic_series_length(self, number):
        self.kinetic_series_length = max(int(float(number)), 1)
        self._save_persistent_settings()
        return self.kinetic_series_length

    def get_acquisition_timings(self):
        timings_result = self._safe_camera_call("GetAcquisitionTimings")
        if self._camera_call_succeeded(timings_result):
            return {
                "exposure": float(timings_result[1]),
                "accumulate": float(timings_result[2]),
                "kinetic": float(timings_result[3]),
            }

        exposure_seconds = self.get_exposure_seconds()
        accumulate_seconds = exposure_seconds + self.cycle_time_offset_s * 0.82
        kinetic_seconds = exposure_seconds + self.cycle_time_offset_s
        return {
            "exposure": exposure_seconds,
            "accumulate": accumulate_seconds,
            "kinetic": kinetic_seconds,
        }

    def generate_multi_track_tracks(self, track_count=None, height=None, offset=None):
        track_count = max(int(track_count if track_count is not None else self.multi_track_count), 1)
        height = max(int(height if height is not None else self.multi_track_height), 1)
        offset = max(int(offset if offset is not None else self.multi_track_offset), 0)

        self.multi_track_count = track_count
        self.multi_track_height = height
        self.multi_track_offset = offset

        total_height = track_count * height + max(track_count - 1, 0) * offset
        first_row = max(1, ((self.detector_rows - total_height) // 2) + 1)
        track_rows = []
        current_row = first_row
        for _ in range(track_count):
            start_row = current_row
            end_row = min(self.detector_rows, start_row + height - 1)
            track_rows.append((int(start_row), int(end_row)))
            current_row = end_row + 1 + offset

        self.multi_track_tracks = track_rows
        self._save_persistent_settings()
        return list(self.multi_track_tracks)

    def set_multi_track_tracks(self, track_rows):
        sanitized_tracks = []
        for start_row, end_row in track_rows:
            start_value = max(1, int(float(start_row)))
            end_value = min(self.detector_rows, int(float(end_row)))
            if end_value < start_value:
                start_value, end_value = end_value, start_value
            sanitized_tracks.append((start_value, end_value))

        if sanitized_tracks:
            self.multi_track_tracks = sanitized_tracks
            self.multi_track_count = len(sanitized_tracks)
            self.multi_track_height = max(end - start + 1 for start, end in sanitized_tracks)
        self._save_persistent_settings()
        return list(self.multi_track_tracks)

    def get_multi_track_tracks(self):
        return list(self.multi_track_tracks)

    def set_multi_track_horizontal_range(self, horizontal_start, horizontal_end):
        horizontal_start = max(1, int(float(horizontal_start)))
        horizontal_end = min(self.detector_width_pixels, int(float(horizontal_end)))
        if horizontal_end < horizontal_start:
            horizontal_start, horizontal_end = horizontal_end, horizontal_start
        self.multi_track_horizontal_start = horizontal_start
        self.multi_track_horizontal_end = horizontal_end
        self._save_persistent_settings()
        return self.multi_track_horizontal_start, self.multi_track_horizontal_end

    def set_multi_track_horizontal_binning(self, horizontal_binning):
        self.multi_track_horizontal_binning = max(int(float(horizontal_binning)), 1)
        self._save_persistent_settings()
        return self.multi_track_horizontal_binning

    def set_multi_track_flip_horizontal(self, enabled):
        self.multi_track_flip_horizontal = bool(enabled)
        self._save_persistent_settings()
        return self.multi_track_flip_horizontal

    def _apply_sdk_selection(self, options, selected_key, method_name, *value_keys):
        for option in options:
            if option["key"] != selected_key:
                continue
            values = [option[value_key] for value_key in value_keys]
            self._safe_camera_call(method_name, *values)
            break

    def apply_camera_configuration(self, page=None):
        if page in self.available_settings_pages:
            self.selected_settings_page = page

        selected_page = self.selected_settings_page
        if selected_page in self.read_mode_codes:
            self.selected_read_mode = selected_page

        if self.camera is None:
            return self.get_acquisition_timings()

        acquisition_code = self.acquisition_mode_codes.get(self.selected_acquisition_mode)
        if acquisition_code is not None:
            self._safe_camera_call("SetAcquisitionMode", acquisition_code)

        read_mode_code = self.read_mode_codes.get(self.selected_read_mode)
        if read_mode_code is not None:
            self._safe_camera_call("SetReadMode", read_mode_code)

        self.set_integration_time(self.integration_time)
        self._safe_camera_call("SetNumberAccumulations", self.number_accumulations)
        self._safe_camera_call("SetNumberKinetics", self.kinetic_series_length)
        if self.cycle_time_seconds is not None:
            self._safe_camera_call(
                "SetKineticCycleTime",
                max(float(self.cycle_time_seconds), self.get_exposure_seconds()),
            )
        self._safe_camera_call("SetBaselineClamp", int(self.baseline_clamp_enabled))

        self._apply_sdk_selection(self.vertical_shift_speed_options, self.selected_vertical_shift_speed_key, "SetVSSpeed", "index")
        self._apply_sdk_selection(self.vertical_clock_amplitude_options, self.selected_vertical_clock_amplitude_key, "SetVSAmplitude", "index")

        amplifier_code = 1 if self.selected_output_amplifier == "Conventional" else 0
        self._safe_camera_call("SetOutputAmplifier", amplifier_code)
        for option in self.readout_rate_options:
            if option["key"] != self.selected_readout_rate_key:
                continue
            self._safe_camera_call("SetADChannel", option["channel"])
            self._safe_camera_call("SetOutputAmplifier", option["amp_type"])
            self._safe_camera_call("SetHSSpeed", option["speed_index"])
            break

        # Pre-amp gain availability depends on the selected amplifier/readout
        # path, so apply it after output amplifier, AD channel and HSSpeed.
        self._refresh_preamp_gain_options()
        self._apply_sdk_selection(self.preamp_gain_options, self.selected_preamp_gain_key, "SetPreAmpGain", "index")

        minimum_temperature, maximum_temperature = self.temperature_range_c
        self.target_temperature_c = min(max(self.target_temperature_c, minimum_temperature), maximum_temperature)
        self._safe_camera_call("SetTemperature", self.target_temperature_c)
        self._safe_camera_call("CoolerON" if self.cooler_enabled else "CoolerOFF")

        if self.selected_read_mode == "FVB":
            self._safe_camera_call("SetFVBHBin", 1)
        elif self.selected_read_mode == "Image":
            self._safe_camera_call(
                "SetImage",
                1,
                1,
                1,
                self.detector_width_pixels,
                1,
                self.detector_rows,
            )
        elif self.selected_read_mode == "Multi-track":
            self._safe_camera_call("SetMultiTrack", self.multi_track_count, self.multi_track_height, self.multi_track_offset)
            self._safe_camera_call("SetMultiTrackHBin", self.multi_track_horizontal_binning)
            self._safe_camera_call("SetMultiTrackHRange", self.multi_track_horizontal_start, self.multi_track_horizontal_end)

        self.refresh_sdk_capabilities()
        return self.get_acquisition_timings()

    def set_integration_time(self, time_microseconds):
        """Store integration time and pass it to the Andor camera if connected."""
        self.integration_time = time_microseconds

        if self.connected and self.camera is not None:
            exposure_seconds = float(time_microseconds) / 1000000.0
            try:
                status = self.camera.SetExposureTime(exposure_seconds)
                self._last_sdk_status["set_exposure_time"] = status
            except Exception as error:
                self._last_error = error
                debugp("Kymera", f"Unable to set exposure time: {error}")
        self._save_persistent_settings()

    def get_temperature(self):
        """Return detector temperature when available."""
        status, temperature = self._read_temperature_status()
        self._last_temperature_status = status
        self._last_temperature_value = temperature
        return temperature if temperature is not None else float("nan")

    def _read_temperature_status(self):
        if self.camera is None:
            return None, None
        temperature_status_codes = {
            _DRV_TEMP_OFF,
            _DRV_TEMP_NOT_STABILIZED,
            _DRV_TEMP_STABILIZED,
            _DRV_TEMP_NOT_REACHED,
            _DRV_TEMP_DRIFT,
        }
        if hasattr(self.camera, "GetTemperatureF"):
            try:
                status, temperature = self.camera.GetTemperatureF()
                self._last_sdk_status["get_temperature_f"] = status
                if int(status) in temperature_status_codes:
                    return int(status), float(temperature)
            except Exception as error:
                self._last_error = error
        try:
            status, temperature = self.camera.GetTemperature()
            self._last_sdk_status["get_temperature"] = status
            return int(status), float(temperature)
        except Exception as error:
            self._last_error = error
            return None, None

    def is_temperature_at_target(self):
        """True when the detector reports that it is stabilized at the set point."""
        status, temperature = self._read_temperature_status()
        if status == _DRV_TEMP_STABILIZED:
            return True
        if status in (_DRV_TEMP_NOT_REACHED, _DRV_TEMP_NOT_STABILIZED, _DRV_TEMP_DRIFT):
            return False
        if status == _DRV_TEMP_OFF:
            return False
        if temperature is None:
            return True  # camera missing - don't block
        return abs(temperature - float(self.target_temperature_c)) <= _TEMPERATURE_TOLERANCE_C

    def get_temperature_state(self):
        """Return ('off' | 'warming' | 'reached' | 'unavailable', current_temperature) for the GUI."""
        if self.camera is None:
            return "unavailable", None

        status, temperature = self._read_temperature_status()
        if status is None:
            return "unavailable", None
        if status == _DRV_TEMP_OFF:
            return "off", temperature
        if status == _DRV_TEMP_STABILIZED:
            return "reached", temperature
        if status in (_DRV_TEMP_NOT_REACHED, _DRV_TEMP_NOT_STABILIZED, _DRV_TEMP_DRIFT):
            return "warming", temperature
        return "warming", temperature

    def get_read_mode_options(self):
        return list(self.available_read_modes)

    def set_read_mode(self, mode):
        if mode in self.available_read_modes:
            was_running = self.is_running
            if was_running:
                self.stop()
            self.selected_read_mode = mode
            self.selected_settings_page = mode
            self.apply_camera_configuration(mode)
            self._save_persistent_settings()
            if was_running:
                self.start()
        return self.selected_read_mode

    def get_active_grating(self):
        return self.available_gratings[self.selected_grating_index]

    def cycle_grating(self):
        was_running = bool(self.is_running)
        if was_running:
            self.stop()

        try:
            self.selected_grating_index = (self.selected_grating_index + 1) % len(self.available_gratings)
            grating = self.get_active_grating()
            if self.connected and self.spectrograph is not None:
                self._safe_spectrograph_call(
                    "SetGrating", self.device_index, int(grating["index"])
                )
                self._invalidate_wavelength_cache()
                self.center_wavelength_nm = self.clamp_center_wavelength(self.center_wavelength_nm)
                self._safe_spectrograph_call(
                    "SetWavelength", self.device_index, float(self.center_wavelength_nm)
                )
                self._invalidate_wavelength_cache()
            else:
                self._invalidate_wavelength_cache()
                self.center_wavelength_nm = self.clamp_center_wavelength(self.center_wavelength_nm)
            self._save_persistent_settings()
            return grating
        finally:
            if was_running and self.connected:
                self.start()

    def get_bandwidth_nm(self):
        if self.connected and self.spectrograph is not None:
            wavelengths = self._get_wavelength_axis(self._compute_readout_width())
            if wavelengths is not None and wavelengths.size > 1:
                finite = wavelengths[np.isfinite(wavelengths)]
                if finite.size > 1:
                    return float(np.nanmax(finite) - np.nanmin(finite))
        return self._fallback_bandwidth_nm()

    def _fallback_bandwidth_nm(self):
        return float(self.get_active_grating()["bandwidth_nm"])

    def get_valid_center_bounds(self):
        lower_bound, upper_bound = self.get_active_grating().get(
            "wavelength_limits_nm",
            self.wavelength_display_range_nm,
        )
        half_bandwidth = self.get_bandwidth_nm() / 2.0
        min_center = lower_bound + half_bandwidth
        max_center = upper_bound - half_bandwidth
        if max_center < min_center:
            midpoint = (lower_bound + upper_bound) / 2.0
            return midpoint, midpoint
        return min_center, max_center

    def clamp_center_wavelength(self, wavelength_nm):
        min_center, max_center = self.get_valid_center_bounds()
        return min(max(float(wavelength_nm), min_center), max_center)

    def set_center_wavelength(self, wavelength_nm):
        self.center_wavelength_nm = self.clamp_center_wavelength(wavelength_nm)
        if self.connected and self.spectrograph is not None:
            self._safe_spectrograph_call(
                "SetWavelength", self.device_index, float(self.center_wavelength_nm)
            )
            self._invalidate_wavelength_cache()
        self._save_persistent_settings()
        return self.center_wavelength_nm

    def set_wavelength_marker(self, marker, wavelength_nm):
        half_bandwidth = self.get_bandwidth_nm() / 2.0

        if marker == "minimum":
            return self.set_center_wavelength(float(wavelength_nm) + half_bandwidth)
        if marker == "maximum":
            return self.set_center_wavelength(float(wavelength_nm) - half_bandwidth)

        return self.set_center_wavelength(wavelength_nm)

    def get_wavelength_window(self):
        center = self.clamp_center_wavelength(self.center_wavelength_nm)
        if self.connected and self.spectrograph is not None:
            wavelengths = self._get_wavelength_axis(self._compute_readout_width())
            if wavelengths is not None and wavelengths.size > 1:
                finite = wavelengths[np.isfinite(wavelengths)]
                if finite.size > 1:
                    return float(np.nanmin(finite)), center, float(np.nanmax(finite))

        half_bandwidth = self.get_bandwidth_nm() / 2.0
        return center - half_bandwidth, center, center + half_bandwidth

    def set_exposure_seconds(self, exposure_seconds):
        exposure_seconds = max(float(exposure_seconds), 0.00001)
        self.set_integration_time(exposure_seconds * 1000000.0)
        return self.get_exposure_seconds()

    def get_exposure_seconds(self):
        return float(self.integration_time) / 1000000.0

    def get_cycle_time_seconds(self):
        """Return the user-set kinetic cycle time, or exposure + offset when unset."""
        if self.cycle_time_seconds is not None:
            return max(float(self.cycle_time_seconds), self.get_exposure_seconds())
        return self.get_exposure_seconds() + self.cycle_time_offset_s

    def set_cycle_time_seconds(self, seconds):
        """User-controlled cycle time. Pushes SetKineticCycleTime to the camera when connected."""
        value = max(float(seconds), self.get_exposure_seconds())
        self.cycle_time_seconds = value
        if self.connected and self.camera is not None:
            result = self._safe_camera_call("SetKineticCycleTime", float(value))
            status = result[0] if isinstance(result, tuple) else result
            ok = self._camera_call_succeeded(result)
            print(
                f"[Kymera] SetKineticCycleTime({value:.5f} s) -> status={status} "
                f"({'OK' if ok else 'FAIL'})"
            )
        self._save_persistent_settings()
        return self.cycle_time_seconds

    def set_side_input_slit(self, slit_um):
        self.side_input_slit_um = max(float(slit_um), 0.0)
        if self.connected and self.spectrograph is not None:
            self._push_slit_to_hardware()
        self._save_persistent_settings()
        return self.side_input_slit_um

    def _push_slit_to_hardware(self):
        """Push the current slit width to whichever input slit the device exposes."""
        requested_width = float(self.side_input_slit_um)
        port = self._resolve_input_slit_port()
        result = self._set_slit_width_on_port(port, requested_width)
        if not self._spectrograph_call_succeeded(result):
            alternate_port = 2 if port == 1 else 1
            alternate_result = self._set_slit_width_on_port(alternate_port, requested_width)
            if self._spectrograph_call_succeeded(alternate_result):
                port = alternate_port
                self._side_slit_port = alternate_port
                result = alternate_result

        status = result[0] if isinstance(result, tuple) else result
        ok = self._spectrograph_call_succeeded(result)
        readback = self._read_slit_width(port)
        readback_text = f", readback={readback:.2f} um" if readback is not None else ""
        print(
            f"[Kymera] SetSlitWidth(port={port}, width={requested_width:.2f} um{readback_text}) "
            f"-> status={status} ({'OK' if ok else 'FAIL'})"
        )

    def _set_slit_width_on_port(self, port, width_um):
        return self._safe_spectrograph_call(
            "SetSlitWidth", self.device_index, port, float(width_um)
        )

    def _read_slit_width(self, port):
        result = self._safe_spectrograph_call("GetSlitWidth", self.device_index, port)
        if self._spectrograph_call_succeeded(result) and isinstance(result, tuple) and len(result) > 1:
            try:
                return float(result[1])
            except Exception:
                return None
        return None

    def _resolve_input_slit_port(self):
        """Return the slit port (INPUT_SIDE=1 or INPUT_DIRECT=2) that the spectrograph reports as present."""
        for port in (self._side_slit_port, 2 if self._side_slit_port == 1 else 1):
            result = self._safe_spectrograph_call("IsSlitPresent", self.device_index, port)
            if self._spectrograph_call_succeeded(result) and isinstance(result, tuple) and result[1]:
                self._side_slit_port = port
                return port
        return self._side_slit_port

    def toggle_shutter_state(self):
        # Manual open/close is independent from acquisition-controlled EXT mode.
        self.shutter_external_enabled = False
        self.shutter_is_open = not self.shutter_is_open
        self._push_shutter_to_hardware()
        self._save_persistent_settings()
        return self.shutter_is_open

    def toggle_shutter_external(self):
        self.shutter_external_enabled = not self.shutter_external_enabled
        if self.shutter_external_enabled:
            # EXT means the camera controls the shutter during acquisitions; keep it
            # closed while idle.
            self.shutter_is_open = False
        self._push_shutter_to_hardware()
        self._save_persistent_settings()
        return self.shutter_external_enabled

    def cycle_shutter_mode(self):
        self.selected_shutter_mode_index = (self.selected_shutter_mode_index + 1) % len(self.available_shutter_modes)
        self._push_shutter_to_hardware()
        self._save_persistent_settings()
        return self.get_shutter_mode()

    def get_shutter_mode(self):
        return self.available_shutter_modes[self.selected_shutter_mode_index]

    def _selected_acquisition_shutter_mode(self):
        return self.shutter_mode_codes.get(self.get_shutter_mode(), 0)

    def _set_spectrograph_shutter_mode(self, mode, reason):
        """Drive a Kymera/Shamrock shutter over the spectrograph USB interface."""
        if not self.connected or self.spectrograph is None:
            return None

        present_result = self._safe_spectrograph_call("IsShutterPresent", self.device_index)
        if (
            self._spectrograph_call_succeeded(present_result)
            and isinstance(present_result, tuple)
            and len(present_result) > 1
            and not present_result[1]
        ):
            return None

        result = self._safe_spectrograph_call("SetShutter", self.device_index, int(mode))
        status = result[0] if isinstance(result, tuple) else result
        ok = self._spectrograph_call_succeeded(result)
        print(
            f"[Kymera] Spectrograph SetShutter({reason}, mode={mode}) "
            f"-> status={status} ({'OK' if ok else 'FAIL'})"
        )
        return result

    def _set_camera_shutter_mode(self, mode, reason):
        """Drive the Newton CCD's mechanical shutter via SetShutter."""
        if not self.connected or self.camera is None:
            return None

        result = self._safe_camera_call("SetShutter", 1, mode, 50, 50)
        status = result[0] if isinstance(result, tuple) else result
        ok = self._camera_call_succeeded(result)
        print(
            f"[Kymera] SetShutter({reason}, typ=1, mode={mode}, close=50ms, open=50ms) "
            f"-> status={status} ({'OK' if ok else 'FAIL'})"
        )
        return result

    def _push_shutter_to_hardware(self):
        """Apply the current idle shutter state."""
        if self.shutter_external_enabled:
            # Acquisition-controlled shutter modes should not leave the shutter open
            # between measurements.
            self._set_spectrograph_shutter_mode(0, "EXT idle closed")
            self.shutter_is_open = False
            self._acquisition_shutter_closed = True
            return self._set_camera_shutter_mode(2, "EXT idle closed")

        mode = 1 if self.shutter_is_open else 0
        reason = "manual open" if self.shutter_is_open else "manual closed"
        result = self._set_spectrograph_shutter_mode(mode, reason)
        if self._spectrograph_call_succeeded(result):
            return result
        return self._set_camera_shutter_mode(
            1 if self.shutter_is_open else 2,
            f"{reason} fallback",
        )

    def _push_shutter_for_acquisition(self):
        """Apply the shutter mode used while measurements are running."""
        if self.shutter_external_enabled:
            self._set_spectrograph_shutter_mode(1, f"EXT acquisition {self.get_shutter_mode()}")
            self.shutter_is_open = True
            self._acquisition_shutter_closed = False
            mode = self._selected_acquisition_shutter_mode()
            return self._set_camera_shutter_mode(mode, f"EXT acquisition {self.get_shutter_mode()}")
        return self._push_shutter_to_hardware()

    def _close_acquisition_controlled_shutter(self):
        if self.shutter_external_enabled and not self._acquisition_shutter_closed:
            self._set_spectrograph_shutter_mode(0, "EXT acquisition finished")
            self._set_camera_shutter_mode(2, "EXT acquisition finished")
            self.shutter_is_open = False
            self._acquisition_shutter_closed = True

    def _get_focus_mirror_position(self):
        result = self._safe_spectrograph_call("GetFocusMirror", self.device_index)
        if self._spectrograph_call_succeeded(result) and isinstance(result, tuple) and len(result) > 1:
            return int(result[1])
        return None

    def _get_focus_mirror_max_steps(self):
        result = self._safe_spectrograph_call("GetFocusMirrorMaxSteps", self.device_index)
        if self._spectrograph_call_succeeded(result) and isinstance(result, tuple) and len(result) > 1:
            return max(int(result[1]), 0)
        return None

    def _push_focus_mirror_to_hardware(self, reason="manual"):
        """Move the focus mirror to ``focus_mirror_steps``.

        The SDK's SetFocusMirror argument is relative movement, while the GUI
        stores and displays an absolute focus position. Convert here so typing
        240 means "go to 240", not "move another 240 steps".
        """
        if not self.connected or self.spectrograph is None:
            return None

        target_steps = max(int(float(self.focus_mirror_steps)), 0)
        max_steps = self._get_focus_mirror_max_steps()
        if max_steps is not None:
            target_steps = min(target_steps, max_steps)

        current_steps = self._get_focus_mirror_position()
        movement_steps = target_steps if current_steps is None else target_steps - current_steps

        if movement_steps == 0:
            print(f"[Kymera] Focus mirror already at {target_steps} steps ({reason}).")
            self.focus_mirror_steps = target_steps
            return None

        result = self._safe_spectrograph_call(
            "SetFocusMirror", self.device_index, int(movement_steps)
        )
        status = result[0] if isinstance(result, tuple) else result
        ok = self._spectrograph_call_succeeded(result)
        if ok:
            self.focus_mirror_steps = target_steps
        print(
            f"[Kymera] SetFocusMirror({reason}, target={target_steps}, "
            f"movement={movement_steps}) -> status={status} ({'OK' if ok else 'FAIL'})"
        )
        return result

    def set_focus_mirror_steps(self, steps):
        self.focus_mirror_steps = max(int(float(steps)), 0)
        self._push_focus_mirror_to_hardware("manual")
        self._save_persistent_settings()
        return self.focus_mirror_steps

    def autofocus_focus_mirror(self):
        self.focus_mirror_steps = 237
        self._push_focus_mirror_to_hardware("auto")
        self._save_persistent_settings()
        return self.focus_mirror_steps

    def set_side_input_iris_steps(self, steps):
        self.side_input_iris_steps = min(max(int(float(steps)), 0), 100)
        if self.connected and self.spectrograph is not None:
            result = self._safe_spectrograph_call(
                "SetIris", self.device_index, self._side_iris_port, int(self.side_input_iris_steps)
            )
            status = result[0] if isinstance(result, tuple) else result
            ok = self._spectrograph_call_succeeded(result)
            print(
                f"[Kymera] SetIris(side={self._side_iris_port}, value={self.side_input_iris_steps}) "
                f"-> status={status} ({'OK' if ok else 'FAIL'})"
            )
        self._save_persistent_settings()
        return self.side_input_iris_steps

    def set_excitation_wavelength(self, wavelength_nm):
        self.excitation_wavelength_nm = max(float(wavelength_nm), 1.0)
        self._save_persistent_settings()
        return self.excitation_wavelength_nm

    def format_chart_data(self, wavelengths, intensities):
        """Return live-plot data in the user-selected axis (nm or Raman shift)."""
        display_intensities = np.asarray(intensities)
        if self.mirror_spectral_axis_for_display and display_intensities.ndim == 1:
            display_intensities = display_intensities[::-1]

        if self.axis_mode == "wavelength":
            return np.asarray(wavelengths, dtype=np.float64), display_intensities
        return self.wavelength_to_raman_shift(wavelengths), display_intensities

    def get_axis_labels(self):
        if self.axis_mode == "wavelength":
            return "Wavelength [nm]", "Intensity [counts]"
        return "Raman shift [cm^-1]", "Intensity [counts]"

    def set_axis_mode(self, mode):
        if mode in ("raman", "wavelength"):
            self.axis_mode = mode
            self._save_persistent_settings()
        return self.axis_mode

    @property
    def wavelength_display_range_nm(self):
        """Live display range, derived from the current grating's SDK reachable limits."""
        grating = self.get_active_grating() if self.available_gratings else None
        if grating:
            limits = grating.get("wavelength_limits_nm")
            if limits and len(limits) == 2:
                low, high = float(limits[0]), float(limits[1])
                if high > low:
                    # Tiny padding so markers at the extremes are still clickable.
                    span = high - low
                    padding = max(span * 0.02, 5.0)
                    return (max(low - padding, 0.0), high + padding)
        return self._fallback_wavelength_display_range_nm

    def wavelength_to_raman_shift(self, wavelengths_nm):
        wavelengths_nm = np.asarray(wavelengths_nm, dtype=np.float64)
        laser_wavenumber = 1e7 / float(self.excitation_wavelength_nm)
        # SOLIS uses the signed Raman convention: Stokes is positive and
        # anti-Stokes is negative. Do not force abs(), or the displayed detector
        # orientation flips when the wavelength window crosses the excitation line.
        return laser_wavenumber - (1e7 / wavelengths_nm)

    def raman_shift_to_wavelength(self, shifts_cm):
        shifts_cm = np.asarray(shifts_cm, dtype=np.float64)
        laser_wavenumber = 1e7 / float(self.excitation_wavelength_nm)
        denominator = laser_wavenumber - shifts_cm
        denominator = np.where(denominator == 0, np.nan, denominator)
        return 1e7 / denominator

    def build_detector_image(self, intensities):
        """Return the most recent real CCD frame; fall back to a pseudo-image."""
        if self._last_detector_frame is not None and self._last_detector_frame.ndim == 2:
            return np.clip(np.asarray(self._last_detector_frame, dtype=np.float64), 0.0, None)

        values = np.asarray(intensities, dtype=np.float64)
        if values.size == 0:
            return np.zeros((self.detector_rows, 1), dtype=np.float64)

        clipped = np.clip(values, 0.0, None)
        rows = max(int(self.detector_rows), 64)
        row_axis = np.linspace(-1.0, 1.0, rows, dtype=np.float64)[:, None]
        beam_profile = np.exp(-(row_axis**2) / 0.03)
        baseline = float(np.nanpercentile(clipped, 5)) if clipped.size else 0.0
        background = max(baseline * 0.85, clipped.max() * 0.03 if clipped.size else 0.0, 1.0)
        image = background + beam_profile * clipped[None, :]
        image += 0.05 * background * np.exp(-(row_axis**2) / 0.2)
        image += 0.015 * clipped[None, :] * np.cos(row_axis * np.pi * 3.0)

        return np.clip(image, 0.0, None)

    def _load_sdk_classes(self):
        import ctypes.util

        sdk_root = configure_path()
        print(f"[Kymera] Andor SDK root: {sdk_root}")
        print(f"[Kymera] atmcd64d.dll resolves to: {ctypes.util.find_library('atmcd64d.dll')}")
        print(f"[Kymera] atspectrograph.dll resolves to: {ctypes.util.find_library('atspectrograph.dll')}")

        try:
            from pyAndorSDK2 import atmcd
            from pyAndorSDK2.atmcd_errors import Error_Codes
            from pyAndorSpectrograph import ATSpectrograph
        except ImportError as error:
            print(f"[Kymera] Could not import vendored Andor SDK packages: {error}")
            print(f"[Kymera] Expected packages under: {sdk_root}")
            raise

        return atmcd, Error_Codes, ATSpectrograph

    def _shutdown_sdk(self):
        if self.spectrograph is not None:
            try:
                self.spectrograph.Close()
            except Exception as error:
                debugp("Kymera", f"Spectrograph shutdown failed: {error}")
            finally:
                self.spectrograph = None

        if self.camera is not None:
            try:
                self.camera.ShutDown()
            except Exception as error:
                debugp("Kymera", f"Camera shutdown failed: {error}")
            finally:
                self.camera = None

    def __repr__(self):
        return f"{self.name} Kymera 328i, serial : {self.serial}"
