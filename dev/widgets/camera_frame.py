from ..images.images import *
from .notification import *
import queue
import re
from customtkinter import BooleanVar
from PIL import ImageDraw

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
            self.exposure_display.bind("<FocusIn>", self._on_exposure_entry_focus)

            self.exposure_label = CTkLabel(self.exposure_frame, text="ms")
            self.exposure_label.grid(row=0, column=2, padx=(1, 5), sticky="w")

            self.exposure_set = CTkButton(self.exposure_frame, text="Set", width=40, command=self.on_exposure_entry_updated)
            self.exposure_set.grid(row=0, column=3, padx=(5, 5), sticky="w")

            # Auto-exposure checkbox – only shown for Zelux cameras
            self.auto_exposure_var = BooleanVar(value=False)
            self.auto_exposure_checkbox = CTkCheckBox(
                self.exposure_frame,
                text="Auto",
                variable=self.auto_exposure_var,
                width=60,
                command=self.on_auto_exposure_toggled,
            )
            if getattr(self.camera, "is_zelux", False):
                self.exposure_frame.columnconfigure(4, weight=0)
                self.auto_exposure_checkbox.grid(row=0, column=4, padx=(5, 10), sticky="w")

            # Crosshair overlay checkbox – helps align the sample with the view centre
            self.crosshair_var = BooleanVar(value=False)
            self.exposure_frame.columnconfigure(5, weight=0)
            self.crosshair_checkbox = CTkCheckBox(
                self.exposure_frame,
                text="Crosshair",
                variable=self.crosshair_var,
                width=60,
                command=self.on_crosshair_toggled,
            )
            self.crosshair_checkbox.grid(row=0, column=5, padx=(5, 10), sticky="w")

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
        if hasattr(self.master, "restore_camera_frame"):
            self.master.restore_camera_frame()
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
                display_image = self._apply_crosshair(self.current_image)
                self._ctk_image = CTkImage(display_image, size=(self.image_width, self.image_height))
                self.image_label.configure(image=self._ctk_image)

                # Run software auto-exposure adjustment if enabled
                if getattr(self.camera, "auto_exposure_enabled", False):
                    self.camera.auto_adjust_exposure(self.current_image)
                    # Sync the UI indicators with the current auto-adjusted exposure
                    try:
                        current_ms = round(self.camera.camera.exposure_time_us / 1000)
                        self.exposure_slider.set(current_ms)
                        self.exposure_display.configure(textvariable=StringVar(value=str(current_ms)))
                    except Exception:
                        pass

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


    def set_image_size(self, width, height):
        """Apply a saved display size to the current camera image."""
        self.image_width = width
        self.image_height = height
        image_label = getattr(self, "image_label", None)
        if self.current_image and image_label:
            display_image = self._apply_crosshair(self.current_image)
            self._ctk_image = CTkImage(display_image, size=(width, height))
            image_label.configure(image=self._ctk_image)


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
        """Open or restore the floating camera window."""
        if hasattr(self.master, "toggle_camera_popout"):
            self.master.toggle_camera_popout()
        else:
            self.master.notification(f"Floating camera view unavailable", color="#8e0101")


    def on_closing(self):
        """Stops the current thread and disconnects the camera cleanly
        """
        if self.camera:
            self.camera.disconnect()
            
            
    def on_exposure_slider_updated(self, value):
        """Updates the entry box and sets the camera exposure.
        Also disables auto-exposure when the user manually moves the slider.
        
        Parameters
        ------------
        value : `float`
            Exposure value in milliseconds
        """
        # Disable auto-exposure on manual slider interaction
        if self.auto_exposure_var.get():
            self.auto_exposure_var.set(False)
            self.on_auto_exposure_toggled()

        val = round(value)
        self.exposure_display.configure(textvariable = StringVar(value=str(val)))
        self.on_exposure_updated(val)
        
        
        
    def on_exposure_entry_updated(self):
        """Updates the slider and sets the camera exposure.
        Also disables auto-exposure when the user manually sets a value.
        """
        # Disable auto-exposure on manual set
        if self.auto_exposure_var.get():
            self.auto_exposure_var.set(False)
            self.on_auto_exposure_toggled()

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


    def on_auto_exposure_toggled(self):
        """Called when the auto-exposure checkbox is toggled."""
        enabled = self.auto_exposure_var.get()
        self.camera.set_auto_exposure(enabled)


    def on_crosshair_toggled(self):
        """Called when the crosshair checkbox is toggled.

        Refreshes the displayed image immediately so the change is visible even
        when the live stream is paused.
        """
        if self.current_image and getattr(self, "image_width", None) and getattr(self, "image_height", None):
            display_image = self._apply_crosshair(self.current_image)
            self._ctk_image = CTkImage(display_image, size=(self.image_width, self.image_height))
            self.image_label.configure(image=self._ctk_image)


    def _apply_crosshair(self, image):
        """Return a copy of `image` with a centred crosshair drawn on it.

        The crosshair is drawn on the image content itself so its centre always
        matches the centre of the sample view, in both the embedded and the
        pop-out window. The original image is never modified, so saved images
        stay clean. If the crosshair is disabled the original image is returned
        unchanged.

        Parameters
        ------------
        image : `PIL.Image`
            The current camera frame

        Returns
        ---------
        _apply_crosshair : `PIL.Image`
            The frame with the crosshair, or the untouched frame if disabled
        """
        if not getattr(self, "crosshair_var", None) or not self.crosshair_var.get():
            return image

        overlay = image.convert("RGB")
        draw = ImageDraw.Draw(overlay)
        width, height = overlay.size
        cx, cy = width // 2, height // 2
        color = (255, 0, 0)
        gap = max(4, min(width, height) // 40)
        line_width = max(2, min(width, height) // 250)

        # Horizontal arms (left and right of the centre gap)
        draw.line((0, cy, cx - gap, cy), fill=color, width=line_width)
        draw.line((cx + gap, cy, width, cy), fill=color, width=line_width)
        # Vertical arms (above and below the centre gap)
        draw.line((cx, 0, cx, cy - gap), fill=color, width=line_width)
        draw.line((cx, cy + gap, cx, height), fill=color, width=line_width)
        # Small ring marking the exact centre
        draw.ellipse((cx - gap, cy - gap, cx + gap, cy + gap), outline=color, width=line_width)

        return overlay


    def _on_exposure_entry_focus(self, event=None):
        """Disable auto-exposure when the user clicks into the exposure entry to type."""
        if self.auto_exposure_var.get():
            self.auto_exposure_var.set(False)
            self.on_auto_exposure_toggled()


class FloatingCameraFrame(CTkFrame):
    """Detached live camera view controlled by the main CameraFrame."""

    def __init__(self, master, source_frame, restore_command):
        super().__init__(master)
        self.source_frame = source_frame
        self.restore_command = restore_command
        self.aspect_ratio = getattr(source_frame, "aspect_ratio", None)
        self.image_width = None
        self.image_height = None
        self.current_image_size = None
        self._ctk_image = None
        self._after_id = None
        self._resize_after_id = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.grid_propagate(False)

        self._build()
        self.bind("<Configure>", self._on_configure)
        self._after_id = self.after(50, self.update_image)

    def _build(self):
        self.image_label = CTkLabel(self, text="Waiting for camera...")
        self.image_label.grid(row=0, column=1, sticky="nsew", rowspan=4)

        self.restore_button = CTkButton(
            self,
            text="",
            width=40,
            height=40,
            image=img_full_screen,
            fg_color="transparent",
            command=self.restore_command,
        )
        self.restore_button.grid(row=0, column=2, padx=5, pady=(5, 0), sticky="ne")

        self.resize_button = CTkButton(
            self,
            text="",
            width=40,
            height=40,
            image=img_rescale,
            fg_color="transparent",
            command=self.resize_image,
        )
        self.resize_button.grid(row=1, column=2, padx=5, pady=(5, 0), sticky="ne")

        self.pause_button = CTkButton(
            self,
            text="",
            width=30,
            height=40,
            image=img_pause,
            fg_color="transparent",
            command=self.stop_camera,
        )
        self.pause_button.grid(row=0, column=0, padx=5, pady=(5, 0), sticky="nw")

        self.play_button = CTkButton(
            self,
            text="",
            width=30,
            height=40,
            image=img_play,
            fg_color="transparent",
            command=self.start_camera,
        )
        self.play_button.grid(row=0, column=0, padx=5, pady=(5, 0), sticky="nw")

        self.save_button = CTkButton(
            self,
            text="",
            width=30,
            height=40,
            image=img_save,
            fg_color="transparent",
            command=self.source_frame.save_image,
        )
        self.save_button.grid(row=1, column=0, padx=5, pady=(5, 0), sticky="nw")

        self.exposure_frame = CTkFrame(self, fg_color="transparent")
        self.exposure_frame.grid(row=4, column=0, columnspan=3, padx=10, pady=(5, 5), sticky="ew")

        self.exposure_frame.columnconfigure(0, weight=1)
        self.exposure_frame.columnconfigure(1, weight=0)
        self.exposure_frame.columnconfigure(2, weight=0)
        self.exposure_frame.columnconfigure(3, weight=0)

        current_exposure = self._get_current_exposure()
        self.exposure_slider = CTkSlider(self.exposure_frame, from_=0, to=1000, command=self.on_exposure_slider_updated)
        self.exposure_slider.set(current_exposure)
        self.exposure_slider.grid(row=0, column=0, padx=(10, 5), sticky="ew")

        self.exposure_var = StringVar(value=str(current_exposure))
        self.exposure_display = CTkEntry(self.exposure_frame, textvariable=self.exposure_var, width=60)
        self.exposure_display.grid(row=0, column=1, padx=(5, 5), sticky="w")
        self.exposure_display.bind("<FocusIn>", self._on_exposure_entry_focus)

        self.exposure_label = CTkLabel(self.exposure_frame, text="ms")
        self.exposure_label.grid(row=0, column=2, padx=(1, 5), sticky="w")

        self.exposure_set = CTkButton(self.exposure_frame, text="Set", width=40, command=self.on_exposure_entry_updated)
        self.exposure_set.grid(row=0, column=3, padx=(5, 5), sticky="w")

        self.auto_exposure_var = BooleanVar(value=self._source_auto_exposure_enabled())
        self.auto_exposure_checkbox = CTkCheckBox(
            self.exposure_frame,
            text="Auto",
            variable=self.auto_exposure_var,
            width=60,
            command=self.on_auto_exposure_toggled,
        )
        if getattr(self.source_frame.camera, "is_zelux", False):
            self.exposure_frame.columnconfigure(4, weight=0)
            self.auto_exposure_checkbox.grid(row=0, column=4, padx=(5, 10), sticky="w")

        # Crosshair overlay checkbox – mirrors the main frame's setting
        self.crosshair_var = BooleanVar(value=self._source_crosshair_enabled())
        self.exposure_frame.columnconfigure(5, weight=0)
        self.crosshair_checkbox = CTkCheckBox(
            self.exposure_frame,
            text="Crosshair",
            variable=self.crosshair_var,
            width=60,
            command=self.on_crosshair_toggled,
        )
        self.crosshair_checkbox.grid(row=0, column=5, padx=(5, 10), sticky="w")

        self._sync_run_buttons()

    def _on_configure(self, event=None):
        if self._resize_after_id:
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(80, self._resize_after_configure)

    def _resize_after_configure(self):
        self._resize_after_id = None
        self.resize_image()

    def _get_current_exposure(self):
        try:
            return int(float(self.source_frame.exposure_display.get()))
        except Exception:
            return getattr(self.source_frame, "default_exposure", 60)

    def _source_auto_exposure_enabled(self):
        try:
            return bool(self.source_frame.auto_exposure_var.get())
        except Exception:
            return False

    def _source_crosshair_enabled(self):
        try:
            return bool(self.source_frame.crosshair_var.get())
        except Exception:
            return False

    def _sync_run_buttons(self):
        if getattr(self.source_frame.camera, "is_running", False):
            self.pause_button.lift()
        else:
            self.play_button.lift()

    def _sync_source_exposure_controls(self, value):
        try:
            self.source_frame.exposure_slider.set(value)
        except Exception:
            pass
        try:
            self.source_frame.exposure_display.configure(textvariable=StringVar(value=str(value)))
        except Exception:
            pass

    def start_camera(self):
        if not getattr(self.source_frame.camera, "is_running", False):
            self.source_frame.start_camera()
        self._sync_run_buttons()

    def stop_camera(self):
        if getattr(self.source_frame.camera, "is_running", False):
            self.source_frame.stop_camera()
        self._sync_run_buttons()

    def resize_image(self):
        image = getattr(self.source_frame, "current_image", None)
        if image is None:
            return

        width, height = image.size
        if height == 0:
            return
        self.aspect_ratio = width / height

        frame_width = max(120, self.winfo_width() - 120)
        frame_height = max(120, self.winfo_height() - 80)

        if frame_width / frame_height > self.aspect_ratio:
            self.image_height = frame_height
            self.image_width = int(self.image_height * self.aspect_ratio)
        else:
            self.image_width = frame_width
            self.image_height = int(self.image_width / self.aspect_ratio)

    def update_image(self):
        image = getattr(self.source_frame, "current_image", None)
        if image:
            if self.current_image_size != image.size or not self.image_width or not self.image_height:
                self.current_image_size = image.size
                self.resize_image()
            if self.image_width and self.image_height:
                display_image = self.source_frame._apply_crosshair(image)
                self._ctk_image = CTkImage(display_image, size=(self.image_width, self.image_height))
                self.image_label.configure(image=self._ctk_image, text="")
        else:
            self.image_label.configure(text="Waiting for camera...")

        self._sync_run_buttons()
        try:
            self._after_id = self.after(100, self.update_image)
        except Exception:
            self._after_id = None

    def on_exposure_slider_updated(self, value):
        if self.auto_exposure_var.get():
            self.auto_exposure_var.set(False)
            self.on_auto_exposure_toggled()

        val = round(value)
        self.exposure_display.configure(textvariable=StringVar(value=str(val)))
        self._sync_source_exposure_controls(val)
        self.source_frame.on_exposure_updated(val)

    def on_exposure_entry_updated(self):
        if self.auto_exposure_var.get():
            self.auto_exposure_var.set(False)
            self.on_auto_exposure_toggled()

        str_val = self.exposure_display.get()
        match = re.search(r'\b\d+(\.\d+)?\b', str_val)
        if not match:
            self.exposure_display.configure(textvariable=StringVar(value=""))
            return

        value = float(match.group()) if "." in match.group() else int(match.group())
        self.exposure_slider.set(value)
        self.exposure_display.configure(textvariable=StringVar(value=str(value)))
        self._sync_source_exposure_controls(value)
        self.source_frame.on_exposure_updated(value)

    def on_auto_exposure_toggled(self):
        try:
            self.source_frame.auto_exposure_var.set(self.auto_exposure_var.get())
            self.source_frame.on_auto_exposure_toggled()
        except Exception:
            pass

    def on_crosshair_toggled(self):
        # Mirror onto the source frame so both views share the setting and the
        # shared drawing helper picks up the change on the next refresh.
        try:
            self.source_frame.crosshair_var.set(self.crosshair_var.get())
            self.source_frame.on_crosshair_toggled()
        except Exception:
            pass

    def _on_exposure_entry_focus(self, event=None):
        if self.auto_exposure_var.get():
            self.auto_exposure_var.set(False)
            self.on_auto_exposure_toggled()

    def on_closing(self):
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self._resize_after_id:
            try:
                self.after_cancel(self._resize_after_id)
            except Exception:
                pass
            self._resize_after_id = None
