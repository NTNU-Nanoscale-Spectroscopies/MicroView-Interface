# -*- mode: python ; coding: utf-8 -*-

import glob
import os

datas = [
    ('dev/images', 'dev/images'),
    ('dev/themes', 'dev/themes'),
    ('dev/devices/camera/dlls', 'dev/devices/camera/dlls'),
    ('dev/devices/shutter/dlls', 'dev/devices/shutter/dlls'),
]

# Collect native/managed DLLs that should be placed next to the exe so
# Windows loader and pythonnet can find them at runtime. Each tuple is
# (source_path, dest_dir) where dest_dir='.' places files beside the exe.
binaries = []
for pattern in (
    os.path.join('dev', 'devices', 'camera', 'dlls', '*.dll'),
    os.path.join('dev', 'devices', 'shutter', 'dlls', '*.dll'),
):
    for f in glob.glob(pattern):
        # Use the raw path for pyinstaller; dest '.' puts the DLL next to the exe
        binaries.append((f, '.'))

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=['clr.style_builder', 'clr', 'colorama', 'clr.style'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='MicroView V.3.1.0',
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