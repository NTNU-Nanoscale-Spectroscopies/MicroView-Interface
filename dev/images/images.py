from customtkinter import *
from PIL import Image, UnidentifiedImageError
import os
import sys


def set_working_directory():
    """Adjusts the project's working directory to ensure it uses the correct base path,
    especially when compiled into an executable
    """
    try:
        base_path = sys._MEIPASS
        os.chdir(base_path)
    except AttributeError:
        pass

set_working_directory()


def load_image(size, light_filename, dark_filename=None, path="dev/images/"):
    """Loads the requested image, then returns a CustomTkinter image

    Parameters
    ------------
    size : `tuple(width, height)`
        Image size
    light_filename : `str`
        Image name in light mode
    dark_filename : `str`, optional
        Image name in dark mode, by default None
    path : `str`, optional
        Path to image folder, by default `dev/images/`

    Returns
    ---------
    load_image : `CTkImage`
        returns a CustomTkinter image
    """
    try:
        light_image_data = Image.open(f"{path}light-mode/{light_filename}")
    except (FileNotFoundError, UnidentifiedImageError) as e:
        print(f"Error loading image {light_filename}: {e}")
        light_image_data = None

    try:
        dark_image_data  = Image.open(f"{path}night-mode/{dark_filename}") if dark_filename else light_image_data
    except (FileNotFoundError, UnidentifiedImageError) as e:
        print(f"Error loading image {dark_filename}: {e}")
        dark_image_data = None
        
    try:
        return CTkImage(light_image_data, dark_image_data, size)
    except ValueError:
        # no image available, return None so callers can handle gracefully
        return None


img_microscope = load_image((150, 150), 'microscope_black.png', 'microscope_white.png')
img_apparence_color_theme = load_image((30, 30), 'moon_icon_black.png', 'sun_icon_white.png')
img_play = load_image((25, 25), 'play_icon_black.png', 'play_icon_white.png')
img_pause = load_image((25, 25), 'pause_icon_black.png', 'pause_icon_white.png')
img_save = load_image((25, 25), 'save_icon_black.png', 'save_icon_white.png')
img_advanced_save = load_image((25, 25), 'advanced_save_icon_black.png', 'advanced_save_icon_white.png')
img_rescale = load_image((25, 25), 'rescale_icon_black.png', 'rescale_icon_white.png')
img_full_screen = load_image((20, 20), 'full_screen_icon_black.png', 'full_screen_icon_white.png')
img_retry = load_image((25, 25), 'retry_icon_grey.png')
img_info = load_image((15, 15), 'info_icon_black.png', 'info_icon_white.png')
img_plus = load_image((15, 15), 'plus_icon_black.png', 'plus_icon_white.png')
img_bulb_on = load_image((25, 25), 'bulb_on_icon_black.png', 'bulb_on_icon_white.png')
img_bulb_off = load_image((25, 25), 'bulb_off_icon_black.png', 'bulb_off_icon_white.png')
img_cogwheel = load_image((18, 18), 'cogwheel_icon_black.png', 'cogwheel_icon_white.png')
img_split = load_image((20, 20), 'split_screen_black.png', 'split_screen_white.png')
img_split_full = load_image((20, 20), 'split_screen_full_black.png', 'split_screen_full_white.png')
img_split_left = load_image((20, 20), 'split_screen_left_black.png', 'split_screen_left_white.png')
img_split_right = load_image((20, 20), 'split_screen_right_black.png', 'split_screen_right_white.png')
img_new_experiment = load_image((25, 25), 'new_experiment_black.png', 'new_experiment_white.png')
img_auto_calibration = load_image((20, 20), 'compass_black.png', 'compass_white.png')
img_open_folder = load_image((20, 20), 'folder-into_black.png', 'folder_into_white.png')