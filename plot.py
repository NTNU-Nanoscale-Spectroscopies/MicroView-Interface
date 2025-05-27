import numpy as np
import matplotlib.pyplot as plt
import os
from mpl_toolkits.mplot3d import Axes3D

# Data
def plot_data(data):
    # Plotting
    plt.figure(figsize=(10, 6))
    plt.plot(data[:, 0], data[:, 1], marker='o', linestyle='-', color='b')
    plt.title('Plot of the Given Data')
    plt.xlabel('X-axis')
    plt.ylabel('Y-axis')
    plt.grid(True)
    plt.show()




def read_spectrum_file(filepath):
    with open(filepath, 'r') as f:
        lines = f.readlines()
    start_index = next(i for i, line in enumerate(lines) if '>>>>>Begin Spectral Data<<<<<' in line) + 1
    data = [list(map(float, line.strip().split(','))) for line in lines[start_index:]]
    return np.array(data)

def plot_3d_spectra(folder_path, wavelength_min=None, wavelength_max=None):
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection='3d')

    files = sorted([f for f in os.listdir(folder_path) if f.endswith('.txt')])
    for i, filename in enumerate(files):
        filepath = os.path.join(folder_path, filename)
        data = read_spectrum_file(filepath)

        # Filter wavelengths
        wavelengths = data[:, 0]
        intensities = data[:, 1]
        if wavelength_min is not None and wavelength_max is not None:
            mask = (wavelengths >= wavelength_min) & (wavelengths <= wavelength_max)
            wavelengths = wavelengths[mask]
            intensities = intensities[mask]

        z = np.full_like(wavelengths, i)
        ax.plot(wavelengths, z, intensities, label=filename)

    ax.set_xlabel('Wavelength [nm]')
    ax.set_ylabel('File Index')
    ax.set_zlabel('Intensity [counts]')
    ax.set_title('3D Spectral Layers')
    plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    plt.tight_layout()
    plt.show()







def extract_intensity_at_650nm(filepath, target_wavelength=650.0, tolerance=1.0):
    with open(filepath, 'r') as file:
        lines = file.readlines()

    # Find where spectral data starts
    start_index = None
    for i, line in enumerate(lines):
        if '>>>>>Begin Spectral Data<<<<<' in line:
            start_index = i + 1
            break

    if start_index is None:
        return None

    closest_diff = float('inf')
    closest_intensity = None

    for line in lines[start_index:]:
        try:
            wavelength, intensity = map(float, line.strip().split(','))
            diff = abs(wavelength - target_wavelength)
            if diff < closest_diff and diff <= tolerance:
                closest_diff = diff
                closest_intensity = intensity
        except:
            continue

    return closest_intensity

def plot_intensity_curve(folder_path):
    files = sorted([f for f in os.listdir(folder_path) if f.endswith('.txt') or f.endswith('.csv')])
    intensities = []
    labels = []

    for file in files:
        path = os.path.join(folder_path, file)
        intensity = extract_intensity_at_650nm(path)
        if intensity is not None:
            labels.append(file)
            intensities.append(intensity)
        else:
            print(f"Warning: No valid 650 nm data found in {file}")

    # Plot as connected dots
    plt.figure(figsize=(12, 6))
    plt.plot(intensities, marker='o', linestyle='-', color='darkorange')
    #plt.xticks(ticks=range(len(labels)), labels=labels, rotation=45, ha='right')
    plt.title('Intensity at ~650 nm Across Files')
    plt.xlabel('File Index')
    plt.ylabel('Intensity at ~650 nm')
    plt.grid(True)
    plt.tight_layout()
    plt.show()



def plot_all_intensity_curve(folder_path):
    
    experiment_folders = sorted([
        f for f in os.listdir(folder_path)
        if os.path.isdir(os.path.join(folder_path, f)) and f.lower().startswith("experiment")
    ])

    plt.figure(figsize=(12, 6))  # Only one figure for all plots

    for experiment in experiment_folders:
        calibration_path = os.path.join(folder_path, experiment, "Calibration")
        if not os.path.isdir(calibration_path):
            print(f"Calibration folder not found for {experiment}. Skipping.")
            continue

        files = sorted([
            f for f in os.listdir(calibration_path)
            if f.endswith('.txt') or f.endswith('.csv')
        ])

        intensities = []
        labels = []

        for file in files:
            path = os.path.join(calibration_path, file)
            intensity = extract_intensity_at_650nm(path)
            if intensity is not None:
                labels.append(file)
                intensities.append(intensity)
            else:
                print(f"Warning: No valid 650 nm data found in {file}")

        if intensities:
            plt.plot(intensities, marker='o', linestyle='-', label=experiment)

    # Global plot settings
    plt.title('Intensity at ~650 nm Across Experiments')
    plt.xlabel('File Index')
    plt.ylabel('Intensity at ~650 nm')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

#Plot one folder
#plot_intensity_curve(r"C:\Users\olive\OneDrive\Bureau\2025-05-12\Experiment_10\Calibration")

#Plot all folders
#plot_all_intensity_curve(r"C:\Users\olive\OneDrive\Bureau\2025-05-12")

#Plot on folder in 3D
#plot_3d_spectra(r"C:\Users\olive\OneDrive\Bureau\2025-05-12\Experiment_10\Calibration", 649, 651)
