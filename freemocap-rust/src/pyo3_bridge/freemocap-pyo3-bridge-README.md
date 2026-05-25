# freemocap-pyo3-bridge

Python entry point for the freemocap engine. Compiles as a `cdylib` loaded by Python via `import _freemocap_rust`.

## Module Structure

```
#[pymodule] fn _freemocap_rust
  └── PyPipeline  (pyclass)
        ├── new(camera_group_manager, group_id, config_json, camera_ids)
        ├── start()
        ├── shutdown()
        ├── update_config(config_json)
        ├── get_latest_output() → dict | None
        ├── camera_ids() → list[str]
        └── alive() → bool
```

## Python Usage

```python
import _freemocap_rust

# camera_group_manager is a _skellycam_rust.CameraGroupManager instance
pipeline = _freemocap_rust.Pipeline(
    camera_group_manager,  # PyO3 CameraGroupManager from skellycam
    "group_abc",           # camera group ID
    config_json,           # PipelineConfig as JSON string
    ["cam_1", "cam_2"],    # camera IDs
)

pipeline.start()

# Poll for output
output = pipeline.get_latest_output()
if output:
    print(f"Frame {output['frame_number']} ready")
    payload = output['frontend_payload']  # bytes

# Update config at runtime
pipeline.update_config(new_config_json)

pipeline.shutdown()
```

## FrameSlots Extraction

`PyPipeline::new()` internally extracts `FrameSlots` from the skellycam `PyO3CameraGroupManager`:

```rust
let bound = camera_group_manager.bind(py);
let cam_mgr = bound.cast::<PyO3CameraGroupManager>()?;
let frame_slots = cam_mgr.borrow().get_frame_slots(&group_id)?;
```

This is Rust-to-Rust — no frame data crosses the Python boundary. The `FrameSlots` are `Arc` clones of the same slots the skellycam dispatcher writes to.

## Build

```bash
maturin develop   # builds + installs into current venv
```

Module name: `_freemocap_rust` (underscore prefix = private implementation detail).

## OpenCV DLL Setup

On Windows, the Python import path must discover OpenCV DLLs before importing:

```python
import os
opencv_bin = "C:/tools/opencv/build/x64/vc16/bin"
if os.path.isdir(opencv_bin):
    os.add_dll_directory(opencv_bin)

import _freemocap_rust
```
