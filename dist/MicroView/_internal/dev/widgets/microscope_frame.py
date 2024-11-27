from ..images.images import *


class MicroscopeFrame(CTkFrame):
    def __init__(self, master, microscopes):
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(0, weight=1)
        self.microscopes = microscopes
        self.buttons = []

        for i, microscope in enumerate(self.microscopes):
            button = CTkButton(self, text=microscope.name, width=300, height=300, image=img_microscope, compound="top", font=("Arial", 20), text_color=["grey14","grey90"], command= lambda m=microscope: master.goToMicroscope(m))
            button.grid(row=0, column=i, padx=10, pady=10)
            self.grid_columnconfigure(i, weight=1)
            self.buttons.append(button)