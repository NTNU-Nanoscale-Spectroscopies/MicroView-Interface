from datetime import *
import os
import re
import shutil
import subprocess
import sys
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
        
        # new: track the active sweep routine folder name (e.g. "SweepRoutine1")
        self.current_sweep_routine = None
        # new: mark whether current sweep routine has produced files
        self.current_sweep_has_data = False
        
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
            pass
        
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
        # If a sweep routine is active, place files under that container folder
        if self.current_sweep_routine:
            file_path = os.path.expanduser(f"{self.backup_directory}\\{self.current_sweep_routine}\\{file_name}\\")
            # mark that this sweep routine will receive data (caller will save files here)
            try:
                self.current_sweep_has_data = True
            except Exception:
                pass
        else:
            file_path = os.path.expanduser(f"{self.backup_directory}\\{file_name}\\")
        file_path += f"{spectro_name}\\"
        if not os.path.exists(file_path): os.makedirs(file_path)
        file_name += f"_#_$__{datetime.now():%Y%m%d}_@_{integration_time/1000}ms.txt"
        
        return f"{file_path}{file_name}"
    
    def get_calibration_directory(self, name=None):
        """Provides the full path to the calibration data backup location

        Notes
        ----------
        `#` is a placeholder for an index, 
        `@` is a placeholder for a time, 
        `__` is a placeholder to simplify the file name

        Parameters
        ----------
        spectro_name : `str`
            Spectrometer's name
        integration_time : `str`
            Spectrometer's integration time in microseconds
        name : `str`, optional
            Will be the name of the saved file

        Returns
        ---------
        get_calibration_directory : `str`
            Path to the calibration data backup location
        """
        folder_name = name or "Calibration"
        # include sweep routine container if set
        if self.current_sweep_routine:
            file_path = os.path.expanduser(f"{self.backup_directory}\\{self.current_sweep_routine}\\{folder_name}\\")
            # mark that this sweep routine will receive data (caller will save files here)
            try:
                self.current_sweep_has_data = True
            except Exception:
                pass
        else:
            file_path = os.path.expanduser(f"{self.backup_directory}\\{folder_name}\\")
        if not os.path.exists(file_path): os.makedirs(file_path)
        
        return f"{file_path}"
    
    def get_calibration_file_name(self, integration_time="", name=None):
        """Provides the full path to the calibration data backup location

        Notes
        ----------
        `#` is a placeholder for an index, 
        `@` is a placeholder for a time, 
        `__` is a placeholder to simplify the file name

        Parameters
        ----------
        spectro_name : `str`
            Spectrometer's name
        integration_time : `str`
            Spectrometer's integration time in microseconds
        name : `str`, optional
            Will be the name of the saved file

        Returns
        ---------
        get_calibration_directory : `str`
            Path to the calibration data backup location
        """

        file_name = f"Polarizer_£_#__$__@_{integration_time/1000}ms.txt"
        
        return f"{file_name}"
       
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
        """
        Updates the UI to reflect the new backup directory path.
        """
        self.directory_frame.set_backup_directory(self.backup_directory)
        self.app.title(f"MicroView - {self.backup_directory}")
    
    def update_username(self, username):
        """
        Updates the UI to reflect the selected username.

        Parameters:
        username : str
            The username to be displayed in the UI.
        """
        self.app.user_button.configure(text=username.upper())

    def open_backup_directory(self):
        """Open the current backup directory in the system file explorer.
           Uses existing FileSystem attributes (self.root, self.user, self.backup_directory)
           instead of defining any path inside the function.
        """

        # Prefer the user's root folder (root\<user>), fall back to the current backup path
        user_directory = os.path.join(self.root, self.user)
        try:
            path = os.path.expanduser(user_directory)
            if not os.path.exists(path):
                # fall back to the exact backup_directory (may include date/experiment)
                path = os.path.expanduser(self.backup_directory)
        except Exception as e:
            debugp("open_backup_directory", f"Invalid backup path: {e}")
            if getattr(self, "app", None):
                self.app.notification("Error", f"Invalid backup path", color="#8e0101")
            return
        # If path points to a file, use its directory
        if os.path.isfile(path):
            path = os.path.dirname(path)
 
         # Ensure directory exists
        try:
             os.makedirs(path, exist_ok=True)
        except Exception as e:
             debugp("open_backup_directory", f"Could not create directory: {e}")
             if getattr(self, "app", None):
                 self.app.notification("Error", f"Could not create folder: {e}", color="#8e0101")
             return
 
         # Open in system file explorer
        try:
             if sys.platform.startswith("win"):
                 os.startfile(path)
             elif sys.platform == "darwin":
                 subprocess.Popen(["open", path])
             else:
                 subprocess.Popen(["xdg-open", path])
        except Exception as e:
             debugp("open_backup_directory", f"Failed to open folder: {e}")
             if getattr(self, "app", None):
                 self.app.notification("Error", f"Failed to open folder: {e}", color="#8e0101")

    # new helper: start a new SweepRoutine folder and set it active
    def start_new_sweep_routine(self):
        """
        Create and set the next SweepRoutine folder inside the current experiment backup directory.
        Folder names: SweepRoutine1, SweepRoutine2, ...
        """
        base = self.backup_directory
        try:
            existing = []
            if os.path.exists(base) and os.path.isdir(base):
                for name in os.listdir(base):
                    if name.startswith("SweepRoutine"):
                        m = re.match(r"SweepRoutine(\d+)$", name)
                        if m:
                            existing.append(int(m.group(1)))
            next_idx = (max(existing) + 1) if existing else 1
            folder_name = f"SweepRoutine{next_idx}"
            folder_path = os.path.join(base, folder_name)
            os.makedirs(folder_path, exist_ok=True)
            self.current_sweep_routine = folder_name
            # reset has-data flag for the new routine
            self.current_sweep_has_data = False
            debugp("FileSystem", f"Started new sweep routine folder: {folder_name}")
            return folder_name
        except Exception as e:
            debugp("FileSystem", f"Failed to start SweepRoutine folder: {e}")
            return None

    # new helper: cleanup current sweep routine folder if no data was recorded
    def cleanup_current_sweep_routine(self):
        """
        If a sweep routine is active and no data files were recorded inside it,
        remove the SweepRoutineN folder (including empty subfolders). If files
        exist, leave it in place. Reset the current sweep markers in either case.
        """
        if not self.current_sweep_routine:
            return

        folder_path = os.path.join(self.backup_directory, self.current_sweep_routine)
        try:
            if not os.path.exists(folder_path):
                # nothing to do
                self.current_sweep_routine = None
                self.current_sweep_has_data = False
                return

            # If any real files exist anywhere under the folder -> keep it
            has_files = False
            for root, dirs, files in os.walk(folder_path):
                if files:
                    has_files = True
                    break

            if not has_files:
                # safe to remove entire tree (only empty dirs or no files)
                try:
                    shutil.rmtree(folder_path)
                    debugp("FileSystem", f"Removed empty sweep routine folder: {self.current_sweep_routine}")
                except Exception as e:
                    debugp("FileSystem", f"Failed to remove sweep routine folder: {e}")

            # Reset markers
            self.current_sweep_routine = None
            self.current_sweep_has_data = False

        except Exception as e:
            debugp("FileSystem", f"Error during cleanup_current_sweep_routine: {e}")
            # Ensure markers are cleared to allow future routines
            try:
                self.current_sweep_routine = None
                self.current_sweep_has_data = False
            except Exception:
                pass