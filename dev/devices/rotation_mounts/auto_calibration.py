from datetime import *
import time
import numpy as np

from dev.debugHelp import debugp
from plot import plot_data


class AutoCalibrate():
    """Class for combining all the logic to auto calibrate a rotation mount with polarizer"""

    def __init__(self, rotation_mount, spectrometer, spectrometer_frame):
        """Initializes the AutoCalibrate class.

        Args:
            rotation_mount (MyRotationMount): The rotation mount used for calibration.
            spectrometer (MySpectrometer): The spectrometer used to measure intensity values.
        """
        self.rotation_mount = rotation_mount
        self.spectrometer = spectrometer
        self.spectrometer_frame = spectrometer_frame
        self.zero_angle = None
        self.ninety_angle = None

    def start(self):
        """Performs the auto-calibration process by rotating the mount, measuring intensity, 
        and determining the zero and ninety-degree angles based on intensities.
        """
        
        debugp("AutoCalibration", "Starting auto calibration")
        
        
        
        self.rotation_mount.home()
        time.sleep(0.2)
        
        wave_length = 650
        angle_intensity = np.full((360, 2), np.nan)
        date = f"{datetime.now():%H.%M.%S}"
        all_data = []
        
        for angle in range(0,360,5):
            
            self.rotation_mount.set_absolute_angle(angle)
            time.sleep((self.spectrometer.integration_time/1000)/1000 + 0.5)
            chart_data = self.spectrometer.chart_queue.get()
            all_data.append([angle, chart_data])
            
            wavelengths, intensities = chart_data
            wave_length_index = np.where(wavelengths >= wave_length)[0][0]
            intensity = intensities[wave_length_index]
            angle_intensity[angle] = [angle, intensity]  
            
            

        max_idx = np.nanargmax(angle_intensity[:, 1])
        min_idx = np.nanargmin(angle_intensity[:, 1])
        max_angle, max_intensity = angle_intensity[max_idx]
        min_angle, min_intensity = angle_intensity[min_idx]

        self.zero_angle = max_angle
        self.ninety_angle = min_angle
        
        debugp("Autocalib", f"Max Intensity: {max_intensity} at Angle: {max_angle}")
        debugp("Autocalib", f"Min Intensity: {min_intensity} at Angle: {min_angle}")
         
        for data in all_data:
            
            angle = data[0]
            wavelengths, intensities = data[1]
            file_path = self.spectrometer_frame.file_system.get_calibration_directory(self.spectrometer.integration_time)
            file_path = file_path.replace("£", self.rotation_mount.name).replace("#", date).replace("$", f"{angle}").replace("@", self.spectrometer.name.split("-")[-1])   
            
            self.spectrometer_frame.single_save(file_path, wavelengths, intensities, True, False, self.spectrometer_frame.split -1, False)
       
    
    def get_zero_angle(self):
        """Returns the angle corresponding to maximum intensity (zero-degree angle).
        """
        return self.zero_angle
    
    def get_ninety_angle(self):
        """Returns the angle corresponding to minimum intensity (ninety-degree angle).
        """
        return self.ninety_angle