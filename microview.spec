# -*- mode: python ; coding: utf-8 -*-

block_cipher = None
datas = [
    ('dev/images', 'dev/images'),
    ('dev/devices/camera/camera_sdk', 'dev/devices/camera/camera_sdk'),
    ('dev/devices/camera/dlls', 'dev/devices/camera/dlls'),
    ('dev/themes', 'dev/themes'),
    ('dev/widgets', 'dev/widgets'),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MicroView',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='dev/images/MicroView.ico',
    onefile=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MicroView'
)
