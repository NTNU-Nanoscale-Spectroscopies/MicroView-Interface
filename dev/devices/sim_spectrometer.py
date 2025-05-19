
import queue
import random
import threading
import time

import numpy as np
from dev.debugHelp import debugp
from dev.devices.spectrometer import MySpectrometer


class MySimSpectrometer(MySpectrometer):

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
        """Override connect method"""        
        self.connected = False
        self.is_running = False
        
        temp = self.get_temperature()
        if temp != None and temp < 0 :
            self.connected = True
            
        return self.connected

    def start(self):
        """Override start method"""
        if self.connected and not self.is_running:
            self.is_running = True
            self.data_thread = threading.Thread(target=self.acquire_data, daemon=True)
            self.data_thread.start()

    def acquire_data(self):
            """Override acquire_data method with simulation option"""
            try:
                self.index = 0
                while self.is_running:
                    
                    wavelengths, intensities = self.simulate_spectrum()
                   
                    # Place data in the chart queue
                    if not self.chart_queue.empty():
                        self.chart_queue.get_nowait()
                    self.chart_queue.put_nowait((wavelengths, intensities))

                    # Place data in the save queue if needed
                    if self.acquire_save_data > 0:
                        self.index += 1
                        if self.index >= self.acquire_save_data:
                            self.index = 0
                            self.save_queue.put((wavelengths, intensities))
                    
                    time.sleep(0.1)

            except Exception as e:
                print(f"Error in spectrometer acquisition: {e}")

    def simulate_spectrum(self):
        """Simulates wavelengths and intensities for testing purposes

        Parameters
        ------------
        graph : `int`
            Selects between two different simulated spectra (1 or 2)
        """

        # Create Gaussian peaks for a simulated spectrum
        def gaussian(x, amp, cen, wid):
            return amp * np.exp(-(x - cen) ** 2 / (2 * wid ** 2)).astype(np.float64)

        # Generate intensities for Graph 1 (Visible Spectrum)
        if self.name == "Spectrometer-VIS":
            # Generate wavelengths from 400 to 700 nm as float64
            wavelengths = np.linspace(400.0, 700.0, 1024, dtype=np.float64)
            
            intensities = (
                gaussian(wavelengths, 100.0, 450.0, 20.0) +  # Peak at 450 nm
                gaussian(wavelengths, 200.0, 550.0, 30.0) +  # Peak at 550 nm
                gaussian(wavelengths, 150.0, 620.0, 25.0)    # Peak at 620 nm
            ).astype(np.float64)

        # Generate intensities for Graph 2 (Near-Infrared Spectrum)
        else:
            # Generate wavelengths from 700 to 1000 nm as float64
            wavelengths = np.linspace(700.0, 1000.0, 1024, dtype=np.float64)
            
            intensities = (
                gaussian(wavelengths, 180.0, 750.0, 20.0) +  # Peak at 750 nm
                gaussian(wavelengths, 220.0, 820.0, 30.0) +  # Peak at 820 nm
                gaussian(wavelengths, 160.0, 900.0, 25.0)    # Peak at 900 nm
            ).astype(np.float64)
        
        # Add random noise to simulate real data
        noise = np.random.normal(0.0, 10.0, wavelengths.shape).astype(np.float64)
        intensities = intensities + noise
        intensities = np.clip(intensities, 0, None)  # Ensure no negative intensities

        # Ensure all outputs are float64
        wavelengths = wavelengths.astype(np.float64)
        intensities = intensities.astype(np.float64)

        return wavelengths, intensities
    
    def simulate_spectrum_sin(self):
        """Simulates wavelengths and intensities for testing purposes

        Parameters
        ------------
        graph : `int`
            Selects between two different simulated spectra (1 or 2)
        """

        # Generate wavelengths based on the spectrometer type
        if self.name == "Spectrometer-VIS":
            # Visible: 400–700 nm
            wavelengths = np.linspace(400.0, 700.0, 1024, dtype=np.float64)
            frequency = 0.05  # Adjust frequency to control number of waves
            phase = 0.0       # Phase shift
            amplitude = 100.0
        else:
            # Near-Infrared: 700–1000 nm
            wavelengths = np.linspace(700.0, 1000.0, 1024, dtype=np.float64)
            frequency = 0.04
            phase = np.pi / 4
            amplitude = 120.0

        # Create sine wave intensities
        intensities = (amplitude * np.sin(2 * np.pi * frequency * wavelengths + phase)).astype(np.float64)

        # Normalize to be positive and add random noise
        intensities = intensities - np.min(intensities)  # Shift to be all positive
        noise = np.random.normal(0.0, 10.0, wavelengths.shape).astype(np.float64)
        intensities = intensities + noise
        intensities = np.clip(intensities, 0, None)  # Remove negatives from noise

        # Ensure types
        wavelengths = wavelengths.astype(np.float64)
        intensities = intensities.astype(np.float64)

        return wavelengths, intensities

       

    def stop(self):
        """Override stop method"""
        self.is_running = False

    def disconnect(self):
        """Override disconnect method"""
        if self.connected:
            self.stop()
            if hasattr(self, 'data_thread'):
                self.data_thread.join(timeout=1)  # Wait for thread to finish
            # Clear queues
            while not self.chart_queue.empty():
                self.chart_queue.get_nowait()
            while not self.save_queue.empty():
                self.save_queue.get_nowait()
            self.connected = False


    def set_integration_time(self, time_microseconds):
        """Override set_integration_time method"""
        if self.connected:
            #self.spectrometer.integration_time_micros(time_microseconds)
            self.integration_time = time_microseconds

    def get_temperature(self):
        if self.name == "Spectrometer-VIS":
            return round(random.uniform(-5,-1), 2)
        else:
            return round(random.uniform(-10,-4), 2)

    def __repr__(self):
        """Override __repr__ method"""
        return f"New {self.name}, serial : {self.serial}"
