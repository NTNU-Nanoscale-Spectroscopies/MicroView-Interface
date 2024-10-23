from ..images.images import *
from .notification import *
import queue


class CameraFrame(CTkFrame):
    def __init__(self, master, camera):
        super().__init__(master)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.grid_propagate(False)

        if not camera:
            self.label = CTkLabel(self, text="No camera", font=("Arial", 25))
            self.label.grid(row=3, column=1, padx=5, pady=5)
            return

        self.disconnected_label = CTkLabel(self, text="Disconnected", font=("Arial", 25))
        self.disconnected_label.grid(row=3, column=1, padx=5, pady=5)
        self.disconnected_button = CTkButton(self, text="", width=30, height=40,  image=img_retry, fg_color="transparent", command=self.try_connection)
        self.disconnected_button.grid(row=3, column=1, padx=5, pady=(75, 0))

        self.camera = camera
        self.try_connection()


    def try_connection(self):
        if self.camera.connect():
            self.disconnected_label.grid_forget()
            self.disconnected_button.grid_forget()

            self.image_queue = None
            self.resize_after_id = None
            self.aspect_ratio = None
            self.image_width = None
            self.image_height = None
            self.bind("<Configure>", self.on_resize)

            self.image_label = CTkLabel(self, text="")
            self.image_label.grid(row=0, column=1, sticky="nsew", rowspan=4)
            self.fullscreen_button = CTkButton(self, text="", width=40, height=40, image=img_full_screen, fg_color="transparent")
            self.fullscreen_button.grid(row=0, column=2, padx=5, pady=(5,0), sticky="ne")
            self.pause_button = CTkButton(self, text="", width=30, height=40, image=img_pause, fg_color="transparent", command=self.stop_camera)
            self.pause_button.grid(row=0, column=0, padx=5, pady=(5,0), sticky="nw")
            self.play_button = CTkButton(self, text="", width=30, height=40,  image=img_play, fg_color="transparent", command=self.start_camera)
            self.play_button.grid(row=0, column=0, padx=5, pady=(5,0), sticky="nw")
            self.save_button = CTkButton(self, text="", width=30, height=40, image=img_save, fg_color="transparent", command=self.save_image)
            self.save_button.grid(row=1, column=0, padx=5, pady=(5,0), sticky="nw")

            self.current_image = None
            if self.camera.enable: 
                self.start_camera()
        else:
            self.master.notification(f"Unable to connect to {self.camera.name} {self.camera.serial}", color="#8e0101")


    def start_camera(self):
        self.image_queue = self.camera.run()
        self.pause_button.lift()
        self.update_image()


    def stop_camera(self):
        self.camera.stop()
        self.play_button.lift()


    def update_image(self):
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
            self.after(20, self.update_image)


    def on_resize(self, event):
        if self.resize_after_id:
            self.after_cancel(self.resize_after_id)
        self.resize_after_id = self.after(20, self.resize_image)


    def resize_image(self):
        if self.aspect_ratio:
            frame_width = int(self.master.winfo_width() /3)
            frame_height = int(self.master.winfo_height() /3)

            if frame_width / frame_height > self.aspect_ratio:
                self.image_height = frame_height
                self.image_width = int(self.image_height * self.aspect_ratio)
            else:
                self.image_width = frame_width
                self.image_height = int(self.image_width / self.aspect_ratio)


    def save_image(self):
        if self.current_image:
            file_path = self.master.directory_frame.get_camera_directory()
            if file_path:
                try:
                    self.current_image.save(file_path)
                    self.master.directory_frame.get_camera_directory(update_placeholder=True)
                    self.master.notification(f"Successfully saved as", file_path, "#1a8300")
                    print(f"Image saved to {file_path}")
                except Exception as e:
                    print(f"Error saving image: {e}")
                    self.master.notification(f"Impossible to save as", file_path, "#8e0101")
            else:
                self.master.notification(f"No directory to save", color="#8e0101")
        else:
            self.master.notification(f"No image to save", color="#8e0101")