from .notification import *
from ..images.images import *
from ..devices.camera.camera import *
from ..devices.spectrometer import *
from ..devices.whitelight import *
from ..devices.laser import *
from ..devices.filter import *
from ..devices.platform import *

class QuickSetupFrame(CTkScrollableFrame):
    def __init__(self, master, microscope):
        super().__init__(master)

        for i, device in enumerate(microscope.devices.values()):

            frame = CTkFrame(self)
            frame.grid(row=i, column=0, sticky="nsew")
            switch = CTkSwitch(frame, text=device.name, font=("Arial", 20))
            switch.pack(side="left", padx=(30,10), pady=20)

            state = "disabled"
            widget_to_disable = []
            if device.enable and device.connected:
                switch.select()
                state = "normal"

            if isinstance(device, MyCamera): 
                button = CTkButton(frame, text="Calibrate", state=state)
                button.pack(side="left", padx=10, pady=5)
                widget_to_disable.append(button)
                
            elif isinstance(device, MySpectrometer): 
                entry = CTkEntry(frame, width=100, placeholder_text="1000000")
                button = CTkButton(frame, text="Set", width=30, state=state, command=lambda d=device, e=entry: self.check_vailde_entry(d,e))
                label = CTkLabel(frame, text="μs")
                button.pack(side="left", padx=(10,5))
                entry.pack(side="left")
                label.pack(side="left", padx=3)
                entry.configure(state=state)
                widget_to_disable.append(button)
                widget_to_disable.append(entry)

            elif isinstance(device, MyLaser): 
                button = CTkButton(frame, text="", corner_radius=50, width=15, image=img_info, fg_color="transparent")
                button.pack(side="left")

            elif isinstance(device, MyFilter): 
                pass

            elif isinstance(device, MyPlatform): 
                pass

            switch.configure(command=lambda d=device, s=switch, w=widget_to_disable: self.toggle_device(d,s,w))

        self.update_idletasks()
        self.required_height_for_scrollbar = (i+1)*64
        self.previous_frame_height = self.master.winfo_height()
        self.bind("<Configure>", lambda event: self.update_scrollbar_visibility())



    def toggle_device(self, device, switch, widget_to_disable):
        swicth_selected = switch.get()
        state = "normal" if swicth_selected else "disabled"
        for widget in widget_to_disable:
            widget.configure(state=state)


    def check_vailde_entry(self, device, entry):
        try:
            value = int(entry.get())
            if 1000 <= value <= 1000000:
                device.set_integration_time(value)
                self.notification(f"Integration time set at {value}μs", "#1a8300")
            else:
                self.notification(f"Integration time must be between 1000μs and 10000000μs", "#8e0101")
        except:
            self.notification(f"Integration time must be a number", "#8e0101")


    def update_scrollbar_visibility(self):
        current_height = self.master.winfo_height()
        if current_height != self.previous_frame_height:
            self.previous_frame_height = self.master.winfo_height()
            if self.required_height_for_scrollbar > current_height:
                self._scrollbar.grid(column= 1, row= 1, pady= 6, sticky= "nesw")
            else:
                self._scrollbar.grid_forget()


    def notification(self, head_message=None, color=None, message=None):
        self.master.master.master.notification(head_message, message, color)