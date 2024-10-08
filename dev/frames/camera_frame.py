from dev.images.images import *
from PIL import Image, ImageTk
import customtkinter as ctk
import queue


class CameraFrame(ctk.CTkFrame):
    def __init__(self, master, camera):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        if not camera:
            self.label = ctk.CTkLabel(self, text="No camera", font=("Arial", 25))
            self.label.grid(row=3, column=0, padx=5, pady=5)
            return
        
        if not camera.connection():
            self.label = ctk.CTkLabel(self, text="Disconnected", font=("Arial", 25))
            self.label.grid(row=3, column=0, padx=5, pady=5)
            self.button = ctk.CTkButton(self, text="", width=30, height=40,  image=img_retry, fg_color="transparent", command=camera.connection)
            self.button.grid(row=3, column=0, padx=5, pady=(75, 0))
            return
        
        self.camera = camera
        self.image_queue = None
        self.is_running = False

        self.image_label = ctk.CTkLabel(self, text="")
        self.image_label.grid(row=0, column=0, sticky="nsew", rowspan=4)

        self.aspect_ratio = None
        self.bind("<Configure>", self.on_resize)
        self.resize_after_id = None

        self.fullscreen_button = ctk.CTkButton(self, text="", width=30, height=40, image=img_full_screen, fg_color="transparent")
        self.fullscreen_button.grid(row=0, column=0, padx=5, pady=(5,0), sticky="ne")
        self.play_button = ctk.CTkButton(self, text="", width=30, height=40,  image=img_play, fg_color="transparent", command=self.start_camera)
        self.play_button.grid(row=0, column=0, padx=5, pady=(5,0), sticky="nw")
        self.pause_button = ctk.CTkButton(self, text="", width=30, height=40, image=img_pause, fg_color="transparent", command=self.stop_camera)
        self.pause_button.grid(row=1, column=0, padx=5, pady=(5,0), sticky="nw")
        self.save_button = ctk.CTkButton(self, text="", width=30, height=40, image=img_save, fg_color="transparent")
        self.save_button.grid(row=2, column=0, padx=5, pady=(5,0), sticky="nw")
        self.current_image = None


    def start_camera(self):
        if self.camera.connected:
            self.image_queue = self.camera.run()
            self.is_running = True
            self.update_image()


    def stop_camera(self):
        self.camera.stop()
        self.is_running = False


    def update_image(self):
        if self.is_running and self.image_queue:
            try:
                self.current_image = self.image_queue.get_nowait()
                if not self.aspect_ratio:
                    image_width, image_height = self.current_image.size
                    self.aspect_ratio = image_width / image_height
                self.resize_image()
                # self.image_label.image = CTkImage(self.current_image, size=(300, 200))
            except queue.Empty:
                pass
            self.after(20, self.update_image)


    def on_resize(self, event):
        if self.resize_after_id:
            self.after_cancel(self.resize_after_id)
        self.resize_after_id = self.after(10, self.resize_image)


    def resize_image(self):
        if self.current_image and self.aspect_ratio:
            frame_width = int(self.master.winfo_width() /2.4)
            frame_height = int(self.master.winfo_height() /2.4)

            if frame_width / frame_height > self.aspect_ratio:
                new_height = frame_height
                new_width = int(new_height * self.aspect_ratio)
            else:
                new_width = frame_width
                new_height = int(new_width / self.aspect_ratio)

            resized_image = self.current_image.resize((new_width, new_height), Image.LANCZOS)
            tk_image = ImageTk.PhotoImage(resized_image)
            self.image_label.configure(image=tk_image)
            self.image_label.image = tk_image