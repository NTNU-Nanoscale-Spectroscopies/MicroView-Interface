import tkinter as tk 
import customtkinter as ctk
from PIL import Image, ImageTk
from img.images import *

class MicroscopeFrame(ctk.CTkFrame):
    def __init__(self, master, microscopes):
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(0, weight=1)
        self.microscopes = microscopes
        self.buttons = []

        for i, microscope in enumerate(self.microscopes):
            button = ctk.CTkButton(self, text=microscope.name, width=300, height=300, image=img_manager_01.get_image('microscope'), compound="top", font=("Arial", 20), text_color=["grey14","grey90"], command= lambda m=microscope: master.goToMicroscope(m))
            button.grid(row=0, column=i, padx=10, pady=10)
            self.grid_columnconfigure(i, weight=1)
            self.buttons.append(button)


class CameraFrame(ctk.CTkFrame):
    def __init__(self, master, camera):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.values = camera
        
        if not camera or not camera.connection():
            self.label = ctk.CTkLabel(self, text="Disconnected", font=("Arial", 25))
            self.label.grid(row=0, column=0, padx=5, pady=5)
            return
        
        self.canvas = tk.Canvas(self, width=300, height=200, bg='transparent')
        self.canvas.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.camera_widget = camera.run(self.canvas)

        self.button = ctk.CTkButton(self, text="Stop", width=60, command=camera.stop)
        self.button.grid(row=0, column=0, padx=5, pady=5, sticky="nw")

class SpectrometerFrame(ctk.CTkFrame):
    pass