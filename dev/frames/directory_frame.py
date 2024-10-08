import customtkinter as ctk
from dev.images.images import *


class DirectoryFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure((0,1,2), weight=1)
        self.label = ctk.CTkLabel(self, text="Choose a directory :", font=("Arial", 14))
        self.label.grid(row=0, column=0, padx=(20,0), pady=(20,5), sticky="w")
        self.label = ctk.CTkLabel(self, text="Camera backup name :", font=("Arial", 14))
        self.label.grid(row=1, column=0, padx=(20,0), pady=5, sticky="w")
        self.label = ctk.CTkLabel(self, text="Spectrometer backup name :", font=("Arial", 14))
        self.label.grid(row=2, column=0, padx=(20,0), pady=(5,20), sticky="w")
        
        self.label = ctk.CTkLabel(self, text="_n°", font=("Arial", 14), text_color="grey50")
        self.label.grid(row=1, column=2, padx=(0,20), pady=5, sticky="w")
        self.label = ctk.CTkLabel(self, text="_n°_date_integrationTime", font=("Arial", 14), text_color="grey50")
        self.label.grid(row=2, column=2, padx=(0,20), pady=(5,20), sticky="w")
        
        self.entry = ctk.CTkEntry(self, fg_color="#EEEEEE", border_color="#00509E", border_width=1)
        self.entry.grid(row=0, column=1, padx=(5,20), pady=(20,5), sticky="ew", columnspan=2)
        self.entry = ctk.CTkEntry(self, fg_color="#EEEEEE", border_color="#00509E", border_width=1)
        self.entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.entry = ctk.CTkEntry(self, fg_color="#EEEEEE", border_color="#00509E", border_width=1)
        self.entry.grid(row=2, column=1, padx=5, pady=(5,20), sticky="ew")



class QuickSetupFrame(ctk.CTkFrame):
    pass