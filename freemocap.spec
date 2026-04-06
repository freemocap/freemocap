# -*- mode: python ; coding: utf-8 -*-

import sys
sys.setrecursionlimit(sys.getrecursionlimit() * 5)

from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_submodules
import cv2
import os

datas = []
binaries = []
hiddenimports = ["encodings.idna"]

# ── OpenCV ──
binaries.extend(collect_dynamic_libs('cv2'))
hiddenimports.extend(collect_submodules('cv2'))

# ── scipy (uses lazy loading that breaks in frozen envs) ──
scipy_datas, scipy_binaries, scipy_hidden = collect_all('scipy')
datas.extend(scipy_datas)
binaries.extend(scipy_binaries)
hiddenimports.extend(scipy_hidden)

# ── mediapipe (needs .tflite model files at runtime) ──
import mediapipe
mp_path = os.path.dirname(mediapipe.__file__)
datas.append((os.path.join(mp_path, 'modules'), 'mediapipe/modules'))
hiddenimports.extend(collect_submodules('mediapipe'))

# ── skellyforge (yaml config files needed at runtime) ──
import skellyforge
sf_path = os.path.dirname(skellyforge.__file__)
datas.append((os.path.join(sf_path, 'skellymodels', 'tracker_info', '*.yaml'), 'skellyforge/skellymodels/tracker_info'))

# ── setuptools (needed by some vendored deps at runtime) ──
setuptools_datas, _, setuptools_hidden = collect_all('setuptools')
datas.extend(setuptools_datas)
hiddenimports.extend(setuptools_hidden)

# Ensure jaraco.text lorem ipsum file is included
jaraco_text_path = os.path.join(
    os.path.dirname(__import__('setuptools', fromlist=['_vendor']).__file__),
    '_vendor', 'jaraco', 'text'
)
datas.append((os.path.join(jaraco_text_path, '*.txt'), 'setuptools/_vendor/jaraco/text/'))

a = Analysis(
    ['freemocap/__main__.py'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # ── Test frameworks ──
        'pytest',
        'pytest_asyncio',
        '_pytest',

        # ── Dev/build tools ──
        'nuitka',
        'ruff',
        'bumpver',
        'pip_tools',
        'poethepoet',
        'pyinstaller',

        # ── Heavy unused modules ──
        'torch',
        'tkinter',
        '_tkinter',
        'IPython',
        'notebook',
        'sphinx',
        'docutils',

        # ── Debug/profile tools ──
        'pdb',
        'cProfile',
        'profile',
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='freemocap_server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
