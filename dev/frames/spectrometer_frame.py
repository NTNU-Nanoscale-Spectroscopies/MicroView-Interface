from dev.images.images import *
import customtkinter as ctk
import numpy as np
import matplotlib.pyplot as plt
from seabreeze.spectrometers import Spectrometer
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import tkinter
import csv


class SpectrometerFrame(ctk.CTkFrame):
    def __init__(self, master, spectrometer):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        if not spectrometer:
            self.label = ctk.CTkLabel(self, text="No spectrometer", font=("Arial", 25))
            self.label.grid(row=4, column=0, padx=5, pady=5)
            return

        self.disconnected_label = ctk.CTkLabel(self, text="Disconnected", font=("Arial", 25))
        self.disconnected_label.grid(row=4, column=0, padx=5, pady=5)
        self.disconnected_button = ctk.CTkButton(self, text="", width=30, height=40,  image=img_retry, fg_color="transparent", command=self.try_connection)
        self.disconnected_button.grid(row=4, column=0, padx=5, pady=(75, 0))

        self.wavelengths = None
        self.intensities = None
        self.spectrometer = spectrometer
        self.try_connection()


    def try_connection(self):
        if self.spectrometer.connect():
            self.disconnected_label.grid_forget()
            self.disconnected_button.grid_forget()

            self.data_queue = None
            self.spectrometer.set_integration_time(100000)

            self.figure, self.plot1 = plt.subplots(figsize=(6, 4), dpi=100)
            self.canvas = FigureCanvasTkAgg(self.figure, master=self)
            self.canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew")
            toolbar_frame = tkinter.Frame(self)
            toolbar_frame.grid(row=1, sticky="new")
            self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
            self.toolbar.update()

            self.fullscreen_button = ctk.CTkButton(self, text="", width=30, height=40, image=img_full_screen, fg_color="transparent")
            self.fullscreen_button.grid(row=0, column=0, padx=5, pady=5, sticky="ne")
            self.play_button = ctk.CTkButton(self, text="", width=30, height=40,  image=img_play, fg_color="transparent", command=self.start_spectrometer)
            self.play_button.grid(row=0, column=0, padx=5, pady=5, sticky="nw")
            self.pause_button = ctk.CTkButton(self, text="", width=30, height=40, image=img_pause, fg_color="transparent", command=self.stop_spectrometer)
            self.pause_button.grid(row=0, column=0, padx=(50,0), pady=5, sticky="nw")
            self.save_button = ctk.CTkButton(self, text="", width=30, height=40, image=img_save, fg_color="transparent", command=self.save_data)
            self.save_button.grid(row=0, column=0, padx=(95,0), pady=5, sticky="nw")

            if self.spectrometer.enable:
                self.start_spectrometer()


    def start_spectrometer(self):
        self.spectrometer.start()
        self.update_graph()


    def stop_spectrometer(self):
        self.spectrometer.stop()


    def update_graph(self):
        if self.spectrometer.is_running and not self.spectrometer.data_queue.empty():
            self.wavelengths, self.intensities = self.spectrometer.data_queue.get()
            self.plot1.clear()
            self.plot1.plot(self.wavelengths, self.intensities)
            self.plot1.set_xlabel('Wavelength [nm]')
            self.plot1.set_ylabel('Intensity [counts]')
            self.canvas.draw()
            self.after(20, self.update_graph)
        elif self.spectrometer.is_running and self.spectrometer.data_queue.empty():
            self.after(100, self.update_graph)

    def save_data(self):
        if self.wavelengths is not None and self.intensities is not None:
            file_path = self.master.directory_frame.get_spectrometer_directory()
            if file_path:
                try:
                    with open(file_path, mode='w', newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow(['Wavelength [nm]', 'Intensity [counts]'])
                        writer.writerows(zip(self.wavelengths, self.intensities))
                    print(f"Data saved successfully to {file_path}")
                except Exception as e:
                    print(f"Error saving data: {e}")