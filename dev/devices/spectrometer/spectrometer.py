from dev.devices.devices import MyDevice
from seabreeze.spectrometers import Spectrometer

class MySpectrometer(MyDevice):
    def __init__(self, name, serial, enabled = True):
        super().__init__(name, serial, "OceanSepctrometer", "edtiable", enabled)

    def connection(self):
        try:
            self.spectrometer = Spectrometer.from_serial_number(self.serial)
            print("Spect connected : ",self.spectrometer)
            self.connected = True
        except Exception as e:
            print(f"Unable to connect to device “{self.name}”, serial : “{self.serial}”. {e}")
            self.connected = False
        return self.connected

    def set_integration_time(self, time_microseconds):
        self.spectrometer.integration_time_micros(time_microseconds)

    def get_spectrum(self):
        return self.spectrometer.spectrum()
