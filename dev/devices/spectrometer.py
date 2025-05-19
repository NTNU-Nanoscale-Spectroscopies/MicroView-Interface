from seabreeze.spectrometers import Spectrometer
import threading
import queue
import time

from dev.debugHelp import debugp


class MySpectrometer():
    """Class for creating an object that communicates with and controls a spectrometer-type device"""

    def __init__(self, name, serial, enable=False, dark_correction=False, integration_time=100):
        """Create a new Spectrometer object for easy communication with the device concerned

        Parameters
        ------------
        name : `str`
            Visible name of this device in the graphical interface
        serial : `str`
            The unique device serial number enabling communication
        enable : `bool`, optional
            Allows or prevents the device from starting once it is connected. False by default
        dark_correction : `bool`, optional
            Whether to apply dark correction, False by default
        integration_time : `float`, optional
            Default spectrometer integration time in milliseconds, 100ms by default
        """
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
        """Try to establish communication with the device

        Retruns
        ------------
        connect : `bool`
            Whether communication is established
        """
        self.connected = False
        self.is_running = False
        try:
            self.spectrometer = Spectrometer.from_serial_number(self.serial)
            self.connected = True
                
        except Exception as e:
            pass
        return self.connected


    def start(self):
        """Starts spectrometer data acquisition thread
        """
        if self.connected and not self.is_running:
            debugp("Thread", "Spectrometer thread started")
            #debugp("Thread", f"Spectrometer thread started - {self}")
            self.is_running = True
            self.data_thread = threading.Thread(target=self.acquire_data, daemon=True)
            self.data_thread.start()


    def acquire_data(self):
        """Spectrometer data acquisition loop with speed relative to acquisition time

        Notes
        ------------
        Data is added to two separate queues. These structures are thread-safe, ensuring data security and preventing loss.
        The first queue, `chart_queue`, is used for displaying the graph and operates independently of the second queue, 
        `save_queue`, which is dedicated to storing spectrometer save data
        """
        try:
            self.index = 0
            while self.is_running:
                wavelengths, intensities = self.spectrometer.spectrum(correct_dark_counts=self.dark_correction)
                
                #Test faster ???
                if not self.chart_queue.empty():
                    self.chart_queue.get_nowait() 
                self.chart_queue.put_nowait((wavelengths, intensities))
                
                if self.acquire_save_data > 0:
                    self.index += 1
                    if self.index >= self.acquire_save_data:
                        self.index = 0
                        self.save_queue.put((wavelengths, intensities))

        except Exception as e:
            print(f"Error in sepectrometer acquisition: {e}")


    def stop(self):
        """Stops spectrometer data acquisition thread
        """
        self.is_running = False


    def disconnect(self):
        """Try to cleanly terminate communication with the device
        """
        if self.connected:
            self.stop()
            time.sleep(0.2)
            self.spectrometer.close() #Maybe we shouldn't use .close() ?
            self.connected = False
            print(f"{self.name} disconnected.")


    def set_integration_time(self, time_microseconds):
        """Sets the spectrometer integration time

        Parameters
        ------------
        time_microseconds : `float`
            The required spectrometer integration time
        """
        if self.connected:
            self.spectrometer.integration_time_micros(time_microseconds)
            self.integration_time = time_microseconds

    def get_temperature(self):
        try:
            # Check if TEC is enabled (Power Supply)
            tec_status = self.spectrometer.f.thermo_electric.enable_tec(True)
            tec_temp = self.spectrometer.f.thermo_electric.read_temperature_degrees_celsius()
            debugp("TEC Enabled:", f"{self.name} : {tec_status}, temp : {tec_temp}c")
            return tec_temp
        except Exception as e:
            debugp("TEC", f"Tec not working : {e}")
        return

    def __repr__(self):
        return f"{self.name}, serial : {self.serial}"