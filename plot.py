import numpy as np
import matplotlib.pyplot as plt

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
