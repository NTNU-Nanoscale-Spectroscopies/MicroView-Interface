import os
import sys


_SDK_PACKAGES = ("pyAndorSDK2", "pyAndorSpectrograph")


def get_sdk_root():
    """Return the local folder that contains the vendored Andor packages."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "andor_sdk")


def get_sdk_package_dirs():
    """Return the vendored Andor package directories."""
    sdk_root = get_sdk_root()
    return [os.path.join(sdk_root, package) for package in _SDK_PACKAGES]


def get_dll_dirs():
    """Return Windows DLL folders used by the vendored Andor wrappers."""
    arch_dir = "64" if sys.maxsize > 2**32 else "32"
    dll_dirs = []

    for package_dir in get_sdk_package_dirs():
        libs_dir = os.path.join(package_dir, "libs")
        dll_dirs.append(libs_dir)

        windows_dir = os.path.join(libs_dir, "Windows", arch_dir)
        if os.path.isdir(windows_dir):
            dll_dirs.append(windows_dir)

    return dll_dirs


def _prepend_once(path_list, path):
    if path and os.path.isdir(path) and path not in path_list:
        path_list.insert(0, path)


def configure_path():
    """Configure imports and Windows DLL lookup for the vendored Andor SDK.

    The Andor Python wrappers import as top-level packages:
    ``pyAndorSDK2`` and ``pyAndorSpectrograph``.  Adding ``andor_sdk`` to
    ``sys.path`` keeps those imports local to this project.
    """
    sdk_root = get_sdk_root()
    _prepend_once(sys.path, sdk_root)

    path_parts = os.environ.get("PATH", "").split(os.pathsep)
    for dll_dir in reversed(get_dll_dirs()):
        _prepend_once(path_parts, dll_dir)

        try:
            os.add_dll_directory(dll_dir)
        except (AttributeError, FileNotFoundError, OSError):
            pass

    os.environ["PATH"] = os.pathsep.join(path_parts)
    return sdk_root
