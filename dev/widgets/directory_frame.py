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


    def get_spectrometer_directory(self, integration_time="", name=None):
        """Provides the full path to the spectrometer's data backup location

        Notes
        ----------
        `#` is a placeholder for an index, 
        `@` is a placeholder for a time, 
        `__` is a placeholder to simplify the file name

        Parameters
        ----------
        integration_time : `str`
            Spectrometer's integration time in microseconds
        name : `str`, optinal
            Will be the name of the saved file

        Returns
        ---------
        get_spectrometer_directory : `str`
            Path to the spectrometer's data backup location
        """
        file_name = name or self.spectrometer_backup_name.get() or "Spectrum"
        file_path = os.path.expanduser(f"{self.base_directory}/{str(date.today())}/{file_name}/")
        if not os.path.exists(file_path): os.makedirs(file_path)
        file_name += f"_#_$__{datetime.now():%Y%m%d}_@_{integration_time/1000}ms.txt"
        return f"{file_path}{file_name}"


    def get_available_iteration(self, file_path, index=1):
        """Finds the next available index to avoid duplicate files

        Notes
        ----------
        `#` is a placeholder for an index, 
        `@` is a placeholder for a time, 
        `__` is a placeholder to simplify the file name

        Parameters
        ----------
        file_path : `str`
            Path to the backup location
        index : `str`, optinal
            The starting index. 1 by default

        Returns
        ---------
        get_available_iteration : `int`
            The next available index
        """
        directory = os.path.dirname(file_path)
        base_name = f"{file_path.split('#_$__')[0]}"
        existing_files = os.listdir(directory)
        
        while any(f.startswith(f"{os.path.basename(base_name)}{index}") for f in existing_files):
            index += 1
        return index