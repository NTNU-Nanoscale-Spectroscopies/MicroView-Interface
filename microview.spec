# -*- mode: python ; coding: utf-8 -*-

import glob
import os

datas = [
    ('dev/images', 'dev/images'),
    ('dev/themes', 'dev/themes'),
    ('dev/devices/camera/dlls', 'dev/devices/camera/dlls'),
    ('dev/devices/shutter/dlls', 'dev/devices/shutter/dlls'),
    ('dev/devices/Stage/dll_sdk', 'dev/devices/Stage/dll_sdk'),
    ('dev/devices/power_meter/dll_sdk', 'dev/devices/power_meter/dll_sdk'),
    # include the filter wheel SDK folder so FWxC_COMMAND_LIB and its DLLs
    # are available when the application is frozen.
    ('dev/devices/filter_wheel/dll_sdk', 'dev/devices/filter_wheel/dll_sdk'),
    ('dev/devices/spectrograph/andor_sdk', 'dev/devices/spectrograph/andor_sdk'),
]

# Collect native/managed DLLs that should be placed next to the exe so
# Windows loader and pythonnet can find them at runtime. Each tuple is
# (source_path, dest_dir) where dest_dir='.' places files beside the exe.
binaries = []
for pattern in (
    os.path.join('dev', 'devices', 'camera', 'dlls', '*.dll'),
    os.path.join('dev', 'devices', 'shutter', 'dlls', '*.dll'),
    os.path.join('dev', 'devices', 'Stage', 'dll_sdk', '*.dll'),
    os.path.join('dev', 'devices', 'power_meter', 'dll_sdk', '*.dll'),
    os.path.join('dev', 'devices', 'filter_wheel', 'dll_sdk', '*.dll'),
    os.path.join('dev', 'devices', 'spectrograph', 'andor_sdk', 'pyAndorSDK2', 'libs', '*.dll'),
    os.path.join('dev', 'devices', 'spectrograph', 'andor_sdk', 'pyAndorSpectrograph', 'libs', '*.dll'),
    # libusb-1.0.dll is required by pyusb at runtime when seabreeze falls back
    # to the pyseabreeze backend (machines where the spectrometer is bound to
    # WINUSB rather than libusb-win32). pyinstaller-hooks-contrib's runtime
    # hook (pyi_rth_usb.py) only searches sys._MEIPASS for libusb*.dll -- it
    # does NOT fall through to C:\Windows\System32 -- so we must bundle the
    # DLL even if the target machine already has one in System32.
    os.path.join('dev', 'devices', 'libusb', '*.dll'),
):
    for f in glob.glob(pattern):
        # Use the raw path for pyinstaller; dest '.' puts the DLL next to the exe
        binaries.append((f, '.'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        'clr.style_builder', 'clr', 'colorama', 'clr.style',
        'MCM301_COMMAND_LIB', 'MCM301_Type_Define',
        # seabreeze loads its backend lazily by name (seabreeze.use(...)),
        # so pyinstaller can't see the dependency statically. We need both
        # backends bundled so the auto-selector in
        # dev/devices/spectrometer.py can pick whichever works on the target
        # machine: cseabreeze on lab boxes where the QE Pro is bound to
        # libusb-win32 (libusb0), pyseabreeze on machines where Windows uses
        # its inbox WINUSB driver. pyseabreeze's __init__.py statically
        # re-exports everything it needs (api, devices, transport, every
        # feature module), so the top-level package is sufficient.
        'seabreeze.cseabreeze',
        'seabreeze.pyseabreeze',
        # pyusb selects its USB backend at runtime by trying each candidate
        # module in turn -- they're not visible to pyinstaller's static
        # analysis.
        'usb',
        'usb.core',
        'usb.util',
        'usb.backend',
        'usb.backend.libusb1',
        'usb.backend.libusb0',
        'usb.backend.openusb',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# --- Startup splash shown by the bootloader during extraction + Python init ---
splash = Splash(
    'dev/images/splash.png',
    binaries=a.binaries,
    datas=a.datas,
    text_pos=None,              # we baked the text into the image
    text_size=12,
    minify_script=True,
    always_on_top=True,
)

exe = EXE(
    pyz,
    a.scripts,
    splash,                     # <-- include the splash resource
    splash.binaries,            # <-- include splash binaries
    a.binaries,
    a.datas,
    [],
    name='MicroView V.4.0.0',
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    icon='dev/images/MicroView.ico',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
