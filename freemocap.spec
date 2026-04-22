# -*- mode: python ; coding: utf-8 -*-

import sys
sys.setrecursionlimit(sys.getrecursionlimit() * 5)

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)
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

# ── pandas (newer versions ship _cyutility that default hook misses) ──
pandas_datas, pandas_binaries, pandas_hidden = collect_all('pandas')
datas.extend(pandas_datas)
binaries.extend(pandas_binaries)
hiddenimports.extend(pandas_hidden)

# ── mediapipe (needs .tflite model files at runtime) ──
import mediapipe
mp_path = os.path.dirname(mediapipe.__file__)
datas.append((os.path.join(mp_path, 'modules'), 'mediapipe/modules'))
hiddenimports.extend(collect_submodules('mediapipe'))

# ── skellyforge (yaml config files needed at runtime) ──
import skellyforge
sf_path = os.path.dirname(skellyforge.__file__)
datas.append((os.path.join(sf_path, 'skellymodels', 'tracker_info', '*.yaml'), 'skellyforge/skellymodels/tracker_info'))

# ── skellytracker (recursive: all YAMLs under the package, any tracker) ──
datas.extend(collect_data_files('skellytracker', includes=['**/*.yaml']))
hiddenimports.extend(collect_submodules('skellytracker'))

# ── NVIDIA CUDA runtime (bundled so users don't need a system CUDA install) ──
# skellytracker's rtmpose_detector does `find_spec("nvidia")` +
# `nvidia_root.glob("*/bin")` at runtime, so the full tree must be preserved.
for nvidia_subpkg in [
    'nvidia.cublas',
    'nvidia.cuda_runtime',
    'nvidia.cuda_nvrtc',
    'nvidia.cudnn',
    'nvidia.cufft',
    'nvidia.nvjitlink',
]:
    try:
        nv_datas, nv_binaries, nv_hidden = collect_all(nvidia_subpkg)
        datas.extend(nv_datas)
        binaries.extend(nv_binaries)
        hiddenimports.extend(nv_hidden)
    except Exception as e:
        print(f"[freemocap.spec] WARNING: could not collect '{nvidia_subpkg}' "
              f"— GPU acceleration may not work in the frozen build. ({e})")

# ── onnxruntime (GPU build — needs provider DLLs bundled explicitly) ──
ort_datas, ort_binaries, ort_hidden = collect_all('onnxruntime')
datas.extend(ort_datas)
binaries.extend(ort_binaries)
hiddenimports.extend(ort_hidden)

# ── rtmlib (model registry + configs) ──
rtm_datas, rtm_binaries, rtm_hidden = collect_all('rtmlib')
datas.extend(rtm_datas)
binaries.extend(rtm_binaries)
hiddenimports.extend(rtm_hidden)

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
