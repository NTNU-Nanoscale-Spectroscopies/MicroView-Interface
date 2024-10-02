import customtkinter as ctk 
from images import *

class MicroscopeFrame(ctk.CTkFrame):
    def __init__(self, master, values):
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(0, weight=1)
        self.values = values
        self.buttons = []

        for i, value in enumerate(self.values):
            button = ctk.CTkButton(self, text=value, width=300, height=300, image=img_manager_01.get_image('microscope'), compound="top", font=("Arial", 20), text_color=["grey14","grey90"])
            button.grid(row=0, column=i, padx=10, pady=10)
            self.grid_columnconfigure(i, weight=1)
            self.buttons.append(button)

