from seabreeze.spectrometers import Spectrometer
import threading
import queue
import time

class MySpectrometer():
    def __init__(self, name, serial, enable=False, dark_correction=False, integration_time=100):
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

    def connect(self):
        self.connected = False
        self.is_running = False
        try:
            self.spectrometer = Spectrometer.from_serial_number(self.serial)
            self.connected = True
        except Exception as e:
            pass
        return self.connected

    def start(self):
        if self.connected and not self.is_running:
            self.is_running = True
            self.data_thread = threading.Thread(target=self.acquire_data, daemon=True)
            self.data_thread.start()

    def acquire_data(self):
        try:
            self.index = 0
            while self.is_running:
                wavelengths, intensities = self.spectrometer.spectrum(correct_dark_counts=self.dark_correction)
                self.chart_queue.put((wavelengths, intensities))
                if self.acquire_save_data > 0:
                    self.index += 1
                    if self.index >= self.acquire_save_data:
                        self.index = 0
                        self.save_queue.put((wavelengths, intensities))
        except Exception as e:
            print(f"Error in sepectrometer acquisition: {e}")

    def stop(self):
        self.is_running = False

    def disconnect(self):
        if self.connected:
            self.stop()
            time.sleep(0.2)
            self.spectrometer.close()
            self.connected = False

    def set_integration_time(self, time_microseconds):
        if self.connected:
            self.spectrometer.integration_time_micros(time_microseconds)
            self.integration_time = time_microseconds

    def __repr__(self):
        return f"{self.name}, serial : {self.serial}"