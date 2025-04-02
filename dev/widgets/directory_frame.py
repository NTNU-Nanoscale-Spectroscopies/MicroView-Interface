import re
from ..images.images import *
from datetime import *


class DirectoryFrame(CTkFrame):
    """Class for creating a frame for saving camera and spectrometer files"""

    def __init__(self, master, backup_directory):
        """Create a frame in the main window.
        Users can easily choose camera and spectrometer save files name

        Parameters
        ------------
        master : `CTk`
            Main window
        backup_directory : `str`
            Root directory where backups will be made
        """
        super().__init__(master, height=10)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure((0,1), weight=1)
        self.grid_propagate(False)
        self.base_directory = backup_directory

        self.label = CTkLabel(self, text="Camera save file name :", font=("Arial", 14))
        self.label.grid(row=0, column=0, padx=(20,0), pady=(20,5), sticky="sw")
        self.label = CTkLabel(self, text="Spectrometer save file name :", font=("Arial", 14))
        self.label.grid(row=1, column=0, padx=(20,0), pady=(5,20), sticky="w")

        time = f"{datetime.now():%Y%m%d_%H.%M.%S}"
        self.camera_backup_name = CTkEntry(self, placeholder_text=f"Picture_{time}")
        self.camera_backup_name.grid(row=0, column=1, padx=(5,20), pady=(20,5), sticky="sew")
        self.spectrometer_backup_name = CTkEntry(self, placeholder_text=f"Spectrum_{time}_100.0ms")
        self.spectrometer_backup_name.grid(row=1, column=1, padx=(5,20), pady=(5,20), sticky="ew")


    def get_camera_directory(self):
        """Provides the full path to the camera's image backup location

        Notes
        ----------
        `#` is a placeholder for an index, 
        `@` is a placeholder for a time, 
        `__` is a placeholder to simplify the file name

        Returns
        ---------
        get_camera_directory : `str`
            Path to the camera's image backup location
        """
        file_name = self.camera_backup_name.get() or "Picture"
        file_path = os.path.expanduser(f"{self.base_directory}/{str(date.today())}/Pictures/")
        if not os.path.exists(file_path): os.makedirs(file_path)
        file_name += f"_{datetime.now():%Y%m%d_%H.%M.%S}.png"
        return f"{file_path}{file_name}"

    def set_backup_directory(self, path):
        """Sets backup directory to new path
        Parameters
        ------------
        path : `string`
            new path to backup directory
        """
        self.base_directory = path