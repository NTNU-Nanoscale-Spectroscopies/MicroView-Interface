# -*- mode: python ; coding: utf-8 -*-

datas = [
    ('dev/images', 'dev/images'),
    ('dev/themes', 'dev/themes'),
    ('dev/devices/camera/dlls', 'dev/devices/camera/dlls'),
    ('dev/devices/shutter/dlls', 'dev/devices/shutter/dlls'),
]

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
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
    name='MicroView(Test3)',
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