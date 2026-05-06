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

# ── scipy (targeted: only submodules actually imported at runtime) ──
binaries.extend(collect_dynamic_libs('scipy'))
hiddenimports.extend([
    'scipy.optimize',
    'scipy.sparse',
    'scipy.linalg',
    'scipy.spatial.transform',
    'scipy.interpolate',
    'scipy.cluster.hierarchy',
    'scipy.cluster.vq',
    'scipy.signal',
])

# ── pandas (standard hook handles most; _cyutility missed by default hook) ──
binaries.extend(collect_dynamic_libs('pandas'))
hiddenimports.append('pandas._libs._cyutility')

# ── mediapipe (needs .tflite model files at runtime; only solutions/vision/formats) ──
import mediapipe
mp_path = os.path.dirname(mediapipe.__file__)
datas.append((os.path.join(mp_path, 'modules'), 'mediapipe/modules'))
hiddenimports.extend([
    'mediapipe',
    'mediapipe.python.solutions',
    'mediapipe.python.solutions.holistic',
    'mediapipe.python.solutions.drawing_utils',
    'mediapipe.python.solutions.face_mesh',
    'mediapipe.python.solutions.face_mesh_connections',
    'mediapipe.framework.formats',
    'mediapipe.framework.formats.landmark_pb2',
    'mediapipe.tasks.python',
    'mediapipe.tasks.python.vision',
])

# ── skellyforge (yaml config files needed at runtime) ──
import skellyforge
sf_path = os.path.dirname(skellyforge.__file__)
datas.append((os.path.join(sf_path, 'skellymodels', 'tracker_info', '*.yaml'), 'skellyforge/skellymodels/tracker_info'))

# ── skellytracker (active trackers only; exclude v1 legacy, tests, scripts) ──
datas.extend(collect_data_files('skellytracker', includes=['**/*.yaml']))
hiddenimports.extend([
    'skellytracker',
    'skellytracker.system',
    'skellytracker.system.logging_configuration',
    'skellytracker.system.logging_configuration.handlers',
    'skellytracker.system.logging_configuration.handlers.websocket_log_queue_handler',
    'skellytracker.io',
    'skellytracker.io.process_videos',
    'skellytracker.io.process_videos.process_single_video',
    'skellytracker.utilities',
    'skellytracker.tracked_object_definition',
    'skellytracker.trackers.mediapipe_tracker',
    'skellytracker.trackers.rtmpose_tracker',
    'skellytracker.trackers.rtmpose_tracker.__rtmpose_tracker',
    'skellytracker.trackers.rtmpose_tracker.run_rtmpose',
    'skellytracker.trackers.charuco_tracker',
    'skellytracker.trackers.brightest_point_tracker',
])

# ── NVIDIA CUDA runtime (bundled so users don't need a system CUDA install) ──
# skellytracker's rtmpose_detector does `find_spec("nvidia")` +
# `nvidia_root.glob("*/bin")` at runtime to discover CUDA libraries.
#
# Included — required by ONNX Runtime CUDA execution provider:
#   nvidia.cublas       (737 MB) — GEMM/BLAS for GPU tensor ops
#   nvidia.cuda_runtime  (11 MB) — core CUDA runtime (cudart)
#   nvidia.cudnn       (1006 MB) — cuDNN: primitives for deep neural network inference
#
# Excluded — only needed by TensorRT EP (not currently functional):
#   nvidia.cufft        (275 MB) — FFT library, not used by ONNX inference
#   nvidia.cuda_nvrtc   (179 MB) — runtime compilation, TensorRT-only
#   nvidia.nvjitlink     (84 MB) — JIT linker, TensorRT-only
for nvidia_subpkg in [
    'nvidia.cublas',
    'nvidia.cuda_runtime',
    'nvidia.cudnn',
]:
    try:
        nv_datas, nv_binaries, nv_hidden = collect_all(nvidia_subpkg)
        datas.extend(nv_datas)
        binaries.extend(nv_binaries)
        hiddenimports.extend(nv_hidden)
    except Exception as e:
        print(f"[freemocap.spec] WARNING: could not collect '{nvidia_subpkg}' "
              f"— GPU acceleration may not work in the frozen build. ({e})")

# ── onnxruntime (GPU build — only DLLs + capi bindings; exclude dev tools) ──
binaries.extend(collect_dynamic_libs('onnxruntime'))
hiddenimports.extend(['onnxruntime', 'onnxruntime.capi'])

# ── rtmlib (model registry + configs) ──
rtm_datas, rtm_binaries, rtm_hidden = collect_all('rtmlib')
datas.extend(rtm_datas)
binaries.extend(rtm_binaries)
hiddenimports.extend(rtm_hidden)

# ── onnx (used by rtmpose_session for model loading; separate from onnxruntime) ──
hiddenimports.append('onnx')

# ── setuptools (_vendor only — jaraco, packaging, etc. needed by vendored deps) ──
hiddenimports.extend(collect_submodules('setuptools._vendor'))
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

        # ── Dependencies in pyproject.toml but never imported ──
        'numba',
        'llvmlite',
        'libsass',
        'sass',
        'sklearn',
        'numpydantic',

        # ── onnxruntime dev tools (not needed at runtime) ──
        'onnxruntime.transformers',
        'onnxruntime.tools',
        'onnxruntime.quantization',
        'onnxruntime.backend',
        'onnxruntime.datasets',

        # ── mediapipe dev/bundled tools ──
        'mediapipe.tasks.python.test',
        'mediapipe.tasks.python.metadata',
        'mediapipe.tasks.python.benchmark',

        # ── skellytracker legacy/unused ──
        'skellytracker.tests',
        'skellytracker.trackers.v1',
        'skellytracker.trackers.vitpose_tracker',
        'skellytracker.trackers.legacy_mediapipe_tracker',
        'skellytracker.scripts',
        'skellytracker.__main__',

        # ── setuptools cruft ──
        'setuptools.tests',
        'setuptools.command',
        'setuptools._distutils.command',
        'setuptools._distutils.tests',
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
    upx=True,
    upx_exclude=['nvcuda', 'nvrtc', 'cudnn', 'cublas', 'cufft', 'cudart'],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
