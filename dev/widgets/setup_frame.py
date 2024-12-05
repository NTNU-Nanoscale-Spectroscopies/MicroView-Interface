from .notification import *
from ..images.images import *
from ..devices.camera.camera import *
from ..devices.spectrometer import *
from ..devices.shutter.shutter import *
from ..devices.laser import *
from ..devices.filter import *
from ..devices.platform import *

class QuickSetupFrame(CTkScrollableFrame):
    def __init__(self, master, microscope):
        super().__init__(master)

        self.switch_list = []
        for i, device in enumerate(microscope.devices):

            frame = CTkFrame(self)
            frame.grid(row=i, column=0, sticky="nsew")
            switch = CTkSwitch(frame, text=device.name, font=("Arial", 20))
            switch.pack(side="left", padx=(30,10), pady=20)

            master_frame = None
            widget_to_disable = []

            if isinstance(device, MyCamera):
                master_frame = self.master.master.master.camera_frame
                
            elif isinstance(device, MySpectrometer):
                master_frame = self.master.master.master.spectrometer_frame
                entry = CTkEntry(frame, width=100, placeholder_text=device.integration_time/1000)
                button = CTkButton(frame, text="Set", width=30, state="disabled", command=lambda d=device, e=entry: self.check_valide_entry(d,e))
                label = CTkLabel(frame, text="ms")
                button.pack(side="left", padx=(10,5))
                entry.pack(side="left")
                label.pack(side="left", padx=3)
                entry.configure(state="disabled")
                widget_to_disable.append(button)
                widget_to_disable.append(entry)

            elif isinstance(device, MyLaser):
                info = CTkButton(frame, text="", corner_radius=50, width=15, image=img_info, fg_color="transparent")
                info.pack(side="left")
                widget_to_disable.append(info)
                if device.shutter:
                    button = CTkButton(frame, text="Close", state="disabled", width=70, fg_color="transparent", border_width=2, border_color="#920000", hover_color="#4b0000")
                    button.configure(command=lambda d=device.shutter, b=button: self.toggle_shutter(d,b))
                    button.pack(side="left")
                    widget_to_disable.append(button)

            elif isinstance(device, MyFilter):
                pass

            elif isinstance(device, MyPlatform):
                pass

            elif isinstance(device, MyShutter):
                button = CTkButton(frame, text="Close", state="disabled", width=70, fg_color="transparent", border_width=2, border_color="#920000", hover_color="#4b0000")
                button.configure(command=lambda d=device, b=button: self.toggle_shutter(d,b))
                button.pack(side="left")
                widget_to_disable.append(button)

            self.switch_list.append((switch, device, master_frame, widget_to_disable))
            switch.configure(command=lambda d=device, s=switch, m=master_frame: self.toggle_device(d,s,m))

        self.update_idletasks()
        self.required_height_for_scrollbar = (i+1) * frame.winfo_height()
        self.previous_frame_height = self.master.winfo_height()
        self.master.bind("<Configure>", lambda event: self.update_scrollbar_visibility())
        self.after(200, self.init)


    def init(self):
        spectrometer_already_open = False
        for switch, device, master_frame, widget_to_disable in self.switch_list:
            if isinstance(device, MySpectrometer) and spectrometer_already_open: continue
            element = master_frame or device
            if not element.connect():
                self.notification(f"Unable to connect to {device.name} {device.serial}", color="#8e0101")
            elif isinstance(device, MySpectrometer):
                spectrometer_already_open = True
        self.check_connected_devices()


    def check_connected_devices(self):
        for switch, device, master_frame, widget_to_disable in self.switch_list:
            if device.connected:
                switch.select()
                state = "normal"
            else:
                switch.deselect()
                state = "disabled"

            for widget in widget_to_disable:
                widget.configure(state=state)


    def toggle_device(self, device, switch, master_frame):
        element = master_frame or device
        if isinstance(device, MySpectrometer):
            if element.spectrometer != device:
                element.disconnect()
                element.spectrometer = device

        if switch.get():
            if not element.connect():
                self.notification(f"Unable to connect to {device.name} {device.serial}", color="#8e0101")
        else:
            element.disconnect()
        self.check_connected_devices()


    def reconnection(self, frame_device):
        for switch, device, master_frame, widget_to_disable in self.switch_list:
            if device == frame_device:
                switch.select()
                self.toggle_device(device, switch, master_frame)


    def toggle_shutter(self, device, widget):
        if device.state():    
            device.close()
            widget.configure(text="Close", border_color="#920000", hover_color="#4b0000")
        else:
            device.open()
            widget.configure(text="Open", border_color="#009200", hover_color="#004b00")


    def check_valide_entry(self, device, entry):
        try:
            value = float(entry.get())
            if 8 <= value <= 1600000:
                device.set_integration_time(value * 1000)
                self.notification(f"Integration time set at {value} ms", "#1a8300")
            else:
                self.notification(f"Integration time must be between 8 ms and 1600000 ms", "#8e0101")
        except:
            self.notification(f"Integration time must be a number", "#8e0101")


    def update_scrollbar_visibility(self):
        current_height = self.master.winfo_height()
        if current_height != self.previous_frame_height:
            self.previous_frame_height = current_height
            if self.required_height_for_scrollbar > current_height:
                self._scrollbar.grid(column= 1, row= 1, pady= 6, sticky= "nesw")
            else:
                self._scrollbar.grid_forget()


    def notification(self, head_message=None, color=None, message=None):
        self.master.master.master.notification(head_message, message, color)