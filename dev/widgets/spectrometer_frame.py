from dev.debugHelp import debugp
from ..images.images import *
from .notification import *

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from datetime import *
import threading
import numpy
import time
import csv
from copy import deepcopy

class SpectrometerFrame(CTkFrame):
    """Class for creating a frame to control a spectrometer"""

    def __init__(self, master, spectrometers):
        """Create a frame in the main window.
        Users can easily control the spectrometer

        Parameters
        ------------
        master : `CTk`
            Main window
        spectrometer : `MySpectrometer`
            Object containing all information about a spectrometer
        """
        super().__init__(master)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(4, weight=1)
        self.grid_propagate(False)
        
        self.spectrometer_count = len(spectrometers)

        if not spectrometers:
            self.label = CTkLabel(self, text="No spectrometer", font=("Arial", 25))
            self.label.grid(row=3, column=1, padx=5, pady=5)
        else:
            self.spectrometers = spectrometers
            #self.spectrometer = spectrometers[0]
            self.init()


    def init(self):
        """Creating the initial spectrometer display
        """
        self.disconnected_label = CTkLabel(self, text="Disconnected", font=("Arial", 25))
        self.disconnected_label.grid(row=4, column=1, padx=5, pady=5)
        self.disconnected_button = CTkButton(self, text="", width=30, height=40,  image=img_retry, fg_color="transparent", command=self.reconnection)
        self.disconnected_button.grid(row=4, column=1, padx=5, pady=(75, 0))

        self.popup = None
        self.backup_name = None
        self.stop_after_saves = False
        self.reflectance_mode = False
        self.save_frequency = 1
        self.backups_counts_memorie = 10
        self.wavelengthsList, self.intensitiesList = [], []
        self.light_reference, self.dark_reference = [], []
        self.light_ref_acquisition_time, self.dark_ref_acquisition_time = [], []
        self.connected_spectrometers = []
        self.graph_updating = False
        
        
        self.light_reference_wavelengths, self.light_reference_intensities = [], []
        self.dark_reference_wavelengths, self.dark_reference_intensities = [], []
        
        """
        self.light_reference_wavelengths, self.light_reference_intensities = None, None
        self.dark_reference_wavelengths, self.dark_reference_intensities = None, None
        """
        
        self.split = 1
    
    def connect(self, device):
        """Try connecting the spectrometers. 
        If the connection is established, the frame is updated to access the associated functionality.
        In addition, if the device enable parameter is activated, the device is automatically started

        Returns
        ------------
        connect : `bool`
            Wether the spectrometer is connected
        """
        
        debugp("spec", "Connecting spectrometer : " + str(device))
        
        if not device.connected and device.connect() == True:
            self.connected_spectrometers.append(device)
            self.wavelengthsList.append([])
            self.intensitiesList.append([])
            self.light_ref_acquisition_time.append([])
            self.dark_ref_acquisition_time.append([])
            self.light_reference_wavelengths.append([])
            self.dark_reference_wavelengths.append([])
            self.light_reference_intensities.append([])
            self.dark_reference_intensities.append([])
            debugp("spec", "Connected spectrometer successfully : " + str(device))        
                       
        connected_spectrometers_count = len(self.connected_spectrometers)
        
        #Testing or simulate_spectrometer_connected > 0   
        if connected_spectrometers_count > 0:
            debugp("spec", "Updating Spectrometer Display")

            self.disconnected_label.grid_forget()
            self.disconnected_button.grid_forget()
            
            # #or ?
            # self.disconnected_label.destroy()
            # self.disconnected_button.destroy()
   
            for spec in self.spectrometers:
                spec.set_integration_time(spec.integration_time)           
            self.figure = Figure(figsize=(6, 6))
            
            #If 1 or 2 spectrometers are detected initialise the plots
            # self.plot1 = self.figure.add_subplot(101 + connected_spectrometers_count * 10)
            # self.plot1.set_title(self.connected_spectrometers[0].name, loc="right")
            # self.plot1.set_visible(False)#
            # if connected_spectrometers_count == 2:
            #     self.plot2 = self.figure.add_subplot(122)
            #     self.plot2.set_title(self.connected_spectrometers[1].name, loc="right")
            #     self.plot2.set_visible(False)#
    
            self.plot3 = self.figure.add_subplot(111)
            self.plot3.set_visible(True)
        
            self.canvas = FigureCanvasTkAgg(self.figure, master=self)
            self.canvas.get_tk_widget().grid(row=0, column=1, sticky="nsew", rowspan=5)
            toolbar_frame = CTkFrame(self)
            toolbar_frame.grid(row=0, column=1, sticky="new")
            self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
            self.toolbar.update()
   
            self.fullscreen_button = CTkButton(self, text="", width=40, height=40, image=img_full_screen, fg_color="transparent", command=self.extend)
            self.fullscreen_button.grid(row=0, column=2, padx=5, pady=5, sticky="ne")
            self.import_button = CTkButton(self, text="", width=40, height=40, image=img_plus, fg_color="transparent", command=self.import_chart)
            self.import_button.grid(row=1, column=2, padx=5, pady=5, sticky="ne")
            self.light_reference_button = CTkButton(self, text="", width=40, height=40, image=img_bulb_on, fg_color="transparent", command=self.set_light_reference)
            self.light_reference_button.grid(row=2, column=2, padx=5, pady=5, sticky="ne")
            self.dark_reference_button = CTkButton(self, text="", width=40, height=40, image=img_bulb_off, fg_color="transparent", command=self.set_dark_reference)
            self.dark_reference_button.grid(row=3, column=2, padx=5, pady=5, sticky="ne")
            self.pause_button = CTkButton(self, text="", width=40, height=40, image=img_pause, fg_color="transparent", command=self.stop_spectrometer)
            self.pause_button.grid(row=0, column=0, padx=5, pady=5, sticky="nw")
            self.play_button = CTkButton(self, text="", width=40, height=40,  image=img_play, fg_color="transparent", command=self.start_spectrometer)
            self.play_button.grid(row=0, column=0, padx=5, pady=5, sticky="nw")
            self.save_button = CTkButton(self, text="", width=40, height=40, image=img_save, fg_color="transparent", command=self.save_data)
            self.save_button.grid(row=1, column=0, padx=5, pady=5, sticky="nw")
            self.save_button = CTkButton(self, text="", width=40, height=40, image=img_advanced_save, fg_color="transparent", command=self.advanced_save_popup)
            self.save_button.grid(row=2, column=0, padx=5, pady=5, sticky="nw")
            self.reflectance_data_button = CTkButton(self, text="%", font=("Arial", 25), width=40, height=40, fg_color="transparent", command=self.toggle_mode)
            self.reflectance_data_button.grid(row=3, column=0, padx=5, pady=5, sticky="nw")
            self.raw_data_button = CTkButton(self, text="#", font=("Arial", 25), width=40, height=40, fg_color="transparent", command=self.toggle_mode)
            self.raw_data_button.grid(row=3, column=0, padx=5, pady=5, sticky="nw")
        
        
            if connected_spectrometers_count > 1:  
                self.view_button = CTkButton(self, text="", width=40, height=40, image=img_split_left, fg_color="transparent", command=self.toggle_split_screen)
                self.view_button.grid(row=4, column=0, padx=5, pady=5, sticky="nw")
                
            self.start_spectrometer(device)
            
        return (connected_spectrometers_count > 0)


    def reconnection(self):
        """Try reconnecting the spectrometer via `setup frame` to update the display correctly
        """
        self.master.quick_setup_frame.reconnection(self.spectrometers[0])

    
    def disconnect(self, device):
        """Stops the current thread, disconnects the spectrometer cleanly, then updates the display
        """
         
        #Remove spectrometer from connected
        self.connected_spectrometers.remove(device)
        device.disconnect()

        self.split = 1
        
        if hasattr(self, 'view_button'):
            self.view_button.destroy()
        
        if(len(self.connected_spectrometers) == 0):
            self.figure.clf() 
            for widget in self.winfo_children():
                widget.destroy()
            self.init()
            self.on_closing()
            

    def start_spectrometer(self, device=None):
        """Starts thread for continuous spectrometer data extraction
        """
        #TODO When play button clicked have to play all spectrometers.
        
        #print("--- Starting spectrometer")
        # for spec in self.connected_spectrometers:
        #     #print("Starting spec :", spec)
        #     spec.start()
        
        if device in self.connected_spectrometers:
            debugp("spec", "Starting spectrometer : " + str(device))
            device.start()
        else:
            for spec in self.connected_spectrometers:
                debugp("spec", "Starting spectrometer : " + str(spec))
                spec.start()
    
        self.pause_button.lift()
        self.update_graph(True)


    def stop_spectrometer(self):
        """Stops continuous extraction of spectrometer data without disconnecting the camera
        """
            
        for spec in self.connected_spectrometers:
            debugp("spec", "Stopping spectrometer : " + str(spec))
            spec.stop()

        self.play_button.lift()


    def toggle_mode(self):
        """Switches between spectrometer data display modes. 
        The main mode is raw data display. However, if the ligth reference 
        and dark reference have been taken, it is possible to switch to reflectance/transmittance mode. 
        Otherwise, a notification is displayed to users.
        """
        if self.reflectance_mode:
            self.reflectance_mode = False
            self.raw_data_button.lift()
        else:
            if not self.light_reference or not self.dark_reference:
                self.notification(f"To use reflectance or transmittance, you need both light and dark references", color="#8e0101")
                return
            self.reflectance_mode = True
            self.reflectance_data_button.lift()
            if self.light_ref_acquisition_time[self.split-1] != self.dark_ref_acquisition_time[self.split-1]:
                self.notification(f"Light reference acquisition time differs from dark", color="#e17e00")              
            if self.light_ref_acquisition_time[self.split-1] != self.connected_spectrometers[self.split-1].integration_time:
                self.notification(f"Light reference acquisition time differs from current", color="#e17e00")              
            if self.dark_ref_acquisition_time[self.split-1] != self.connected_spectrometers[self.split-1].integration_time:
                self.notification(f"Dark reference acquisition time differs from current", color="#e17e00")              


    def update_plot(self, spectrometer, plot, index):
        """Updates the plot of a spectrometer with raw data, 
        or calculates reflectance/transmittance if this mode is enabled.
        """
        if spectrometer.is_running :
            if not spectrometer.chart_queue.empty() :
                
                local_wavelengths, local_intensities = spectrometer.chart_queue.get()
                
                if len(self.wavelengthsList) >= index + 1 and len(self.intensitiesList) >= index + 1:
                    self.wavelengthsList[index] = local_wavelengths
                    self.intensitiesList[index] = local_intensities
                    
                plot.clear()
                
                if self.reflectance_mode:

                    denominator = self.light_reference_intensities[index] - self.dark_reference_intensities[index]
                    denominator = numpy.where(denominator == 0, numpy.nan, denominator)
                                        
                    self.reflectance_intensities = (self.intensitiesList[index] - self.dark_reference_intensities[index]) / denominator * 100
                    
                    #TODO : Should we have multiple reflectance intensities ? Yes
                    #intensities = self.reflectance_intensities
                    intensities = self.reflectance_intensities
                    
                    plot.set_ylabel('Relative intensity [%]')
                    plot.set_ylim(-20, 180)
                else:
                    #intensities = self.intensities
                    intensities = self.intensitiesList[index]
                    plot.set_ylabel('Intensity [counts]')
                
                plot.plot(self.wavelengthsList[index], intensities)
                plot.set_xlabel('Wavelength [nm]')
                plot.set_title(spectrometer.name, loc="right")
                plot.grid()


    #TODO Test here
    def update_graph(self, first_launch):
        """Updates the graph (all plots) every 20ms.
        """
        
        if first_launch and not self.graph_updating:
            debugp("spec", "First time updating graph")
            self.graph_updating = True

        elif first_launch:
            debugp("spec", "Aborted updating graph")
            return
        
        if len(self.connected_spectrometers) == 1:
            spec = self.connected_spectrometers[0]
            if spec.is_running and not spec.chart_queue.empty():
                self.update_plot(spec, self.plot3, 0)  

                #If image has been plotted
                if spec.chart_queue.empty():
                    self.canvas.draw()
                    
        elif len(self.connected_spectrometers) > 1:
            spec = self.connected_spectrometers[self.split-1]
            if spec.is_running and not spec.chart_queue.empty():
                self.update_plot(spec, self.plot3, self.split-1)
            
                #If image has been plotted
                if spec.chart_queue.empty():
                    self.canvas.draw()
            
        self.after(20, lambda : self.update_graph(False))
                

    def save_data(self, file_path=None, wavelengths=None, intensities=None, single_save=True, reference=False):
        """Saves the current raw data and reflectance/transmittance data if this mode is enabled.

        Notes
        ------------
        The saved file name always includes the iteration number, date, time, and spectrometer acquisition time. 
        Users can modify the file name in the directory frame. However, in the case of an advanced save, 
        the name specified in the associated popup takes priority. If no name is provided in the popup, 
        the one set in the directory frame will be used. If neither field is filled, the default name will be Spectrum

        Parameters
        ------------
        file_path : `str`, optional
            Path to the file save location, None by default
        wavelengths : `list(float)`, optional
            List of measured wavelengths, Empty by default
        intensities : `list(float)`, optional
            List of raw intensity data measured, Empty by default
        single_save : `bool`, optional
            Defines how files are named and whether or not a notification is returned after saving, True by default
        reference : `bool`, optional
            If this variable is true, then save the reflectance/transmittance data, False by default
        """
        
        if single_save:
            counts = None
            for i in range(len(self.connected_spectrometers)):
                file_path = self.master.directory_frame.get_spectrometer_directory(self.connected_spectrometers[i].integration_time)
                if counts == None :
                    counts = self.master.directory_frame.get_available_iteration(file_path)
                file_path = file_path.replace("#", str(counts)).replace("@", f"{datetime.now():%H.%M.%S}").replace("$", self.connected_spectrometers[i].name.split("-")[-1])                    
                self.single_save(file_path, wavelengths, intensities, single_save, reference, i)
        else:
            self.single_save(file_path, wavelengths, intensities, single_save, reference, self.split-1)
    
    def single_save(self, file_path, wavelengths, intensities, single_save, reference, index):      
        local_wavelengths, local_intensities = self.connected_spectrometers[index].chart_queue.get()
        wavelengths_to_write = wavelengths if wavelengths is not None else local_wavelengths
        intensities_to_write = intensities if intensities is not None else local_intensities
        if wavelengths_to_write is not None and intensities_to_write is not None:
            
            if file_path:
                try:
                    with open(file_path, mode='w', newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow(['Wavelength [nm]', ' Intensity [counts]'])
                        writer.writerow(['>>>>>Begin Spectral Data<<<<<'])
                        writer.writerows(zip(wavelengths_to_write, intensities_to_write))
                        
                    if self.reflectance_mode and not reference:
                        denominator = self.light_reference_intensities[index] - self.dark_reference_intensities[index]
                        denominator = numpy.where(denominator == 0, numpy.nan, denominator)
                        intensities = (intensities - self.dark_reference_intensities[index]) / denominator * 100
                        directory, filename = os.path.split(file_path)
                        file_path = f"{directory}/relative_{filename}"
                        with open(file_path, mode='w', newline='') as file:
                            writer = csv.writer(file)
                            writer.writerow(['Wavelength [nm]', ' Relative intensity [%]'])
                            writer.writerow(['>>>>>Begin Spectral Data<<<<<'])
                            writer.writerows(zip(wavelengths_to_write, intensities_to_write))
                    if single_save:
                        self.notification(f"Successfully saved as", file_path, "#1a8300", path=file_path)
                        print(f"Data saved successfully to {file_path}")
                except Exception as e:
                    print(f"Error saving data: {e}")
                    self.notification(f"Impossible to save as", file_path, "#8e0101")
            else:
                self.notification(f"No directory to save", color="#8e0101")
        else:
            self.notification(f"No data to save", color="#8e0101")
    
    
    def advanced_save(self):
        """Handles the advanced save process for spectrometer data.
        Waits briefly to ensure the spectrometer is initialized with the correct integration time. 
        Then, for the number of iterations requested by the user, it waits for new data to arrive and saves it accordingly.
        """
        #Test with one spectrometer
        time.sleep((self.acquisition_time /1000) + 0.5)
        self.connected_spectrometers[self.split-1].save_queue.queue.clear()
        while self.backups_counts > 0:
            self.backups_counts -= 1
            self.wavelengthsList[self.split-1], self.intensitiesList[self.split-1] = self.connected_spectrometers[self.split-1].save_queue.get()
            file_name = self.file_path.replace("#", str(self.file_counts)).replace("@", f"{datetime.now():%H.%M.%S}").replace("$", self.connected_spectrometers[self.split-1].name.split("-")[-1])   
            self.save_data(file_name, single_save=False)
            self.file_counts += 1

        if self.stop_after_saves:
            self.stop_spectrometer()
        self.notification(f"Serial backup completed !", color="#1a8300")
        self.thread_finish = True


    def advanced_save_popup(self):
        """Displays the advanced save popup.
        Allows users to configure a data backup sequence
        """
        if not self.popup:
            self.popup = CTkToplevel(self)
            self.popup.title("Spectrometer - Advanced save")
            self.popup.minsize(405, 330)
            self.center_popup(600, 400)
            self.popup.grid_rowconfigure((1,2,3,4,5,6), weight=1)
            self.popup.grid_columnconfigure((0,1), weight=1)
            self.popup.protocol("WM_DELETE_WINDOW", self.close_popup)
            self.popup.attributes("-topmost", True)
            self.after(50, lambda: self.popup.attributes("-topmost", False))

            time = f"{datetime.now():%Y%m%d_%H.%M.%S}"
            acq = (self.connected_spectrometers[self.split-1].integration_time or 100000) /1000
            self.backup_name = self.backup_name or self.master.directory_frame.spectrometer_backup_name.get()

            title = CTkLabel(self.popup, text="Please define your backup settings :", font=("Arial", 20))
            title.grid(row=0, column=0, padx=(40,0), pady=(30,20), sticky="w", columnspan=2)

            frame = CTkFrame(self.popup, fg_color="transparent")
            frame.grid(row=1, column=0, sticky="nsew", columnspan=2)
            CTkLabel(frame, text="File name :").pack(side="left", padx=(40,0))
            name = self.connected_spectrometers[self.split-1].name.split("-")[-1]
            if self.backup_name:
                self.backup_name_entry = CTkEntry(frame, placeholder_text=f"Spectrum_n°_{name}__{time}_{acq}ms",textvariable=StringVar(value=self.backup_name))
            else:
                self.backup_name_entry = CTkEntry(frame, placeholder_text=f"Spectrum_n°_{name}__{time}_{acq}ms")
            self.backup_name_entry.pack(side="left", fill="x", expand=True, padx=(20,40))

            frame = CTkFrame(self.popup, fg_color="transparent")
            frame.grid(row=2, column=0, sticky="nsew", columnspan=2)
            CTkLabel(frame, text="Acquisition time :").pack(side="left", padx=(40,20))
            self.acquisition_time_entry = CTkEntry(frame, placeholder_text="100.0", textvariable=StringVar(value=acq))
            self.acquisition_time_entry.pack(side="left")
            CTkLabel(frame, text="ms").pack(side="left", padx=5)

            frame = CTkFrame(self.popup, fg_color="transparent")
            frame.grid(row=3, column=0, sticky="nsew", columnspan=2)
            CTkLabel(frame, text="Number of files to save :").pack(side="left", padx=(40,10))
            CTkButton(frame, text="-", width=10, fg_color="transparent", command=lambda: self.increment_entry("-",self.backups_counts_entry)).pack(side="left")
            self.backups_counts_entry = CTkEntry(frame, width=100, placeholder_text="10", textvariable=StringVar(value=self.backups_counts_memorie))
            self.backups_counts_entry.pack(side="left", padx=1)
            CTkButton(frame, text="+", width=10, fg_color="transparent", command=lambda: self.increment_entry("+",self.backups_counts_entry)).pack(side="left")
            CTkLabel(frame, text="files").pack(side="left", padx=5)

            frame = CTkFrame(self.popup, fg_color="transparent")
            frame.grid(row=4, column=0, sticky="nsew", columnspan=2)
            CTkLabel(frame, text="Save every").pack(side="left", padx=(40,5))
            CTkButton(frame, text="-", width=10, fg_color="transparent", command=lambda: self.increment_entry("-",self.save_frequency_entry)).pack(side="left")
            self.save_frequency_entry = CTkEntry(frame, width=100, placeholder_text="1", textvariable=StringVar(value=self.save_frequency))
            self.save_frequency_entry.pack(side="left")      
            CTkButton(frame, text="+", width=10, fg_color="transparent", command=lambda: self.increment_entry("+",self.save_frequency_entry)).pack(side="left")
            CTkLabel(frame, text="scan").pack(side="left", padx=5)

            frame = CTkFrame(self.popup, fg_color="transparent")
            frame.grid(row=5, column=0, sticky="nsew", columnspan=2)
            self.light_reference_entry = CTkCheckBox(frame, text="Light reference", border_width=2, border_color="#1F6AA5")
            self.light_reference_entry.pack(side="left", padx=40)
            self.dark_reference_entry = CTkCheckBox(frame, text="Dark reference", border_width=2, border_color="#1F6AA5")
            self.dark_reference_entry.pack(side="left", padx=0)
            if self.light_reference:
                self.light_reference_entry.select()
            elif self.light_reference_intensities[self.split-1] is None:
                self.light_reference_entry.configure(state="disabled", border_color="gray45")
            if self.dark_reference:
                self.dark_reference_entry.select()
            elif self.dark_reference_intensities[self.split-1] is None:
                self.dark_reference_entry.configure(state="disabled", border_color="gray45")

            self.stop_after_saves_entry = CTkCheckBox(self.popup, text="Stop spectrometer after saves", border_width=2, border_color="#1F6AA5")
            self.stop_after_saves_entry.grid(row=6, column=0, padx=40, sticky="nsew", columnspan=2)
            if self.stop_after_saves: self.stop_after_saves_entry.select()
            CTkButton(self.popup, text="Cancel", fg_color="transparent", border_width=2, border_color="#1F6AA5", command=self.close_popup).grid(row=7, column=0, padx=(40,20), pady=20, sticky="ew")
            CTkButton(self.popup, text="Save", command=self.start_save_thread).grid(row=7, column=1, padx=(20,40), pady=20, sticky="ew")

        self.popup.focus_force()


    def increment_entry(self, operator, entry):
        """Adjusts the value in a given entry field by incrementing or decrementing it.
        Returns a notification if the entry value is not a positive integer

        Parameters
        ------------
        operator : `str`
            Increments field value if “+” or decrements if “-”
        entry : `CTkEntry`
            User-modifiable field
        """
        try:
            val = int(entry.get())
            if operator == "+":
                val += 1
            elif operator == "-" and val > 1:
                val -= 1
            entry.configure(textvariable=StringVar(value=val))
        except:
            self.notification(f"Must be a positive integer", color="#8e0101")


    def center_popup(self, width, height):
        """Centers the popup window in the main window

        Parameters
        ------------
        width : `int`
            Popup width
        height : `int`
            Popup height
        """
        x = int((self.master.winfo_width()/2) + self.master.winfo_x() - (width/2))
        y = int((self.master.winfo_height()/2) + self.master.winfo_y() - (height/2))
        self.popup.geometry(f"{width}x{height}+{x}+{y}")


    def close_popup(self):
        """Closes the settings popup cleanly
        """
        if self.popup:
            self.popup.destroy()
            self.popup = None
    

    def is_thread_finished(self):
        """Checks every 500ms if the advanced save thread is finished. 
        If so, then the advanced save popup is cleanly closed
        """
        if self.thread_finish:
            self.connected_spectrometers[self.split-1].acquire_save_data = 0
            self.close_popup()
        else:
            self.after(500, self.is_thread_finished)
    

    def start_save_thread(self):
        """Checks that all fields entered by the user are correct. 
        If so, initialize and start the advanced save thread
        """
        if not self.check_acquisition_time(): return
        if not self.check_backups_counts(): return
        if not self.check_save_frequency(): return

        self.thread_finish = False
        self.backup_name = self.backup_name_entry.get()
        self.stop_after_saves = self.stop_after_saves_entry.get()
        self.light_reference = self.light_reference_entry.get()
        self.dark_reference = self.dark_reference_entry.get()
        self.connected_spectrometers[self.split-1].acquire_save_data = self.save_frequency
        self.connected_spectrometers[self.split-1].set_integration_time(self.acquisition_time *1000)
        self.file_path = self.master.directory_frame.get_spectrometer_directory(self.connected_spectrometers[self.split-1].integration_time, self.backup_name_entry.get())
        self.file_counts = self.master.directory_frame.get_available_iteration(self.file_path)

        self.popup.withdraw()
        reference_path = os.path.dirname(self.file_path)
        end_file = f"_{self.backup_name}_{str(self.file_counts)}__{datetime.now():%Y%m%d_%H.%M.%S}_{self.acquisition_time}ms.txt"
        if self.light_reference:
            self.save_data(f"{reference_path}/reference{end_file}", self.light_reference_wavelengths[self.split-1], self.light_reference_intensities[self.split-1], False, True)
            if self.light_ref_acquisition_time != self.connected_spectrometers[self.split-1].integration_time:
                self.notification(f"Light reference acquisition time differs from current", color="#e17e00")
        if self.dark_reference:
            self.save_data(f"{reference_path}/dark{end_file}", self.dark_reference_wavelengths[self.split-1], self.dark_reference_intensities[self.split-1], False, True)
            if self.dark_ref_acquisition_time != self.connected_spectrometers[self.split-1].integration_time:
                self.notification(f"Dark reference acquisition time differs from current", color="#e17e00")

        if not self.connected_spectrometers[self.split-1].is_running: self.start_spectrometer()
        self.notification(f"Serial backup has begun...", color="#006bd2")
        self.save_thread = threading.Thread(target=self.advanced_save, daemon=True)
        self.save_thread.start()
        self.is_thread_finished()


    def check_acquisition_time(self):
        """Checks the validity of content entered by users before using it.
        If the content is inappropriate, an error notification is sent to the user

        Note that the acquisition time must be a positive float between 8 and 1600000
        
        Returns
        ------------
        check_acquisition_time : `bool`
            Whether or not valid
        """
        try:
            self.acquisition_time = float(self.acquisition_time_entry.get())
            if 8 <= self.acquisition_time <= 1600000:
                return True
            else:
                self.notification(f"Integration time must be between 8 ms and 1600000 ms", color="#8e0101")
                return False
        except:
            self.notification(f"Integration time must be a number", color="#8e0101")
            return False


    def check_backups_counts(self):
        """Checks the validity of content entered by users before using it.
        If the content is inappropriate, an error notification is sent to the user

        Note that the backups counts must be a positive integer
        
        Returns
        ------------
        check_backups_counts : `bool`
            Whether or not valid
        """
        try:
            self.backups_counts = int(self.backups_counts_entry.get())
            self.backups_counts_memorie = self.backups_counts
            result = self.backups_counts > 0
            if not result:
                self.notification(f"The number of backups must be higher than 0", color="#8e0101")
            return result
        except:
            self.notification(f"The number of backups must be an integer", color="#8e0101")
            return False


    def check_save_frequency(self):
        """Checks the validity of content entered by users before using it.
        If the content is inappropriate, an error notification is sent to the user

        Note that the save frequency must be a positive integer
        
        Returns
        ------------
        check_save_frequency : `bool`
            Whether or not valid
        """
        try:
            self.save_frequency = int(self.save_frequency_entry.get())
            result = self.save_frequency > 0
            if not result:
                self.notification(f"The number of scan must be higher than 0", color="#8e0101")
            return result
        except:
            self.notification(f"The number of scan must be an integer", color="#8e0101")
            return False


    #TODO: Modify to get light reference of both spectrometers
    def set_light_reference(self):
        """Stores light reference data
        """
      
        for i in range(len(self.connected_spectrometers)):  
            
            wave, inten = self.connected_spectrometers[i].chart_queue.get()
            self.light_reference_wavelengths[i] = wave.copy()
            self.light_reference_intensities[i] = inten.copy()
             
            self.light_ref_acquisition_time[i] = self.connected_spectrometers[i].integration_time
            
            if self.light_reference_intensities[i] is not None:
                self.light_reference = True
                self.notification(f"Light reference successfully recorded", color="#1a8300")
            else:
                self.light_reference = False
                self.notification(f"There is no data to save for the light reference", color="#8e0101")


    #TODO: Modify to get dark reference of both spectrometers
    def set_dark_reference(self):
        """Stores dark reference data
        """
       
        for i in range(len(self.connected_spectrometers)):      
            
            wave, inten = self.connected_spectrometers[i].chart_queue.get()
            self.dark_reference_wavelengths[i] = wave.copy()
            self.dark_reference_intensities[i] = inten.copy()
             
            self.dark_ref_acquisition_time[i] = self.connected_spectrometers[i].integration_time
       
            if self.dark_reference_intensities[i] is not None:
                self.dark_reference = True
                self.notification(f"Dark reference successfully recorded", color="#1a8300")
            else:
                self.dark_reference = False
                self.notification(f"There is no data to save for the dark reference", color="#8e0101")



    def import_chart(self):
        """Overloads the graph with data imported by users. 
        Adjusts axis titles according to the display mode selected. 
        Displays file names in the legend in a simplified version
        """
        
        file_paths = filedialog.askopenfilenames(initialdir=self.master.backup_directory ,filetypes=[("CSV and TXT files", "*.csv *.txt"), ("CSV files", "*.csv"), ("Text files", "*.txt")])

        self.stop_spectrometer()
        if file_paths:
            if len(self.plot3.lines) == 1:
                self.plot3.clear()
                if self.reflectance_mode:
                    intensities = self.reflectance_intensities
                    self.plot3.set_ylabel('Relative intensity [%]')
                else:
                    intensities = self.intensitiesList[self.split-1]
                    self.plot3.set_ylabel('Intensity [counts]')

                self.plot3.plot(self.wavelengthsList[self.split-1], intensities, label="Current")
                self.plot3.set_xlabel('Wavelength [nm]')
                self.plot3.grid()
            
            for file_path in file_paths:
                x, y = [], []
            
                if file_path.endswith(".csv"):
                    with open(file_path, newline='') as file:
                        reader = csv.reader(file)
                        next(reader)
                        for row in reader:
                            x.append(float(row[0]))
                            y.append(float(row[1]))
                
                else:
                    with open(file_path, 'r') as file:
                        for line in file:
                            if line.strip() == ">>>>>Begin Spectral Data<<<<<":
                                break
                        
                        for line in file:
                            parts = line.strip().split(',')
                            if len(parts) == 2: 
                                x.append(float(parts[0]))
                                y.append(float(parts[1]))


                legend = os.path.basename(file_path).split('__')[0]
                self.plot3.plot(x, y, label=legend)

            self.plot3.legend()
            self.canvas.draw()


    def extend(self):
        """Not available.
        The purpose of this method is to open the spectrometer frame in a 
        new window in order to have a larger view of the spectrometer graph
        """
        self.notification(f"Coming soon !", color="#006bd2")

    def notification(self, head_message=None, message=None, color=None, path=""):
        """Creates notifications attached to the main window. 

        Parameters
        ------------
        head_message : `str`, optional
            Main content. None by default
        message : `str`, optional
            Sub-content used to display the path of the last saved file. None by default
        color : `str`, optional
            Notification border color. Grey by default
        """
        self.master.notification(head_message, message, color, path)

    def on_closing(self):
        """Stops the current thread and disconnects the spectrometer cleanly
        """
        for spec in self.connected_spectrometers:
            if spec:
                self.backups_counts = 0
                time.sleep(0.2)
                spec.disconnect()
            
            
    def toggle_split_screen(self):
        self.split = ((self.split ) % 2) + 1

        debugp("spec", "Split:" + str(self.split))
        self.plot3.cla()
        
        if self.split == 0:
            self.view_button.configure(image=img_split)
        elif self.split == 1:
            self.view_button.configure(image=img_split_left)
        else:
            self.view_button.configure(image=img_split_right)