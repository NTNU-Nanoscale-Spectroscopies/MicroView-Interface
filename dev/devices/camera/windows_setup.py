import os

def configure_path():
    """Change the PATH environment variable (Just for the current process, 
    not the system PATH variable) to the dlls ThorCam dlls required for camera operation
    """
    relative_path_to_dlls = 'dlls' + os.sep
    absolute_path_to_file_directory = os.path.dirname(os.path.abspath(__file__))
    absolute_path_to_dlls = os.path.abspath(absolute_path_to_file_directory + os.sep + relative_path_to_dlls)
    os.environ['PATH'] = absolute_path_to_dlls + os.pathsep + os.environ['PATH']

    try:
        os.add_dll_directory(absolute_path_to_dlls)
    except AttributeError:
        pass
