
from datetime import *
import os
import re
from dev.debugHelp import debugp


class FileSystem():
    
    def __init__(self, app, backup_directory, directory_frame):
        
        self.spectrometer_data_path = ""
        self.camera_data_path = ""
        self.backup_directory = backup_directory + f"\\{datetime.now():%Y-%m-%d}"
        self.directory_frame = directory_frame
        self.app = app
        self.root = os.path.dirname(backup_directory)
        self.user = os.path.basename(backup_directory)
        
        self.new_spectrometer_experiment()
    
    def change_user(self, username):
        """Sets directory path to selected user"""
        
        self.backup_directory = f"{self.root}\\{username}\\{datetime.now():%Y-%m-%d}"
        self.user = username
        
        self.new_spectrometer_experiment()
        
        self.update()
        self.update_username(username)
        
    def go_to_user_root(self):
        """Sets directory path to root"""
        self.backup_directory = self.root
        
    def new_spectrometer_experiment(self):
        """Sets directory path to new experiment"""
        self.backup_directory = f"{self.root}\\{self.user}\\{datetime.now():%Y-%m-%d}\\Experiment_{self.get_next_experiment()}"
        self.update()
        self.update_username(self.user)
        
    def get_next_experiment(self):
        """Gets the next experiment index"""
        path = f"{self.root}\\{self.user}\\{datetime.now():%Y-%m-%d}"
        max_number = 0
        pattern = re.compile(r'Experiment_(\d+)')

        try:
            for folder in os.listdir(path):
                match = pattern.match(folder)
                if match:
                    max_number = max(max_number, int(match.group(1)))
        except FileNotFoundError:
            print(f"Error: The path '{path}' does not exist.")
        
        return max_number + 1
        
    def get_backup_directory(self):
        """Gets the current backup path"""
        return self.backup_directory
    
    def set_backup_directory(self, backup_directory):
        """Sets the backup directory path"""
        self.backup_directory = backup_directory
        
        user = os.path.basename(self.backup_directory)
        parts = backup_directory.split(os.sep)
        if "Data" in parts:
            ind = parts.index("Data") + 1
            if len(parts) > ind:
                user = parts[ind]

        self.update()
        self.update_username(user)
        
    def get_user_names(self):
        """Gets the available known users"""
        parent_directory = self.root
        if os.path.exists(parent_directory) and os.path.isdir(parent_directory):
            return [d for d in os.listdir(parent_directory) if os.path.isdir(os.path.join(parent_directory, d))]
        else:
            return []
        
    def get_spectrometer_directory(self, integration_time="",spectro_name="", name=None):
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
        file_name = name or self.directory_frame.spectrometer_backup_name.get() or "Spectrum"
        file_path = os.path.expanduser(f"{self.backup_directory}\\{file_name}\\")
        file_path += f"{spectro_name}\\"
        if not os.path.exists(file_path): os.makedirs(file_path)
        file_name += f"_#_$__{datetime.now():%Y%m%d}_@_{integration_time/1000}ms.txt"
        
        return f"{file_path}{file_name}"

       
    def get_max_spectrum_number(self):
        """Finds the next available index Spectrum folder to avoid duplicate files
            Simultaneously save files have the same index
            
            Parameters
            ----------
            root_folder : `str`
                Path to the root backup location
        """
        max_number = 0
        pattern = re.compile(r"Spectrum_(\d+)_")  # Regex
        root_folder = self.backup_directory
        root_folder += f"\\Spectrum"

        try :
            for folder in os.listdir(root_folder):
                folder_path = os.path.join(root_folder, folder)
                if os.path.isdir(folder_path):
                    for file in os.listdir(folder_path):
                        match = pattern.search(file)
                        if match:
                            number = int(match.group(1))
                            max_number = max(max_number, number)
        except :
            return 0

        return max_number + 1
     
    def update(self):
        self.directory_frame.set_backup_directory(self.backup_directory)
        self.app.title(f"MicroView - {self.backup_directory}")
    
    def update_username(self, username):
        self.app.user_button.configure(text=username.upper())