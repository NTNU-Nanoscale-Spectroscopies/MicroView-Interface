from customtkinter import *
import sys


class Notification(CTkToplevel):
    """Class for creating notifications"""

    def __init__(self, head_message=None, message=None, border_color=None, time_before_delete=3, alpha=0.90, width=400, height=50, corner_radius=25, border_width=2, cancel_button=True, path="", **kwargs):
        """Create a notification window to inform users of potential errors

        Create a new CustomTkinter window, unresizable, rounded and without banner.
        After a few seconds, this window is automatically removed with a disappearing animation.
        If another notification is created, the current notification is moved to the top

        Parameters
        ------------
        head_message : `str`, optional
            Main content. None by default
        message : `str`, optional
            Sub-content used to display the path of the last saved file. None by default
        border_color : `str`, optional
            Notification border color. Grey by default
        time_before_delete : `int`, optional
            Delay in second before notification begins to fade out. 3s by default
        alpha : `int`, optional
            Transparency of notification. 0,9 by default (10%)
        width : `int`, optional
            Notification width. 400 pixels by default
        height : `int`, optional
            Notification height. 50 pixels by default
        corner_radius : `int`, optional
            Notification border radius. 25% by default
        border_width : `int`, optional
            Notification border width. 2 pixels by default
        cancel_button : `bool`, optional
            Has a close button. True by default
        """
        super().__init__()
        time_before_delete = int(time_before_delete*1000)
        self.overrideredirect(True)
        self.alpha = alpha
        self.attributes('-alpha', 0)
        self.path = path
        
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

        if head_message:
            width = max(width, len(head_message) * 9)
        if message:
            width = max(width, len(message) * 6)
            height += 25
        self.width = width
        self.height = height

        self.frame = CTkFrame(self, bg_color=self.transparent_color, corner_radius=corner_radius, border_width=border_width, border_color=border_color, **kwargs)
        self.frame.pack(expand=True, fill="both")
                    
        self.text_frame = CTkFrame(self.frame, fg_color="transparent")
        self.text_frame.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=12)

        if self.path != "":
            self.text_frame.bind("<Button-1>", self.click_button)
               
        self.head_label = CTkLabel(self.text_frame, text=head_message, font=("Arial", 14))
        self.head_label.pack(anchor="w", side=None if message else "left")
        self.message_label = CTkLabel(self.text_frame, text=message, font=("Arial", 10))
        self.message_label.pack(anchor="w")

        if cancel_button:
            self.button_frame = CTkFrame(self.frame, fg_color="transparent")
            self.button_frame.pack(side="top", anchor="ne", padx=7+border_width, pady=7+border_width)
            self.button_close = CTkButton(self.button_frame, corner_radius=10, width=0, height=0, hover=False, text_color=self.frame._border_color, text="✕", fg_color="transparent", command=self.remove)
            self.button_close.pack()

        self.resizable(width=False, height=False)
        self.transient(self.master)
        self.update_idletasks()
        self.draw()

        self.attributes('-alpha', alpha)
        self.after(time_before_delete, self.remove)
        
    def remove(self):
        """Triggers the disappearing animation. When the notification is completely transparent, 
        it is removed and all upper notifications are moved to the bottom
        """
        self.alpha -= .1
        self.attributes('-alpha', self.alpha)
        if self.alpha <= 0:
            self.master.notif_list.remove(self)
            self.destroy()
            height_sum = 0
            for notif in self.master.notif_list[:]: 
                notif.draw(height_sum)
                height_sum += notif.winfo_height() + 10
        else:
            self.after(40, self.remove)

    def draw(self, shift=0):
        """Allows to position the notification at the bottom right of the main window 
        according to the position and size of this main window, but also according to 
        other notifications already present.

        Parameters
        ------------
        shift : int, optional
            Notification height offset. 0 by default
        """
        self.x = int(self.master.winfo_width() + self.master.winfo_x() - self.width * self.master.scale)
        self.y = int(self.master.winfo_height() + self.master.winfo_y() - self.height * self.master.scale - shift + 25)
        self.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")

    def click_button(self, event=None):
        os.startfile(os.path.dirname(self.path))