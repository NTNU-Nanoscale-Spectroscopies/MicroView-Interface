from ..images.images import *
from .notification import *

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from datetime import *
import threading
import time
import csv


class SpectrometerFrame(CTkFrame):
    def __init__(self, master, spectrometer):
        super().__init__(master)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.grid_propagate(False)

        if not spectrometer:
            self.label = CTkLabel(self, text="No spectrometer", font=("Arial", 25))
            self.label.grid(row=3, column=1, padx=5, pady=5)
        else:
            self.spectrometer = spectrometer
            self.init()
            self.after(120, self.connect)


    def init(self):
        self.disconnected_label = CTkLabel(self, text="Disconnected", font=("Arial", 25))
        self.disconnected_label.grid(row=3, column=1, padx=5, pady=5)
        self.disconnected_button = CTkButton(self, text="", width=30, height=40,  image=img_retry, fg_color="transparent", command=self.connect)
        self.disconnected_button.grid(row=3, column=1, padx=5, pady=(75, 0))

        self.popup = None
        self.wavelengths = None
        self.intensities = None
        self.backup_name = None
        self.stop_after_saves = False
        self.save_frequency = 1
        self.backups_counts_memorie = 10


    def connect(self):
        if self.spectrometer.connect():
            self.disconnected_label.grid_forget()
            self.disconnected_button.grid_forget()

            self.spectrometer.set_integration_time(self.spectrometer.integration_time)
            self.figure = Figure()
            self.plot1 = self.figure.subplots()
            self.canvas = FigureCanvasTkAgg(self.figure, master=self)
            self.canvas.get_tk_widget().grid(row=0, column=1, sticky="nsew", rowspan=4)
            toolbar_frame = CTkFrame(self)
            toolbar_frame.grid(row=0, column=1, sticky="new")
            self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_frame)
            self.toolbar.update()

            self.fullscreen_button = CTkButton(self, text="", width=40, height=40, image=img_full_screen, fg_color="transparent", command=self.extend)
            self.fullscreen_button.grid(row=0, column=2, padx=5, pady=5, sticky="ne")
            self.import_button = CTkButton(self, text="", width=40, height=40, image=img_plus, fg_color="transparent", command=self.import_chart)
            self.import_button.grid(row=1, column=2, padx=5, pady=5, sticky="ne")
            self.play_button = CTkButton(self, text="", width=30, height=40,  image=img_play, fg_color="transparent", command=self.start_spectrometer)
            self.play_button.grid(row=0, column=0, padx=5, pady=5, sticky="nw")
            self.pause_button = CTkButton(self, text="", width=30, height=40, image=img_pause, fg_color="transparent", command=self.stop_spectrometer)
            self.pause_button.grid(row=0, column=0, padx=5, pady=5, sticky="nw")
            self.save_button = CTkButton(self, text="", width=30, height=40, image=img_save, fg_color="transparent", command=self.save_data)
            self.save_button.grid(row=1, column=0, padx=5, pady=5, sticky="nw")
            self.save_button = CTkButton(self, text="", width=30, height=40, image=img_advanced_save, fg_color="transparent", command=self.advanced_save_popup)
            self.save_button.grid(row=2, column=0, padx=5, pady=5, sticky="nw")

            self.master.quick_setup_frame.check_connected_devices()
            if self.spectrometer.enable:
                self.start_spectrometer()
        else:
            self.notification(f"Unable to connect to {self.spectrometer.name} {self.spectrometer.serial}", color="#8e0101")

    
    def disconnect(self):
        for widget in self.winfo_children():
            widget.destroy()
        self.init()
        self.on_closing()


    def start_spectrometer(self):
        self.spectrometer.start()
        self.pause_button.lift()
        self.update_graph()


    def stop_spectrometer(self):
        self.spectrometer.stop()
        self.play_button.lift()


    def update_graph(self):
        if self.spectrometer.is_running:
            if not self.spectrometer.chart_queue.empty():
                self.wavelengths, self.intensities = self.spectrometer.chart_queue.get()
                self.plot1.clear()
                self.plot1.plot(self.wavelengths, self.intensities)
                self.plot1.set_xlabel('Wavelength [nm]')
                self.plot1.set_ylabel('Intensity [counts]')
                self.plot1.grid()
                self.canvas.draw()
            self.after(20, self.update_graph)


    def save_data(self, file_path=None, single_save=True):
        if self.wavelengths is not None and self.intensities is not None:
            if single_save:
                file_path = self.master.directory_frame.get_spectrometer_directory(self.spectrometer.integration_time)
                counts = self.master.directory_frame.get_available_iteration(file_path)
                file_path = file_path.replace("#", str(counts)).replace("@", f"{datetime.now():%H.%M.%S}")
            if file_path:
                try:
                    with open(file_path, mode='w', newline='') as file:
                        writer = csv.writer(file)
                        writer.writerow(['Wavelength [nm]', ' Intensity [counts]'])
                        writer.writerow(['>>>>>Begin Spectral Data<<<<<'])
                        writer.writerows(zip(self.wavelengths, self.intensities))
                    if single_save:
                        self.notification(f"Successfully saved as", file_path, "#1a8300")
                        print(f"Data saved successfully to {file_path}")
                except Exception as e:
                    print(f"Error saving data: {e}")
                    self.notification(f"Impossible to save as", file_path, "#8e0101")
            else:
                self.notification(f"No directory to save", color="#8e0101")
        else:
            self.notification(f"No data to save", color="#8e0101")
    
    
    def advanced_save(self):
        time.sleep((self.acquisition_time /1000) + 0.5)
        self.spectrometer.save_queue.queue.clear()
        while self.backups_counts > 0:
            self.backups_counts -= 1
            self.wavelengths, self.intensities = self.spectrometer.save_queue.get()
            file_name = self.file_path.replace("#", str(self.file_counts)).replace("@", f"{datetime.now():%H.%M.%S}")
            self.save_data(file_name, False)
            self.file_counts += 1

        if self.stop_after_saves:
            self.stop_spectrometer()
        self.notification(f"Serial backup completed !", color="#1a8300")
        self.thread_finish = True


    def advanced_save_popup(self):
        if not self.popup:
            self.popup = CTkToplevel(self)
            self.popup.title("Spectrometer - Advanced save")
            self.popup.minsize(405, 310)
            self.center_popup((600,380))
            self.popup.grid_rowconfigure((1,2,3,4,5,6), weight=1)
            self.popup.grid_columnconfigure((0,1), weight=1)
            self.popup.protocol("WM_DELETE_WINDOW", self.close_popup)

            time = f"{datetime.now():%Y%m%d_%H.%M.%S}"
            acq = (self.spectrometer.integration_time or 100000) /1000
            self.backup_name = self.backup_name or self.master.directory_frame.spectrometer_backup_name.get()

            title = CTkLabel(self.popup, text="Please define your backup settings :", font=("Arial", 20))
            title.grid(row=0, column=0, padx=(40,0), pady=(30,20), sticky="w", columnspan=2)

            frame = CTkFrame(self.popup, fg_color="transparent")
            frame.grid(row=1, column=0, sticky="nsew", columnspan=2)
            CTkLabel(frame, text="File name :").pack(side="left", padx=(40,0))
            if self.backup_name:
                self.backup_name_entry = CTkEntry(frame, placeholder_text=f"Spectrum_{time}_{acq}ms",textvariable=StringVar(value=self.backup_name))
            else:
                self.backup_name_entry = CTkEntry(frame, placeholder_text=f"Spectrum_{time}_{acq}ms")
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

            self.stop_after_saves_entry = CTkCheckBox(self.popup, text="Stop spectrometer after saves", border_width=2, border_color="#1F6AA5")
            self.stop_after_saves_entry.grid(row=5, column=0, padx=40, sticky="nsew", columnspan=2)
            if self.stop_after_saves: self.stop_after_saves_entry.select()
            CTkButton(self.popup, text="Cancel", fg_color="transparent", border_width=2, border_color="#1F6AA5", command=self.close_popup).grid(row=6, column=0, padx=(40,20), pady=20, sticky="ew")
            CTkButton(self.popup, text="Save", command=self.start_save_thread).grid(row=6, column=1, padx=(20,40), pady=20, sticky="ew")

        self.popup.focus_force()


    def increment_entry(self, operator, entry):
        try:
            val = int(entry.get())
            if operator == "+":
                val += 1
            elif operator == "-" and val > 1:
                val -= 1
            entry.configure(textvariable=StringVar(value=val))
        except:
            self.notification(f"Must be a positive integer", color="#8e0101")


    def center_popup(self, size):
        x = int((self.master.winfo_width()/2) + self.master.winfo_x() - (size[0]/2))
        y = int((self.master.winfo_height()/2) + self.master.winfo_y() - (size[1]/2))
        self.popup.geometry(f"{size[0]}x{size[1]}+{x}+{y}")


    def close_popup(self):
        if self.popup:
            self.popup.destroy()
            self.popup = None
    

    def is_thread_finished(self):
        if self.thread_finish:
            self.spectrometer.acquire_save_data = 0
            self.close_popup()
        else:
            self.after(500, self.is_thread_finished)
    

    def start_save_thread(self):
        if not self.check_acquisition_time(): return
        if not self.check_backups_counts(): return
        if not self.check_save_frequency(): return

        self.thread_finish = False
        self.backup_name = self.backup_name_entry.get()
        self.stop_after_saves = self.stop_after_saves_entry.get()
        self.spectrometer.acquire_save_data = self.save_frequency
        self.spectrometer.set_integration_time(self.acquisition_time *1000)
        self.file_path = self.master.directory_frame.get_spectrometer_directory(self.spectrometer.integration_time, self.backup_name_entry.get())
        self.file_counts = self.master.directory_frame.get_available_iteration(self.file_path)

        self.popup.withdraw()
        if not self.spectrometer.is_running: self.start_spectrometer()
        self.notification(f"Serial backup has begun...", color="#006bd2")
        self.save_thread = threading.Thread(target=self.advanced_save, daemon=True)
        self.save_thread.start()
        self.is_thread_finished()


    def check_acquisition_time(self):
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
        try:
            self.save_frequency = int(self.save_frequency_entry.get())
            result = self.save_frequency > 0
            if not result:
                self.notification(f"The number of scan must be higher than 0", color="#8e0101")
            return result
        except:
            self.notification(f"The number of scan must be an integer", color="#8e0101")
            return False


    def import_chart(self):
        file_paths = filedialog.askopenfilenames(filetypes=[("CSV and TXT files", "*.csv *.txt"), ("CSV files", "*.csv"), ("Text files", "*.txt")])
        self.stop_spectrometer()
        if file_paths:
            if len(self.plot1.lines) == 1:
                self.plot1.clear()
                self.plot1.plot(self.wavelengths, self.intensities, label="Current")
                self.plot1.set_xlabel('Wavelength [nm]')
                self.plot1.set_ylabel('Intensity [counts]')
                self.plot1.grid()
            
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
                self.plot1.plot(x, y, label=legend)

            self.plot1.legend()
            self.canvas.draw()


    def extend(self):
        self.notification(f"Coming soon !", color="#006bd2")

    def notification(self, head_message=None, message=None, color=None,):
        self.master.notification(head_message, message, color)

    def on_closing(self):
        if self.spectrometer:
            self.backups_counts = 0
            time.sleep(0.2)
            self.spectrometer.disconnect()