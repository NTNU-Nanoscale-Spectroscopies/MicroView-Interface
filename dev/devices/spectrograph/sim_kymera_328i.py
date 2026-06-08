import random
import threading
import time

import numpy as np

from .kymera_328i import MyKymera328i


class MySimKymera328i(MyKymera328i):
    """Simulator for the Kymera 328i spectrograph."""

    def __init__(
        self,
        name,
        serial,
        enable=False,
        dark_correction=False,
        integration_time=100,
        pixels=1024,
    ):
        super().__init__(name, serial, enable, dark_correction, integration_time)
        self.pixels = pixels

    def connect(self):
        self.connected = True
        self.is_running = False
        return self.connected

    def start(self):
        if self.connected and not self.is_running:
            self.is_running = True
            self.data_thread = threading.Thread(target=self.acquire_data, daemon=True)
            self.data_thread.start()

    def acquire_data(self):
        self.index = 0
        while self.is_running:
            wavelengths, intensities = self.simulate_spectrum()

            if not self.chart_queue.empty():
                self.chart_queue.get_nowait()
            self.chart_queue.put_nowait((wavelengths, intensities))

            if self.acquire_save_data > 0 and getattr(self, "auto_save_enabled", True):
                self.index += 1
                if self.index >= self.acquire_save_data:
                    self.index = 0
                    self.save_queue.put((wavelengths, intensities))

            time.sleep(max(self.integration_time / 1000000.0, 0.02))

    def simulate_spectrum(self):
        raman_shifts = np.linspace(100.0, 1800.0, self.pixels, dtype=np.float64)
        wavelengths = self.raman_shift_to_wavelength(raman_shifts)

        def gaussian(x, amp, center, width):
            return amp * np.exp(-((x - center) ** 2) / (2 * width**2))

        intensities = (
            gaussian(raman_shifts, 160.0, 220.0, 12.0)
            + gaussian(raman_shifts, 120.0, 520.0, 10.0)
            + gaussian(raman_shifts, 210.0, 1010.0, 7.0)
            + gaussian(raman_shifts, 540.0, 1118.0, 9.0)
            + gaussian(raman_shifts, 320.0, 1298.0, 10.0)
            + gaussian(raman_shifts, 650.0, 1595.0, 11.0)
        )
        baseline = 90.0 + 8.0 * np.sin(raman_shifts / 180.0)
        intensities = baseline + intensities
        intensities += np.random.normal(0.0, 4.0, wavelengths.shape)
        intensities = np.clip(intensities, 0.0, None).astype(np.float64)

        return wavelengths, intensities

    def capture_signal_series(self, progress_callback=None, spool_sif=False):
        frame_count = self.get_signal_frame_count()
        frames = []
        for frame_index in range(frame_count):
            wavelengths, intensities = self.simulate_spectrum()
            frames.append((wavelengths.copy(), intensities.copy()))
            if progress_callback:
                progress_callback(frame_index + 1, frame_count)
            time.sleep(max(self.integration_time / 1000000.0, 0.02))
        return frames

    def save_last_signal_as_sif(self, path, comment="", calibrated=True):
        return False, "simulator"

    def stop(self):
        self.is_running = False

    def disconnect(self):
        if self.connected:
            self.stop()
            if hasattr(self, "data_thread"):
                self.data_thread.join(timeout=1)

            while not self.chart_queue.empty():
                self.chart_queue.get_nowait()
            while not self.save_queue.empty():
                self.save_queue.get_nowait()

            self.connected = False

    def get_temperature(self):
        return round(random.uniform(-70.0, -60.0), 2)

    def __repr__(self):
        return f"Simulated {self.name} Kymera 328i, serial : {self.serial}"
