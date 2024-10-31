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

        time = f"{datetime.now():%Y%m%d_%H.%M.%S}"
        self.camera_backup_name = CTkEntry(self, placeholder_text=f"Picture_{time}")
        self.camera_backup_name.grid(row=0, column=1, padx=(5,20), pady=(20,5), sticky="sew")
        self.spectrometer_backup_name = CTkEntry(self, placeholder_text=f"Spectrum_{time}_100ms")
        self.spectrometer_backup_name.grid(row=1, column=1, padx=(5,20), pady=(5,20), sticky="ew")


    def get_camera_directory(self):
        file_name = self.camera_backup_name.get() or "Picture"
        file_path = os.path.expanduser(f"{self.base_directory}/{str(date.today())}/Pictures/")
        if not os.path.exists(file_path): os.makedirs(file_path)
        file_name += f"_{datetime.now():%Y%m%d_%H.%M.%S}.png"
        return f"{file_path}{file_name}"


    def get_spectrometer_directory(self, integration_time=""):
        file_name = self.spectrometer_backup_name.get() or "Spectrum"
        file_path = os.path.expanduser(f"{self.base_directory}/{str(date.today())}/{file_name}/")
        if not os.path.exists(file_path): os.makedirs(file_path)
        file_name += f"_{datetime.now():%Y%m%d_%H.%M.%S}_{integration_time/1000}ms.txt"
        return f"{file_path}{file_name}"