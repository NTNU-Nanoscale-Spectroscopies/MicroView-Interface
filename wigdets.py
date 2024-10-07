import customtkinter as ctk
from PIL import Image, ImageTk
from img.images import *
import queue

class MicroscopeFrame(ctk.CTkFrame):
    def __init__(self, master, microscopes):
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(0, weight=1)
        self.microscopes = microscopes
        self.buttons = []

        for i, microscope in enumerate(self.microscopes):
            button = ctk.CTkButton(self, text=microscope.name, width=300, height=300, image=img_microscope, compound="top", font=("Arial", 20), text_color=["grey14","grey90"], command= lambda m=microscope: master.goToMicroscope(m))
            button.grid(row=0, column=i, padx=10, pady=10)
            self.grid_columnconfigure(i, weight=1)
            self.buttons.append(button)



class CameraFrame(ctk.CTkFrame):
    def __init__(self, master, camera):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self.camera = camera

        if not camera or not camera.connection():
            self.label = ctk.CTkLabel(self, text="Disconnected", font=("Arial", 25))
            self.label.grid(row=3, column=0, padx=5, pady=5)
            return
        
        self.image_queue = None
        self.is_running = False

        self.image_label = ctk.CTkLabel(self, text="")
        self.image_label.grid(row=0, column=0, sticky="nsew", rowspan=4)

        self.aspect_ratio = None
        self.bind("<Configure>", self.on_resize)
        self.resize_after_id = None

        self.stop_button = ctk.CTkButton(self, text="", width=30, height=40, image=img_full_screen, fg_color="transparent")
        self.stop_button.grid(row=0, column=0, padx=5, pady=(5,0), sticky="ne")
        self.start_button = ctk.CTkButton(self, text="", width=30, height=40,  image=img_play, fg_color="transparent", command=self.start_camera)
        self.start_button.grid(row=0, column=0, padx=5, pady=(5,0), sticky="nw")
        self.stop_button = ctk.CTkButton(self, text="", width=30, height=40, image=img_pause, fg_color="transparent", command=self.stop_camera)
        self.stop_button.grid(row=1, column=0, padx=5, pady=(5,0), sticky="nw")
        self.stop_button = ctk.CTkButton(self, text="", width=30, height=40, image=img_save, fg_color="transparent")
        self.stop_button.grid(row=2, column=0, padx=5, pady=(5,0), sticky="nw")
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
            except queue.Empty:
                pass
            self.after(20, self.update_image)


    def on_resize(self, event):
        if self.resize_after_id:
            self.after_cancel(self.resize_after_id)
        self.resize_after_id = self.after(10, self.resize_image)


    def resize_image(self):
        if self.current_image and self.aspect_ratio:
            frame_width = self.master.winfo_width()
            frame_height = self.master.winfo_height()

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



class SpectrometerFrame(ctk.CTkFrame):
    def __init__(self, master, spectrometer):
        super().__init__(master)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(4, weight=1)
        self.spectrometer = spectrometer
        
        if not spectrometer or not spectrometer.connection():
            self.label = ctk.CTkLabel(self, text="Disconnected", font=("Arial", 25))
            self.label.grid(row=4, column=0, padx=5, pady=5)
            return

        self.stop_button = ctk.CTkButton(self, text="", width=30, height=40, image=img_full_screen, fg_color="transparent")
        self.stop_button.grid(row=0, column=0, padx=5, pady=(5,0), sticky="ne")
        self.start_button = ctk.CTkButton(self, text="", width=30, height=40,  image=img_play, fg_color="transparent")
        self.start_button.grid(row=0, column=0, padx=5, pady=(5,0), sticky="nw")
        self.stop_button = ctk.CTkButton(self, text="", width=30, height=40, image=img_pause, fg_color="transparent")
        self.stop_button.grid(row=1, column=0, padx=5, pady=(5,0), sticky="nw")
        self.stop_button = ctk.CTkButton(self, text="", width=30, height=40, image=img_save, fg_color="transparent")
        self.stop_button.grid(row=2, column=0, padx=5, pady=(5,0), sticky="nw")
        self.stop_button = ctk.CTkButton(self, text="", width=30, height=40, image=img_rescale, fg_color="transparent")
        self.stop_button.grid(row=3, column=0, padx=5, pady=(5,0), sticky="nw")



class DirectoryFrame(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure((0,1,2), weight=1)
        self.label = ctk.CTkLabel(self, text="Choose a directory :", font=("Arial", 14))
        self.label.grid(row=0, column=0, padx=(20,0), pady=(20,5), sticky="w")
        self.label = ctk.CTkLabel(self, text="Camera backup name :", font=("Arial", 14))
        self.label.grid(row=1, column=0, padx=(20,0), pady=5, sticky="w")
        self.label = ctk.CTkLabel(self, text="Spectrometer backup name :", font=("Arial", 14))
        self.label.grid(row=2, column=0, padx=(20,0), pady=(5,20), sticky="w")
        
        self.label = ctk.CTkLabel(self, text="_n°", font=("Arial", 14), text_color="grey50")
        self.label.grid(row=1, column=2, padx=(0,20), pady=5, sticky="w")
        self.label = ctk.CTkLabel(self, text="_n°_date_integrationTime", font=("Arial", 14), text_color="grey50")
        self.label.grid(row=2, column=2, padx=(0,20), pady=(5,20), sticky="w")
        
        self.entry = ctk.CTkEntry(self, fg_color="#EEEEEE", border_color="#00509E", border_width=1)
        self.entry.grid(row=0, column=1, padx=(5,20), pady=(20,5), sticky="ew", columnspan=2)
        self.entry = ctk.CTkEntry(self, fg_color="#EEEEEE", border_color="#00509E", border_width=1)
        self.entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        self.entry = ctk.CTkEntry(self, fg_color="#EEEEEE", border_color="#00509E", border_width=1)
        self.entry.grid(row=2, column=1, padx=5, pady=(5,20), sticky="ew")



class QuickSetupFrame(ctk.CTkFrame):
    pass