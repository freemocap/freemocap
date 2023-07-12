# -*- mode: python ; coding: utf-8 -*-


block_cipher = None

import sys
import os



a = Analysis(
    ['../freemocap/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[('../freemocap/gui/qt/style_sheet/qt_style_sheet.css','freemocap/gui/qt/style_sheet')],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='freemocap',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
app = BUNDLE(
    exe,
    name='freemocap.app',
    icon=None,
    bundle_identifier=None,
)
