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


# Example usage:
#plot_3d_spectra(r"C:\Users\A068\Documents\Data\Default\2025-05-12\Experiment_6\Calibration", 347, 932)
