# -*- mode: python ; coding: utf-8 -*-

import glob
import os

datas = [
    ('dev/images', 'dev/images'),
    ('dev/themes', 'dev/themes'),
    ('dev/devices/camera/dlls', 'dev/devices/camera/dlls'),
    ('dev/devices/shutter/dlls', 'dev/devices/shutter/dlls'),
    ('dev/devices/Stage/dll_sdk', 'dev/devices/Stage/dll_sdk'),
    # include the filter wheel SDK folder so FWxC_COMMAND_LIB and its DLLs
    # are available when the application is frozen.
    ('dev/devices/filter_wheel/dll_sdk', 'dev/devices/filter_wheel/dll_sdk'),
]

# Collect native/managed DLLs that should be placed next to the exe so
# Windows loader and pythonnet can find them at runtime. Each tuple is
# (source_path, dest_dir) where dest_dir='.' places files beside the exe.
binaries = []
for pattern in (
    os.path.join('dev', 'devices', 'camera', 'dlls', '*.dll'),
    os.path.join('dev', 'devices', 'shutter', 'dlls', '*.dll'),
    os.path.join('dev', 'devices', 'Stage', 'dll_sdk', '*.dll'),
    os.path.join('dev', 'devices', 'filter_wheel', 'dll_sdk', '*.dll'),
):
    for f in glob.glob(pattern):
        # Use the raw path for pyinstaller; dest '.' puts the DLL next to the exe
        binaries.append((f, '.'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=['clr.style_builder', 'clr', 'colorama', 'clr.style',
                   'MCM301_COMMAND_LIB', 'MCM301_Type_Define'],
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
    name='MicroView V.3.5.0 (Beta)',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon='dev/images/MicroView.ico',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)