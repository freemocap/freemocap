# PyO3 Bridge Pattern

> How the Rust native module exposes trackers to Python. Copied from skellycam's bridge strategy and adapted for OpenCV dependency management.

## The Problem

Python code must call into the Rust tracker engine. The bridge must handle:
- numpy ↔ OpenCV Mat conversion (zero-copy for input, single-copy for output)
- JSON serialization of detection results
- OpenCV DLL discovery on Windows (no bundling)
- beartype compatibility (Rust adapter must satisfy `BaseTracker` type)

### Invariants

- Python calls `process_image(image) → dict` and `annotate_image(image, observation) → np.ndarray`
- Detection data flows from Rust to Python via JSON (lightweight — just coordinates)
- Annotation uses Rust-side stored observation (NOT JSON-reconstructed) to preserve contour data
- OpenCV DLLs found via `os.add_dll_directory()` — no PATH manipulation, no bundling
- Build is a single `poe rebuild` command (maturin via uv)

## Architecture

```
┌─ Python (site-packages) ────────────────────────────────────┐
│  import _skellytracker_rust                                   │
│  t = _skellytracker_rust.BrightestPointTracker(3, 200)        │
│  result = t.process_image(0, numpy_image)    # → dict         │
│  annotated = t.annotate_image(image, result)  # → np.ndarray  │
├─ PyO3 bridge (src/pyo3_bridge/mod.rs) ──────────────────────┤
│  #[pyclass] PyBrightestPointTracker                           │
│    inner: BrightestPointTracker    ← pure Rust tracker        │
│    last_obs: Option<BrightestPointObservation>  ← stored!     │
│                                                               │
│  process_image: numpy→Mat, call inner, store obs, return JSON │
│  annotate_image: copy numpy→ndarray, draw via stored obs     │
├─ Pure Rust (src/trackers/brightest_point/) ──────────────────┤
│  BrightestPointTracker, BrightestPointObservation, BrightPatch │
└──────────────────────────────────────────────────────────────┘
```

## Critical Lesson: The NaN → None → Crash Chain

**The mistake:** Serialize the Rust observation to JSON, send to Python, then reconstruct from the JSON dict in `annotate_image` for drawing.

**What happened:**
1. `f64::NAN` → JSON `null` → Python `None`
2. `annotate_image` tried `py_list.extract::<Vec<Vec<f64>>>()` — crashed on `None` values
3. Even when "fixed," contour data was lost (not serialized) — no blob outlines

**The fix:** Store the real Rust `BrightestPointObservation` in the pyclass:
```rust
struct PyBrightestPointTracker {
    inner: BrightestPointTracker,
    last_obs: Option<BrightestPointObservation>,  // ← concrete type, not Box<dyn>
}
```
`process_image` stores the observation. `annotate_image` uses it directly. The JSON dict returned to Python is for the caller's own use (display, logging) — never for annotation.

**Constraint:** PyO3 requires pyclass fields to be `Sync`. `Box<dyn Observation>` is not `Sync` (trait bound issue). Store the concrete type (`BrightestPointObservation`) instead.

## Build Layout (matching skellycam)

```
skellytracker-rust/
├── Cargo.toml          name = "skellytracker", [lib] name = "skellytracker"
├── pyproject.toml      module-name = "_skellytracker_rust", no python-source
├── build.rs            Copies OpenCV DLLs to cargo target dirs only
├── .cargo/config.toml  OPENCV_LINK_PATHS / OPENCV_INCLUDE_PATHS
└── src/
    ├── lib.rs           pub mod pyo3_bridge;
    └── pyo3_bridge/
        ├── mod.rs       #[pymodule] fn _skellytracker_rust, pyclasses
        └── types.rs     Python-facing dataclass equivalents
```

Key: no `python/` directory. The `.pyd` installs directly into site-packages as `_skellytracker_rust.pyd`. On Windows, `os.add_dll_directory("C:/tools/opencv/build/x64/vc16/bin")` is called before import.

## OpenCV DLL Strategy

**Development:** `rust_bridge.py` calls `os.add_dll_directory()` before `import _skellytracker_rust`. The DLLs live at the chocolatey install path. No bundling needed.

**Distribution (future):** Wheels would need to bundle OpenCV DLLs. Options: `build.rs` copies DLLs into the wheel's data directory, or use `auditwheel`-style repair on Windows.

## numpy ↔ Mat Interop

```rust
// Input: borrow numpy buffer as non-owning Mat (zero copy)
fn numpy_to_mat(arr: &PyReadonlyArrayDyn<u8>) -> PyResult<Mat> {
    let slice = arr.as_slice()?;
    let data_ptr = slice.as_ptr() as *mut c_void;
    unsafe { Mat::new_rows_cols_with_data_unsafe_def(rows, cols, CV_8UC3, data_ptr) }
}

// Output: copy ndarray into Python-owned numpy array
fn ndarray_to_numpy(py, arr: Array3<u8>) -> Py<PyAny> {
    arr.into_pyarray(py).into_any().unbind()
}
```

## Guidance for Next Trackers

1. **Store detection results in the pyclass, not in JSON** — every tracker's pyclass needs a `last_obs: Option<ConcreteObservationType>` field
2. **Use the same `draw_markers_into` pattern** — the bridge calls the tracker's shared drawing method, never reimplements drawing
3. **No JSON reconstruction for annotation** — JSON is for Python consumers (display, logging). Drawing uses the real Rust observation with full data.
4. **PyO3 Sync constraint** — if a pyclass stores an observation, it must be the concrete type (not `Box<dyn Trait>`)
5. **Build matches skellycam exactly** — same `poe rebuild` command, same maturin config, same module naming convention
