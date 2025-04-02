import time
import numpy as np

from dev.debugHelp import debugp
from plot import plot_data


class AutoCalibrate():
    """Class for combining all the logic to auto calibrate a rotation mount with polarizer"""

    def __init__(self, rotation_mount, spectrometer):
        """Initializes the AutoCalibrate class.

        Args:
            rotation_mount (MyRotationMount): The rotation mount used for calibration.
            spectrometer (MySpectrometer): The spectrometer used to measure intensity values.
        """
        self.rotation_mount = rotation_mount
        self.spectrometer = spectrometer
        self.zero_angle = None
        self.ninety_angle = None

    def start(self):
        """Performs the auto-calibration process by rotating the mount, measuring intensity, 
        and determining the zero and ninety-degree angles based on intensities.
        """
        
        debugp("AutoCalibration", "Starting auto calibration")
        
        wave_length = 650
        
        angle_intensity = np.zeros((360, 2))

        self.rotation_mount.home()
        time.sleep(0.2)
        
        for angle in range(360):
            
            self.rotation_mount.set_absolute_angle(angle)
            time.sleep(0.2)

            wavelengths, intensities = self.spectrometer.save_queue.get()

            wave_length_index = np.where(wavelengths >= wave_length)[0][0]

            intensity = intensities[wave_length_index]
            angle_intensity[angle] = [angle, intensity]  

            max_idx = np.argmax(angle_intensity[:, 1])
            min_idx = np.argmin(angle_intensity[:, 1])

        max_angle, max_intensity = angle_intensity[max_idx]
        min_angle, min_intensity = angle_intensity[min_idx]

        #plot_data(angle_intensity)

        self.zero_angle = max_angle
        self.ninety_angle = min_angle
        
        debugp("Autocalib", f"Max Intensity: {max_intensity} at Angle: {max_angle}")
        debugp("Autocalib", f"Min Intensity: {min_intensity} at Angle: {min_angle}")
        
    def get_zero_angle(self):
        """Returns the angle corresponding to maximum intensity (zero-degree angle).
        """
        return self.zero_angle
    
    def get_ninety_angle(self):
        """Returns the angle corresponding to minimum intensity (ninety-degree angle).
        """
        return self.ninety_angle