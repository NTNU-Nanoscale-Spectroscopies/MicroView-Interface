from ..images.images import *
from datetime import *


class DirectoryFrame(CTkFrame):
    def __init__(self, master):
        super().__init__(master, height=10)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure((0,1), weight=1)
        self.grid_propagate(False)
        self.base_directory = "/Users/A068/Desktop/Data"

        self.label = CTkLabel(self, text="Camera backup name :", font=("Arial", 14))
        self.label.grid(row=0, column=0, padx=(20,0), pady=(20,5), sticky="sw")
        self.label = CTkLabel(self, text="Spectrometer backup name :", font=("Arial", 14))
        self.label.grid(row=1, column=0, padx=(20,0), pady=(5,20), sticky="w")

        self.camera_backup_name = CTkEntry(self, placeholder_text="Picture_1")
        self.camera_backup_name.grid(row=0, column=1, padx=(5,20), pady=(20,5), sticky="sew")
        self.spectrometer_backup_name = CTkEntry(self, placeholder_text="Spectrum_1_20241014_1000ns")
        self.spectrometer_backup_name.grid(row=1, column=1, padx=(5,20), pady=(5,20), sticky="ew")

        self.button = CTkButton(self, text="", corner_radius=50, width=15, image=img_info, fg_color="transparent")
        self.button.grid(row=0, column=1, padx=5, pady=5, sticky="ne")

        self.get_camera_directory(update_placeholder=True)
        self.get_spectrometer_directory(update_placeholder=True)


    def get_camera_directory(self, update_placeholder=False):
        file_name = self.camera_backup_name.get() or "Picture"
        file_path = os.path.expanduser(f"{self.base_directory}/{str(date.today())}/Pictures/")
        if not os.path.exists(file_path) and not update_placeholder: os.makedirs(file_path)
        file_name += f"_{datetime.now():%H.%M.%S}.png"
        self.camera_backup_name.configure(placeholder_text=file_name)
        return f"{file_path}{file_name}"


    def get_spectrometer_directory(self, integration_time="", update_placeholder=False):
        file_name = self.spectrometer_backup_name.get() or "Spectrum"
        file_path = os.path.expanduser(f"{self.base_directory}/{str(date.today())}/{file_name}/")
        if not os.path.exists(file_path) and not update_placeholder: os.makedirs(file_path)
        file_name += f"_{datetime.now():%Y%m%d_%H.%M.%S}_{integration_time}μs.txt"
        self.spectrometer_backup_name.configure(placeholder_text=file_name)
        return f"{file_path}{file_name}"