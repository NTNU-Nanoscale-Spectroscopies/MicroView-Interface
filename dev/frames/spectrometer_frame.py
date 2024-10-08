from dev.images.images import *
import customtkinter as ctk
import numpy as np
import matplotlib.pyplot as plt
from seabreeze.spectrometers import Spectrometer
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import threading
import queue


class SpectrometerFrame(ctk.CTkFrame):
    def __init__(self, master, spectrometer):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)

        if not spectrometer:
            self.label = ctk.CTkLabel(self, text="No spectrometer", font=("Arial", 25))
            self.label.grid(row=4, column=0, padx=5, pady=5)
            return

        if not spectrometer.connection():
            self.label = ctk.CTkLabel(self, text="Disconnected", font=("Arial", 25))
            self.label.grid(row=4, column=0, padx=5, pady=5)
            self.button = ctk.CTkButton(self, text="", width=30, height=40,  image=img_retry, fg_color="transparent", command=spectrometer.connection)
            self.button.grid(row=4, column=0, padx=5, pady=(75, 0))
            return

        self.spectrometer = spectrometer
        self.is_running = False
        self.data_queue = queue.Queue()

        # self.label = ctk.CTkLabel(self, text="Acquisition time [us]:")
        # self.label.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        # self.acq_time_entry = ctk.CTkEntry(self)
        # self.acq_time_entry.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        self.fullscreen_button = ctk.CTkButton(self, text="", width=30, height=40, image=img_full_screen, fg_color="transparent")
        self.fullscreen_button.grid(row=0, column=0, padx=5, pady=(5,0), sticky="ne")
        self.play_button = ctk.CTkButton(self, text="", width=30, height=40,  image=img_play, fg_color="transparent", command=self.start_spectrometer)
        self.play_button.grid(row=0, column=0, padx=5, pady=(5,0), sticky="nw")
        self.pause_button = ctk.CTkButton(self, text="", width=30, height=40, image=img_pause, fg_color="transparent", command=self.stop_spectrometer)
        self.pause_button.grid(row=1, column=0, padx=5, pady=(5,0), sticky="nw")
        self.save_button = ctk.CTkButton(self, text="", width=30, height=40, image=img_save, fg_color="transparent")
        self.save_button.grid(row=2, column=0, padx=5, pady=(5,0), sticky="nw")
        self.rescale_button = ctk.CTkButton(self, text="", width=30, height=40, image=img_rescale, fg_color="transparent")
        self.rescale_button.grid(row=3, column=0, padx=5, pady=(5,0), sticky="nw")

        self.figure, self.plot1 = plt.subplots(figsize=(6, 4), dpi=100)
        self.canvas = FigureCanvasTkAgg(self.figure, master=self)
        self.canvas.get_tk_widget().grid(row=1, column=0, columnspan=3, sticky="nsew")
        # self.toolbar = NavigationToolbar2Tk(self.canvas, self)
        # self.toolbar.update()

    def start_spectrometer(self):
        if not self.is_running:
            self.is_running = True
            threading.Thread(target=self.acquire_data).start()

    def stop_spectrometer(self):
        self.is_running = False
        print("Stop")

    def acquire_data(self):
        self.plot1.clear()
        try:
            time = 100000 #int(self.acq_time_entry.get())
            self.spectrometer.set_integration_time(time)
            while self.is_running:
                wavelengths, intensities = self.spectrometer.get_spectrum()
                self.data_queue.put((wavelengths, intensities))
                self.update_graph()
                #self.stop_spectrometer()
        except Exception as e:
            print(f"Error in acquisition: {e}")

    def update_graph(self):
        if not self.data_queue.empty():
            wavelengths, intensities = self.data_queue.get()
            self.plot1.clear()
            self.plot1.plot(wavelengths, intensities)
            self.plot1.set_xlabel('Wavelength [nm]')
            self.plot1.set_ylabel('Intensity [counts]')
            self.canvas.draw()


