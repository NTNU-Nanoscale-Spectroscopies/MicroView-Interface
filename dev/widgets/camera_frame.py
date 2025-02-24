from ..images.images import *
from .notification import *
import queue
import re

class CameraFrame(CTkFrame):
    """Class for creating a frame to control a camera"""

    def __init__(self, master, camera):
        """Create a frame in the main window.
        Users can easily control the camera

        Parameters
        ------------
        master : `CTk`
            Main window
        camera : `MyCamera`
            Object containing all information about a camera
        """
        super().__init__(master)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.grid_propagate(False)
        
        self.default_exposure = 60

        if not camera:
            self.label = CTkLabel(self, text="No camera", font=("Arial", 25))
            self.label.grid(row=3, column=1, padx=5, pady=5)
        else:
            self.camera = camera
            self.init()


    def init(self):
        """Creating the initial camera display
        """
        self.disconnected_label = CTkLabel(self, text="Disconnected", font=("Arial", 25))
        self.disconnected_label.grid(row=3, column=1, padx=5, pady=5)
        self.disconnected_button = CTkButton(self, text="", width=30, height=40,  image=img_retry, fg_color="transparent", command=self.reconnection)
        self.disconnected_button.grid(row=3, column=1, padx=5, pady=(75, 0))


    def connect(self):
        """Try connecting the camera. 
        If the connection is established, the frame is updated to access the associated functionality.
        In addition, if the device enable parameter is activated, the device is automatically started
        
        Retruns
        ------------
        connect : `bool`
            Wether the camera is connected
        """
        
        #Testing or True
        if self.camera.connect():
                    
            self.disconnected_label.grid_forget()
            self.disconnected_button.grid_forget()

            self.image_queue = None
            self.aspect_ratio = None
            self.image_width = None
            self.image_height = None

            self.image_label = CTkLabel(self, text="") 
            self.image_label.grid(row=0, column=1, sticky="nsew", rowspan=4)
            self.fullscreen_button = CTkButton(self, text="", width=40, height=40, image=img_full_screen, fg_color="transparent", command=self.extend)
            self.fullscreen_button.grid(row=0, column=2, padx=5, pady=(5,0), sticky="ne")
            self.resize_button = CTkButton(self, text="", width=40, height=40, image=img_rescale, fg_color="transparent", command=self.resize_image)
            self.resize_button.grid(row=1, column=2, padx=5, pady=(5,0), sticky="ne")
            self.pause_button = CTkButton(self, text="", width=30, height=40, image=img_pause, fg_color="transparent", command=self.stop_camera)
            self.pause_button.grid(row=0, column=0, padx=5, pady=(5,0), sticky="nw")
            self.play_button = CTkButton(self, text="", width=30, height=40,  image=img_play, fg_color="transparent", command=self.start_camera)
            self.play_button.grid(row=0, column=0, padx=5, pady=(5,0), sticky="nw")
            self.save_button = CTkButton(self, text="", width=30, height=40, image=img_save, fg_color="transparent", command=self.save_image)
            self.save_button.grid(row=1, column=0, padx=5, pady=(5,0), sticky="nw")

            #Frame that contains all the exposure elements
            self.exposure_frame = CTkFrame(self, fg_color="transparent")
            self.exposure_frame.grid(row=4, column=0, columnspan=3, padx=10, pady=(5, 5), sticky="ew")

            self.exposure_frame.columnconfigure(0, weight=1)
            self.exposure_frame.columnconfigure(1, weight=0)
            self.exposure_frame.columnconfigure(2, weight=0) 
            self.exposure_frame.columnconfigure(3, weight=0) 

            self.exposure_slider = CTkSlider(self.exposure_frame, from_=0, to=1000, command=self.on_exposure_slider_updated)
            self.exposure_slider.set(self.default_exposure)
            self.exposure_slider.grid(row=0, column=0, padx=(10, 5), sticky="ew")  # Expands

            self.exposure_var = StringVar(value=self.default_exposure)
            self.exposure_var.trace_add("write", self.validate_input)
            self.exposure_display = CTkEntry(self.exposure_frame, textvariable=self.exposure_var, width=60)
            self.exposure_display.grid(row=0, column=1, padx=(5, 5), sticky="w")

            self.exposure_label = CTkLabel(self.exposure_frame, text="ms")
            self.exposure_label.grid(row=0, column=2, padx=(1, 5), sticky="w")

            self.exposure_set = CTkButton(self.exposure_frame, text="Set", width=40, command=self.on_exposure_entry_updated)
            self.exposure_set.grid(row=0, column=3, padx=(5, 10), sticky="w")

            self.current_image = None
            if self.camera.enable: 
                self.start_camera()
                
            

        return self.camera.connected


    def reconnection(self):
        """Try reconnecting the camera via `setup frame` to update the display correctly
        """
        self.master.quick_setup_frame.reconnection(self.camera)


    def disconnect(self):
        """Stops the current thread, disconnects the camera cleanly, then updates the display
        """
        for widget in self.winfo_children():
            widget.destroy()
        self.init()
        self.on_closing()


    def start_camera(self):
        """Starts thread for continuous camera image extraction
        """
        self.image_queue = self.camera.run()
        self.pause_button.lift()
        self.update_image()


    def stop_camera(self):
        """Stops continuous extraction of camera images without disconnecting the camera
        """
        self.camera.stop()
        self.play_button.lift()


    def update_image(self):
        """Updates display with images retrieved by camera every 100ms.
        Initializes the image dimensions obtained in the first iteration
        """
        if self.image_queue and self.camera.is_running:
            try:
                self.current_image = self.image_queue.get_nowait()
                if not self.aspect_ratio:
                    image_width, image_height = self.current_image.size
                    self.aspect_ratio = image_width / image_height
                    self.resize_image()
                ctk_image = CTkImage(self.current_image, size=(self.image_width, self.image_height))
                self.image_label.configure(image=ctk_image)
            except queue.Empty:
                pass
            self.after(100, self.update_image)


    def resize_image(self):
        """Updates image dimensions according to available window space
        """
        if self.aspect_ratio:
            frame_width = int(self.master.winfo_width() /2.6)
            frame_height = int(self.master.winfo_height() /2.6)

            if frame_width / frame_height > self.aspect_ratio:
                self.image_height = frame_height
                self.image_width = int(self.image_height * self.aspect_ratio)
            else:
                self.image_width = frame_width
                self.image_height = int(self.image_width / self.aspect_ratio)


    def save_image(self):
        """Saves the current image with the name assigned in the `directory frame`
        """
        if self.current_image:
            file_path = self.master.directory_frame.get_camera_directory()
            if file_path:
                try:
                    self.current_image.save(file_path)
                    self.master.notification(f"Successfully saved as", file_path, "#1a8300")
                    print(f"Image saved to {file_path}")
                except Exception as e:
                    print(f"Error saving image: {e}")
                    self.master.notification(f"Impossible to save as", file_path, "#8e0101")
            else:
                self.master.notification(f"No directory to save", color="#8e0101")
        else:
            self.master.notification(f"No image to save", color="#8e0101")


    def extend(self):
        """Not available.
        The purpose of this method is to open the camera frame in a 
        new window in order to have a larger view of the camera return
        """
        self.master.notification(f"Coming soon !", color="#006bd2")


    def on_closing(self):
        """Stops the current thread and disconnects the camera cleanly
        """
        if self.camera:
            self.camera.disconnect()
            
            
    def on_exposure_slider_updated(self, value):
        """Updates the entry box and sets the camera exposure
        
        Parameters
        ------------
        value : `float`
            Exposure value in milliseconds
        """
        val = round(value)
        self.exposure_display.configure(textvariable = StringVar(value=str(val)))
        self.on_exposure_updated(val)
        
        
        
    def on_exposure_entry_updated(self):
        """Updates the slider and sets the camera exposure
        """
        str_val = self.exposure_display.get()
        match = re.search(r'\b\d+(\.\d+)?\b', str_val)
        if match:
            value = float(match.group()) if '.' in match.group() else int(match.group())
  
            print(value)
        else:
            self.exposure_display.configure(textvariable = StringVar(value=""))
            return
        self.exposure_slider.set(value)
        self.exposure_display.configure(textvariable = StringVar(value=str(value)))
        
        self.on_exposure_updated(value)
        
        
    def validate_input(self, *args):
        """Restrain Entry to only numbers between 0 and 1000
        """
        value = self.exposure_var.get()
        match = re.search(r'\b\d+(\.\d+)?\b', value)
        if match:
            num_value = float(match.group()) if '.' in match.group() else int(match.group())
        else:
            self.exposure_display.configure(textvariable = StringVar(value=""))
            return
        
        self.exposure_var.set(num_value)
        
        
    def on_exposure_updated(self, value):
        """Sets the camera exposure
        
        Parameters
        ------------
        value : `float`
            Exposure value in milliseconds
        """
        #Push notification if value is lower than 100time the minimum exposure time
        if value <= 0.04 * 100 :
            self.master.notification(f"Warning: Low exposure time may cause lag in the spectrometer.", color="#ffa500")

        self.camera.update_exposure(value)