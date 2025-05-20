from datetime import *
import os
import platform
import subprocess
import threading
import time
import numpy as np

from dev.debugHelp import debugp

import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt

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
        self.calibration_wavelength = 650
        self.calibration_folder = "Calibration"
        self.saved_integration_time = (self.spectrometer.integration_time)
        
        
        self.angle1, self.inten1 = None, None
        self.angle2, self.inten2 = None, None
        self.angle3, self.inten3 = None, None
        self.angle4, self.inten4 = None, None
        
    def start(self, func):
        """Performs the auto-calibration process by rotating the mount, measuring intensity, 
        and determining the zero and ninety-degree angles based on intensities.
        """
                
        self.start_routine(func)

        
    def start_routine(self, display_info, overide_integration_time=True):
        """Performs auto-calibration by rotating the mount, measuring intensity,
        and determining zero and ninety-degree angles based on intensity peaks.
        """
        
        debugp("AutoCalibration", "Starting auto calibration")
        calibration_folder = self.spectrometer_frame.file_system.get_calibration_directory(self.calibration_folder)
        self.rotation_mount.home()
        time.sleep(0.2)

        def measure_angles(angle_range, label):
            results = []
            for angle in angle_range:
                real_angle = angle % 360
                self.rotation_mount.set_absolute_angle(real_angle)
                time.sleep((self.spectrometer.integration_time / 1_000_000) + 0.5)
                wavelengths, intensities = self.spectrometer.chart_queue.get()
                intensity = intensities[np.where(wavelengths >= self.calibration_wavelength)[0][0]]
                angle_intensity[real_angle] = [real_angle, intensity]
                display_info(f"{label}\nMeasuring angle: {real_angle}°\n{self.calibration_wavelength}nm: {round(intensity, 3)}")
                results.append([real_angle, (wavelengths, intensities)])
            return results

        if overide_integration_time:
            self.spectrometer.set_integration_time(300000)

        angle_intensity = np.full((360, 2), np.nan)
        date = f"{datetime.now():%H.%M.%S}"
        all_data = measure_angles(range(0, 360, 10), "First Pass")

        angles, intensities = angle_intensity[:, 0], angle_intensity[:, 1]
        self.angles1, self.inten1 = angles, intensities
        #self.plot_data(angle_intensity, calibration_folder, "raw_10_degs", self.calibration_wavelength)

        max_angle = self.get_max_angle(angles, intensities)
        print(f"Max angle orig: {max_angle}")


        sorted_indices = np.argsort(angles)
        angles, intensities = angles[sorted_indices], intensities[sorted_indices]
        smoothed = self.moving_average(intensities, window=5)
        self.angles2, self.inten2 = angles, smoothed
        #self.plot_both(angles, smoothed, calibration_folder, "smoothed_10_degs", self.calibration_wavelength)

        max_angle = self.get_max_angle(angles, intensities)
        print(f"Max angle smoothed: {max_angle}")

        padding_angle = 20
        starting_angle = (max_angle - padding_angle) % 360

        debugp("AutoCalibration", f"Max angle :{max_angle}, Starting angle :{starting_angle}")

        all_data += measure_angles(range(int(starting_angle), int(max_angle + padding_angle)), "Second Pass")

        if overide_integration_time:
            self.spectrometer.set_integration_time(self.saved_integration_time)

        angles, intensities = angle_intensity[:, 0], angle_intensity[:, 1]
        self.angles3, self.inten3 = angles, intensities
        sorted_indices = np.argsort(angles)
        angles, intensities = angles[sorted_indices], intensities[sorted_indices]

        #self.plot_data(angle_intensity, calibration_folder, "raw_1_deg", self.calibration_wavelength)
        
        smoothed = self.moving_average(intensities, window=15)

        # Apply mask
        mask = (angles >= starting_angle) & (angles <= max_angle + padding_angle)
        angles_subset = angles[mask]
        smoothed = np.array(smoothed)
        smoothed_subset = smoothed[mask]

        mask = (angles > starting_angle) & (angles < max_angle + padding_angle)

        # Create a full NaN array of same shape
        smoothed_subset_full = np.full_like(smoothed, np.nan)
        # Fill only masked positions with actual values
        smoothed_subset_full[mask] = smoothed[mask]

        self.angles4, self.inten4 = angles, smoothed_subset_full
        #self.plot_both(angles_subset, smoothed_subset, calibration_folder, "smoothed_1_deg", self.calibration_wavelength)

        angle_max = angles_subset[np.nanargmax(smoothed_subset)]
        print(f"Max angle smoothed 1deg: {angle_max}")

        max_idx = np.nanargmax(angle_intensity[:, 1])
        min_idx = np.nanargmin(angle_intensity[:, 1])
        max_angle, max_intensity = angle_intensity[max_idx]
        min_angle, min_intensity = angle_intensity[min_idx]

        self.zero_angle, self.ninety_angle = max_angle, min_angle

        debugp("Autocalibration", f"Max Intensity: {max_intensity} at Angle: {max_angle}")
        debugp("Autocalibration", f"Min Intensity: {min_intensity} at Angle: {min_angle}")

        self.save_data(all_data, calibration_folder, date)
        
        #Plot recorded data
        #self.plot_data(angle_intensity, calibration_folder, date, self.calibration_wavelength)
        
        self.plot_all(calibration_folder, date, self.calibration_wavelength)
        

    def get_max_angle(self, angles, intensities):
        valid_mask = ~np.isnan(intensities) & ~np.isnan(angles)
        valid_angles = angles[valid_mask]
        valid_intensities = intensities[valid_mask]

        max_index_raw = np.argmax(valid_intensities)
        angle_max_raw = valid_angles[max_index_raw]

        return angle_max_raw

    def moving_average(self, values, window=3):
        smoothed = []
        for i in range(len(values)):
            start = max(0, i - window // 2)
            end = min(len(values), i + window // 2 + 1)
            avg = sum(values[start:end]) / (end - start)
            smoothed.append(avg)
        return smoothed
        
    def save_data(self, all_data, calibration_folder, date):
        
        for data in all_data:
            
            angle = data[0]
            wavelengths, intensities = data[1]
            file_path = self.spectrometer_frame.file_system.get_calibration_file_name(self.spectrometer.integration_time, self.calibration_folder)
            file_path = file_path.replace("£", self.rotation_mount.name).replace("#", date).replace("$", f"{angle}").replace("@", self.spectrometer.name.split("-")[-1])   
            
            self.spectrometer_frame.single_save(f"{calibration_folder}{file_path}", wavelengths, intensities, True, False, self.spectrometer_frame.split -1, False)
    
    def get_zero_angle(self):
        """Returns the angle corresponding to maximum intensity (zero-degree angle).
        """
        return self.zero_angle
    
    def get_ninety_angle(self):
        """Returns the angle corresponding to minimum intensity (ninety-degree angle).
        """
        return self.ninety_angle
    
    def set_settings(self, calibration_wavelength, calibration_folder):
        self.calibration_wavelength = calibration_wavelength
        self.calibration_folder = calibration_folder




    #Plot functions usefull for debugging
    def plot_data(self, data, calibration_folder, date, wavelength):
        # Plotting
        file_name = f"{calibration_folder}calibration_{date}_{wavelength}nm_plot.png"
        matplotlib.use("Agg")
        plt.figure(figsize=(10, 6))
        plt.plot(data[:, 0], data[:, 1], marker='o', linestyle='-', color='b')
        plt.title(f'Calibration Plot - {wavelength}nm')
        plt.xlabel('Rotation mount angle in degrees (°)')
        plt.ylabel('Counts')
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(file_name, dpi=300)
        self.open_image(file_name)
        #plt.show()
        
    def plot_both(self, angles, intensities,  calibration_folder, date, wavelength):
        file_name = f"{calibration_folder}calibration_{date}_{wavelength}nm_plot.png"
        plt.figure(figsize=(10, 6))
        plt.plot(angles, intensities, label='Original', marker='o', linestyle='--')
        plt.xlabel('Angle (degrees)')
        plt.ylabel('Intensity')
        plt.title('Original vs Smoothed Intensity')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        
        plt.savefig(file_name, dpi=300)
        self.open_image(file_name)
        
    def open_image(self, file_path):
        if platform.system() == 'Darwin':       # macOS
            subprocess.call(('open', file_path))
        elif platform.system() == 'Windows':    # Windows
            os.startfile(file_path)
        elif platform.system() == 'Linux':      # Linux
            subprocess.call(('xdg-open', file_path))
            
    def plot_all(self, calibration_folder, date, wavelength):
        file_name = f"{calibration_folder}calibration_{date}_{wavelength}nm_plot.png"
        
        plt.figure(figsize=(10, 6))
        plt.plot(self.angles1, self.inten1, label='Original_10°', marker='o', linestyle='--')
        plt.plot(self.angles2, self.inten2, label='Smoothed_10°', marker='o', linestyle='--')
        plt.plot(self.angles3, self.inten3, label='Original_1°', marker='o', linestyle='--')
        plt.plot(self.angles4, self.inten4, label='Smoothed_1°', marker='o', linestyle='--')
        plt.xlabel('Angle (degrees)')
        plt.ylabel('Intensity')
        plt.title('Original and Smoothed Intensities')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        
        plt.savefig(file_name, dpi=300)
        self.open_image(file_name)