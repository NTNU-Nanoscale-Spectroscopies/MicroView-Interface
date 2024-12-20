from ..images.images import *


class MicroscopeFrame(CTkFrame):
    """Class for creating a frame with a button for each microscope"""

    def __init__(self, master, microscopes):
        """Create a frame in the main window with a button for each microscope.
        Users can choose wich microscope to use

        Parameters
        ------------
        master : `CTk`
            Main window
        microscopes : `list(MyMicroscope)`
            List of all microscopes with all components/devices
        """
        super().__init__(master, fg_color="transparent")
        self.grid_rowconfigure(0, weight=1)
        self.microscopes = microscopes
        self.buttons = []

        for i, microscope in enumerate(self.microscopes):
            button = CTkButton(self, text=microscope.name, width=300, height=300, image=img_microscope, compound="top", font=("Arial", 20), text_color=["grey14","grey90"], command= lambda m=microscope: master.go_to_microscope(m))
            button.grid(row=0, column=i, padx=10, pady=10)
            self.grid_columnconfigure(i, weight=1)
            self.buttons.append(button)