import time
import elliptec
import numpy as np

from dev.debugHelp import debugp


class AutoCalibrate():
    """Class for combining all the logic to auto calibrate a rotation mount with polarizer"""

    def __init__(self, rotation_mount, spectrometer):
        """_summary_

        Args:
            rotation_mount (MyRotationMount): 
            spectrometer (MySpectrometer): 
        """
        self.rotation_mount = rotation_mount
        self.spectrometer = spectrometer
        self.zero_angle = None
        self.ninety_angle = None

    def start(self):
        debugp("AutoCalibration", "Starting auto calibration")
        
        #for each dergre, get spectrometer ?
        
        #home
        #JSP Record the spectrum of the polarized light as a reference.
        wave_length = 500
        
        angle_intensity = np.zeros((180, 2))  # Preallocate NumPy array for efficiency

        self.rotation_mount.home()
        time.sleep(0.2)
        
        for angle in range(180):  # No need for (0, 180), range already excludes 180
            self.rotation_mount.set_absolute_angle(angle)
            time.sleep(0.2)

            wavelengths, intensities = self.spectrometer.chart_queue.get()

            wave_length_index = np.where(wavelengths == wave_length)[0][0]  # Get first matching index
            
            intensity = intensities[wave_length_index]
            angle_intensity[angle] = [angle, intensity]  

            # Extract max and min intensities with corresponding angles
            max_idx = np.argmax(angle_intensity[:, 1])
            min_idx = np.argmin(angle_intensity[:, 1])

        max_angle, max_intensity = angle_intensity[max_idx]
        min_angle, min_intensity = angle_intensity[min_idx]

        self.zero_angle = max_angle
        self.ninety_angle = min_angle
        
        print(f"Max Intensity: {max_intensity} at Angle: {max_angle}")
        print(f"Min Intensity: {min_intensity} at Angle: {min_angle}")
        
    def get_zero_angle(self):
        return self.zero_angle
    
    def get_ninety_angle(self):
        return self.ninety_angle