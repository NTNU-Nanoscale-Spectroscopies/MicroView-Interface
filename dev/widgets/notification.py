from customtkinter import *
import sys

class Notification(CTkToplevel):
    
    def __init__(self, head_message=None, message=None, border_color=None, time_before_delete=3000, alpha=0.90, width=400, height=75, corner_radius=25, border_width=2, cancel_button=True, **kwargs):
        super().__init__()

        self.overrideredirect(True)
        self.width = width
        self.height = height
        self.alpha = alpha
        self.attributes('-alpha', 0)
        
        if sys.platform.startswith("win"):
            self.transparent_color = self._apply_appearance_mode(self._fg_color)
            self.attributes("-transparentcolor", self.transparent_color)
        elif sys.platform.startswith("darwin"):
            self.transparent_color = 'systemTransparent'
            self.attributes("-transparent", True)
        else:
            self.attributes("-type", "splash")
            self.transparent_color = '#000001'
            corner_radius = 0
            self.withdraw()

        self.frame = CTkFrame(self, bg_color=self.transparent_color, corner_radius=corner_radius, border_width=border_width, border_color=border_color, **kwargs)
        self.frame.pack(expand=True, fill="both")
        
        self.text_frame = CTkFrame(self.frame, fg_color="transparent")
        self.text_frame.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=12)

        self.head_label = CTkLabel(self.text_frame, text=head_message, font=("Arial", 14))
        self.head_label.pack(anchor="w", side=None if message else "left")
        self.message_label = CTkLabel(self.text_frame, text=message, font=("Arial", 10))
        self.message_label.pack(anchor="w")

        if cancel_button:
            self.button_frame = CTkFrame(self.frame, fg_color="transparent")
            self.button_frame.pack(side="top", anchor="ne", padx=7+border_width, pady=7+border_width)
            self.button_close = CTkButton(self.button_frame, corner_radius=10, width=0, height=0, hover=False, text_color=self.frame._border_color, text="✕", fg_color="transparent", command=self.destroy_annim)
            self.button_close.pack()

        self.resizable(width=False, height=False)
        self.transient(self.master)
        self.update_idletasks()
        
        self.x = int(self.master.winfo_width() + self.master.winfo_x() - self.width * 1.49)
        self.y = int(self.master.winfo_height() + self.master.winfo_y() - self.height)
    
        self._iconify()
        self.attributes('-alpha', alpha)
        self.after(time_before_delete, self.destroy_annim)
        
    def _iconify(self):
        self.deiconify()
        self.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")

    def destroy_annim(self):
        self.alpha -= .1
        self.attributes('-alpha', self.alpha)
        if self.alpha <= 0:
            self.master.notif_list.remove(self)
            self.destroy()
            for notif in self.master.notif_list[:]: 
                notif.move()
        else:
            self.after(40, self.destroy_annim)

    def move(self):
        if self in self.master.notif_list:
            index = self.master.notif_list.index(self)
            self.x = int(self.master.winfo_width() + self.master.winfo_x() - self.width * 1.49)
            self.y = int(self.master.winfo_height() + self.master.winfo_y() - self.height - self.height * 1.6 * index)
            self._iconify()
