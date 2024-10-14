import customtkinter as ctk
from dev.images.images import *
from datetime import date


class DirectoryFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure((0,1), weight=1)
        self.directory = "/Users/A068/Desktop/Data"

        self.label = ctk.CTkLabel(self, text="Camera backup name :", font=("Arial", 14))
        self.label.grid(row=0, column=0, padx=(20,0), pady=(20,5), sticky="sw")
        self.label = ctk.CTkLabel(self, text="Spectrometer backup name :", font=("Arial", 14))
        self.label.grid(row=1, column=0, padx=(20,0), pady=(5,20), sticky="w")

        self.camera_backup_name = ctk.CTkEntry(self, placeholder_text="Picture_1")
        self.camera_backup_name.grid(row=0, column=1, padx=(5,20), pady=(20,5), sticky="sew")
        self.spectrometer_backup_name = ctk.CTkEntry(self, placeholder_text="Spectrum_1_20241014_1000ns")
        self.spectrometer_backup_name.grid(row=1, column=1, padx=(5,20), pady=(5,20), sticky="ew")

        self.button = ctk.CTkButton(self, text="", corner_radius=50, width=15, image=img_info, fg_color="transparent")
        self.button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")


    def get_camera_directory(self):
        today = str(date.today())
        file_name = self.camera_backup_name.get()
        if not file_name: file_name = "Picture"

        i = 1
        file_path = os.path.expanduser(f"{self.directory}/{today}/Pictures/{file_name}_%s.png")
        while os.path.exists(file_path % i): i += 1

        return f"{self.directory}/{today}/Pictures/{file_name}_{str(i)}.png"


    def get_spectrometer_directory(self):
        integration_time = "1000ns"
        today = str(date.today())
        file_name = self.spectrometer_backup_name.get()
        if not file_name: file_name = "Spectrum"
        folder_name = file_name
        file_name += f"_{today.replace("-", "")}_"
        end_file_name = f"_{integration_time}.txt"

        i = 1
        file_path = os.path.expanduser(f"{self.directory}/{today}/{folder_name}/{file_name}%s{end_file_name}")
        while os.path.exists(file_path % i): i += 1

        return f"{self.directory}/{today}/{folder_name}/{file_name}{str(i)}{end_file_name}"



class QuickSetupFrame(ctk.CTkFrame):
    pass