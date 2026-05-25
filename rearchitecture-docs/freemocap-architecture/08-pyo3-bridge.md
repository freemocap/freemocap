# PyO3 Bridge Pattern

> Step 4 (Design Rust Architecture) — exposing the pipeline engine to Python. Adapted from skellycam's and skellytracker's bridge strategies.

## The Problem

Python code must create and control a Rust pipeline via `_freemocap_rust`. The bridge must handle:
- Pipeline lifecycle (create, start, shutdown, update_config)
- Config serialization (Python Pydantic JSON ↔ Rust serde struct)
- Aggregator output retrieval (Rust struct → Python dict)
- OpenCV DLL discovery on Windows (same as skellytracker)
- Integration with skellycam's PyO3 objects (receiving `PyO3CameraGroupManager`)

### Invariants

- Python calls `pipeline = _freemocap_rust.Pipeline(manager, config_json, camera_ids)`
- Config updates via `pipeline.update_config(config_json)`
- Output retrieval via `pipeline.get_latest_output() → dict | None`
- OpenCV DLLs found via `os.add_dll_directory()` — no PATH manipulation
- Build is a single `poe rebuild` command (maturin via uv)

## Architecture

```
┌─ Python (site-packages) ─────────────────────────────────┐
│  import _freemocap_rust                                    │
│  pipeline = _freemocap_rust.Pipeline(                      │
│      camera_group_manager,                                 │
│      config_json,                                          │
│      ["cam_1", "cam_2"],                                   │
│  )                                                         │
│  pipeline.start()                                          │
│  output = pipeline.get_latest_output()  # → dict or None   │
│  pipeline.update_config(new_config_json)                   │
│  pipeline.shutdown()                                       │
├─ PyO3 bridge (src/pyo3_bridge/mod.rs) ───────────────────┤
│  #[pyclass] PyPipeline                                     │
│    inner: Mutex<Option<Pipeline>>                          │
│    cmd_senders: Vec<mpsc::Sender<PipelineCommand>>        │
│                                                             │
│  get_latest_output() → Option<Py<PyDict>>                  │
│  update_config(json) → PyResult<()>                        │
│  start() / shutdown()                                      │
├─ Pure Rust (src/pipeline/) ───────────────────────────────┤
│  Pipeline, Distributor, CameraNode, Aggregator              │
└────────────────────────────────────────────────────────────┘
```

## PyO3 Module

```rust
// src/pyo3_bridge/mod.rs

#[pymodule]
fn _freemocap_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // Init logging (idempotent — skellycam may have already called this)
    crate::init_logging("freemocap=debug,skellycam=debug,info");

    m.add_class::<py_pipeline::PyPipeline>()?;
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add("__doc__", "FreeMoCap Rust pipeline engine")?;

    Ok(())
}
```

## PyPipeline

```rust
#[pyclass]
pub struct PyPipeline {
    frame_slots: FrameSlots,
    camera_ids: Vec<String>,
    config: PipelineConfig,
    cmd_senders: Arc<Mutex<Vec<mpsc::Sender<PipelineCommand>>>>,
    output_slot: Arc<Mutex<Option<AggregatorOutput>>>,
    shutdown_flag: Arc<AtomicBool>,
    barrier: Arc<BreakableBarrier>,
    handles: Mutex<Option<Vec<JoinHandle<()>>>>,
}

#[pymethods]
impl PyPipeline {
    #[new]
    fn new(
        py: Python<'_>,
        camera_group_manager: Py<PyAny>,  // _skellycam_rust.CameraGroupManager
        group_id: String,
        config_json: &str,
        camera_ids: Vec<String>,
    ) -> PyResult<Self> {
        // Extract FrameSlots from skellycam PyO3 wrapper (Rust-to-Rust, no Python copy)
        // Deserialize config from JSON
        // Create barrier, channels, slots — don't spawn threads yet
        ...
    }

    fn start(&mut self) -> PyResult<()> {
        // Spawn distributor, N camera nodes, and aggregator threads
        // Threads use FrameSlots to poll camera frames directly
        ...
    }

    fn shutdown(&mut self) -> PyResult<()> {
        // Send Shutdown to all command channels
        // Break barrier to release cameras
        // Join all thread handles
        // Take inner to prevent further access
        ...
    }

    fn update_config(&self, config_json: &str) -> PyResult<()> {
        let config: PipelineConfig = serde_json::from_str(config_json)
            .map_err(|e| PyRuntimeError::new_err(format!("Invalid config JSON: {e}")))?;
        for sender in &self.cmd_senders {
            sender.send(PipelineCommand::UpdateConfig(config.clone()))
                .map_err(|e| PyRuntimeError::new_err(format!("Failed to send config: {e}")))?;
        }
        Ok(())
    }

    fn get_latest_output(&self, py: Python<'_>) -> PyResult<Option<Py<PyDict>>> {
        let guard = self.output_slot.lock()
            .map_err(|e| PyRuntimeError::new_err(format!("Lock poisoned: {e}")))?;
        match guard.as_ref() {
            Some(output) => {
                let dict = PyDict::new(py);
                dict.set_item("frame_number", output.frame_number)?;
                dict.set_item("keypoints_raw", dict_from_keypoints(py, &output.keypoints_raw))?;
                dict.set_item("keypoints_filtered", dict_from_keypoints(py, &output.keypoints_filtered))?;
                dict.set_item("frontend_payload", PyBytes::new(py, &output.frontend_payload))?;
                Ok(Some(dict.into()))
            }
            None => Ok(None),
        }
    }

    fn camera_ids(&self) -> PyResult<Vec<String>> {
        // Return list of camera IDs this pipeline manages
        ...
    }

    fn alive(&self) -> PyResult<bool> {
        // Check if all threads are still running
        ...
    }
}

impl Drop for PyPipeline {
    fn drop(&mut self) {
        if self.inner.lock().ok().and_then(|g| g.as_ref()).is_some() {
            eprintln!("[freemocap] PyPipeline dropped without shutdown — shutting down");
            // Best-effort shutdown
            for sender in &self.cmd_senders {
                let _ = sender.send(PipelineCommand::Shutdown);
            }
        }
    }
}
```

## Python-Side Setup

```python
# freemocap/core/pipeline/realtime/_native.py

import os
import sys

_native = None

def _get_native():
    global _native
    if _native is not None:
        return _native

    # OpenCV DLL discovery (same as skellytracker)
    opencv_bin = "C:/tools/opencv/build/x64/vc16/bin"
    if os.path.isdir(opencv_bin):
        os.add_dll_directory(opencv_bin)

    import _freemocap_rust
    _native = _freemocap_rust
    return _native
```

## Build Layout

```
freemocap-rust/
├── Cargo.toml              name = "freemocap"
│                           [lib] name = "freemocap"
│                           crate-type = ["cdylib", "rlib"]
├── pyproject.toml          module-name = "_freemocap_rust"
│                           no python-source
├── build.rs                (if OpenCV DLLs need copying)
├── .cargo/config.toml      OPENCV_LINK_PATHS / OPENCV_INCLUDE_PATHS
└── src/
    ├── lib.rs               pub mod pipeline, pub mod pyo3_bridge
    └── pyo3_bridge/
        ├── mod.rs           #[pymodule] fn _freemocap_rust
        ├── py_pipeline.rs    #[pyclass] PyPipeline
        └── types.rs         Python-facing types (if any)
```

Key: no `python/` directory. The `.pyd` installs directly into site-packages as `_freemocap_rust.pyd`.

## Guidance from SkellyTracker's Lessons

1. **Store concrete types, not trait objects** — PyO3 pyclass fields must be `Sync`. `Mutex<Option<Pipeline>>` works because `Pipeline` contains concrete types.
2. **No JSON reconstruction** — the aggregator output stored in the pyclass slot is the real Rust struct. `get_latest_output()` converts to Python dict on demand.
3. **Drop ensures cleanup** — if Python forgets to call `shutdown()`, `Drop` sends `Shutdown` to all command channels.
4. **OpenCV DLLs** — same `os.add_dll_directory()` pattern as skellytracker. No bundling in development.
5. **beartype compatibility** — `RustRealtimePipeline` must pass any `isinstance()` checks at the call boundary. Subclass if needed.
