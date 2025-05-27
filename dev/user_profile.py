from .widgets.notification import *

import customtkinter as ctk
class UserProfile(ctk.CTkFrame):
    def __init__(self, parent, username, delete_command, click_command, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.username = username
        self.click_command = click_command
        
        initials = username.upper()
        
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.configure(fg_color="transparent")

        self.profile_button = ctk.CTkButton(self, text=initials, 
                                            width=60, height=60, 
                                            fg_color="#1F6AA5", text_color="white", 
                                            corner_radius=30, font=("Arial", 20, "bold"),
                                            command=lambda: self.click_command(self.username))
        
        self.profile_button.grid(row=0, column=0, pady=10, padx=10, sticky="nsew")

        # self.delete_button = ctk.CTkButton(self, text="🗑", width=25, height=25, 
        #                                    fg_color="red", text_color="white", 
        #                                    font=("Arial", 14, "bold"), 
        #                                    command=lambda: delete_command(self))
        # self.delete_button.grid(row=2, column=0, pady=(0, 5), sticky="se")

        