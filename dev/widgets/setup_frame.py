from .notification import *
from ..images.images import *
from ..devices.camera.camera import *
from ..devices.spectrometer import *
from ..devices.shutter.shutter import *
from ..devices.laser import *
from ..devices.filter import *
from ..devices.stage import *

class QuickSetupFrame(CTkScrollableFrame):
    def __init__(self, master, microscope):
        super().__init__(master)

        self.device_entries = []
        for i, device in enumerate(microscope.devices):

            widgets = []
            master_frame = None
            frame = CTkFrame(self)
            frame.grid(row=i, column=0, sticky="nsew")
            switch = CTkSwitch(frame, text=device.name, font=("Arial", 20))
            switch.pack(side="left", padx=(30,10), pady=20)

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
                widgets.append((button,""))
                widgets.append((entry,""))
                widgets.append((label,"NonDisableable"))

            elif isinstance(device, MyLaser):
                info = CTkButton(frame, text="", corner_radius=50, width=15, image=img_info, fg_color="transparent")
                info.pack(side="left")
                widgets.append((info,""))
                if device.shutter:
                    button = CTkButton(frame, text="Close", state="disabled", width=70, fg_color="transparent", border_width=2, border_color="#920000", hover_color="#4b0000")
                    button.configure(command=lambda d=device.shutter, b=button: self.toggle_shutter(d,b))
                    button.pack(side="left")
                    widgets.append((button,"Shutter"))

            elif isinstance(device, MyFilter):
                pass

            elif isinstance(device, MyStage):
                pass

            elif isinstance(device, MyShutter):
                button = CTkButton(frame, text="Close", state="disabled", width=70, fg_color="transparent", border_width=2, border_color="#920000", hover_color="#4b0000")
                button.configure(command=lambda d=device, b=button: self.toggle_shutter(d,b))
                button.pack(side="left")
                widgets.append((button,"Shutter"))

            self.device_entries.append(DeviceEntry(switch, device, widgets, master_frame))
            switch.configure(command=lambda e=self.device_entries[-1]: self.toggle_device(e))

        self.update_idletasks()
        self.required_height_for_scrollbar = (i+1) * frame.winfo_height()
        self.previous_frame_height = self.master.winfo_height()
        self.master.bind("<Configure>", lambda event: self.update_scrollbar_visibility())
        self.after(200, self.init)


    def init(self):
        spectrometer_already_open = False
        for entry in self.device_entries:
            if isinstance(entry.device, MySpectrometer) and spectrometer_already_open: continue
            element = entry.frame or entry.device
            if not element.connect():
                self.notification(f"Unable to connect to {entry.device.name} {entry.device.serial}", color="#8e0101")
            elif isinstance(entry.device, MySpectrometer):
                spectrometer_already_open = True
        self.check_connected_devices()


    def check_connected_devices(self):
        for entry in self.device_entries:
            entry.activate() if entry.is_device_connected() else entry.desactivate()


    def toggle_device(self, entry):
        element = entry.frame or entry.device
        if isinstance(entry.device, MySpectrometer):
            if element.spectrometer != entry.device:
                element.disconnect()
                element.spectrometer = entry.device

        if entry.switch.get():
            if not element.connect():
                self.notification(f"Unable to connect to {entry.device.name} {entry.device.serial}", color="#8e0101")
        else:
            element.disconnect()
        self.check_connected_devices()


    def reconnection(self, frame_device):
        for entry in self.device_entries:
            if entry.device == frame_device:
                entry.switch.select()
                self.toggle_device(entry)
                break


    def toggle_shutter(self, device, button):
        device.close() if device.state() else device.open()
        update_shutter_button_style(button, device)


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



class DeviceEntry:
    def __init__(self, switch, device, widgets=[], frame=None):
        self.switch = switch
        self.device = device
        self.widgets = widgets
        self.frame = frame

    def activate(self):
        self.switch.select()
        self.update_widgets_state("normal")

    def desactivate(self):
        self.switch.deselect()
        self.update_widgets_state("disabled")

    def update_widgets_state(self, state):
        for widget, type in self.widgets:
            if type != "NonDisableable":
                widget.configure(state=state)
            if type == "Shutter":
                update_shutter_button_style(widget, self.device)

    def is_device_connected(self):
        return self.device.connected


def update_shutter_button_style(widget, device):
    if device.state():
        widget.configure(text="Open", border_color="#009200", hover_color="#004b00")
    else:
        widget.configure(text="Close", border_color="#920000", hover_color="#4b0000")
