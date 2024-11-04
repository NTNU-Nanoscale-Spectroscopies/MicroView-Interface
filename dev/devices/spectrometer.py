from .devices import MyDevice
from seabreeze.spectrometers import Spectrometer
import threading
import queue

class MySpectrometer(MyDevice):
    def __init__(self, name, serial, enabled = True):
        super().__init__(name, serial, "OceanSepctrometer", "edtiable", enabled)
        self.data_queue = queue.Queue()
        self.integration_time = None

    def connect(self):
        try:
            self.spectrometer = Spectrometer.from_serial_number(self.serial)
            self.connected = True
            self.is_running = False
        except Exception as e:
            print(f"Unable to connect to “{self.name}” device with serial number “{self.serial}” : {e}")
            self.connected = False
        return self.connected

    def start(self):
        if self.connected and not self.is_running:
            self.data_thread = threading.Thread(target=self.acquire_data, daemon=True)
            self.data_thread.start()
            self.is_running = True

    def acquire_data(self):
        try:
            print("run", self.is_running)
            while self.is_running:
                wavelengths, intensities = self.spectrometer.spectrum()
                self.data_queue.put((wavelengths, intensities))
        except Exception as e:
            print(f"Error in sepectrometer acquisition: {e}")

    def stop(self):
        self.is_running = False
        if self.data_thread.is_alive():
            self.data_thread.join()

    def disconnect(self):
        if self.connected:
            self.stop()
            self.spectrometer.close()
            self.connected = False

    def set_integration_time(self, time_microseconds):
        if self.connected: 
            self.spectrometer.integration_time_micros(time_microseconds)
            self.integration_time = time_microseconds