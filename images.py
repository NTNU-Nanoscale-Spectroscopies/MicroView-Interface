from customtkinter import *
from PIL import Image, UnidentifiedImageError

class MyImageManager:
    def __init__(self, path=""):
        self.path = path
        self.images = {}
    
    def load_image(self, image_name, size, light_filename, dark_filename=None):
        try:
            light_image_data = Image.open(f"{self.path}img/{light_filename}")
        except (FileNotFoundError, UnidentifiedImageError) as e:
            print(f"Error loading image {light_filename}: {e}")
            light_image_data = None

        try:
            dark_image_data  = Image.open(f"{self.path}img/{dark_filename}") if dark_filename else light_image_data
        except (FileNotFoundError, UnidentifiedImageError) as e:
            print(f"Error loading image {dark_filename}: {e}")
            dark_image_data = None
        
        self.images[image_name] = CTkImage(light_image_data, dark_image_data, size)


    def get_image(self, image_name):
        return self.images.get(image_name, None)

img_manager_01 = MyImageManager()
img_manager_01.load_image('microscope', (150, 150), 'microscope_white.png', 'microscope_black.png')
img_manager_01.load_image('apparence_color_theme', (30, 30), 'light_mode_icon.png', 'night_mode_icon.png')