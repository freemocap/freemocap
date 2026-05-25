# SkellyTracker Rust — Architecture Documentation

> Worked example of applying the [re-architecture playbook](../rearchitecture-playbook/) to the skellytracker pose-estimation backend, starting with the BrightestPointTracker as a warm-up.

## Status

| Tracker | Status | Notes |
|---------|--------|-------|
| **BrightestPoint** | ✅ Complete | Full Python→Rust translation with hot-swappable backends |
| **Charuco** | ✅ Complete | OpenCV Charuco board detection + annotation, full data model parity, hot-swappable |
| **RTMPose** | ✅ Phase 1 | Two-stage ONNX pipeline (YOLOX + RTMPose), 133 keypoints, CPU inference, hot-swappable. Phase 2 (CUDA/TRT) deferred. |
| MediaPipe Holistic | 🔜 Later | MediaPipe bindings |
| CompositeGPU | 🔜 Later | Multi-model pipeline |

## Documents

| # | Document | What it covers |
|---|----------|---------------|
| 01 | [Tracker Trait Architecture](./01-tracker-trait-architecture.md) | `Tracker` / `Detector` / `Annotator` / `Observation` traits, `PointCloud`, `Recorder` — the core framework |
| 02 | [BrightestPointTracker Translation](./02-brightest-point-translation.md) | Python → Rust side-by-side: detection, annotation, contour drawing, error handling |
| 03 | [PyO3 Bridge Pattern](./03-pyo3-bridge-pattern.md) | `_skellytracker_rust` native module, `pyo3_bridge/` layout, numpy↔Mat interop, contour data flow |
| 04 | [Hot-Swappable Backend](./04-hot-swappable-backend.md) | `USE_RUST_BACKEND` flag, `Rust*Tracker` adapters, `BaseTracker` subclassing for beartype |
| 05 | [Lessons Learned](./05-lessons-learned.md) | Mistakes, gotchas, patterns to reuse — what to do and NOT do for the next tracker |
| 06 | [Charuco Translation](./06-charuco-translation.md) | detectMarkers→detectBoard decomposition, output type compatibility, data model parity (18 fields), annotation pipeline |
| 07 | [RTMPose Translation](./07-rtmpose-translation.md) | YOLOX + RTMPose two-stage ONNX pipeline, SIMCC decode, affine warp coordinate mapping, `ort` crate integration, CPU inference |

## Key Constraints Discovered

1. **beartype runtime type checking is active across the entire package** — any Rust adapter MUST subclass `BaseTracker` or be accepted by the type system at the boundary. Duck-typing alone fails at runtime.

2. **`f64::NAN` → JSON `null` → Python `None`** — the JSON serialization round-trip through the PyO3 bridge destroys NaN values. The observation MUST be stored in Rust and passed directly to the annotator, bypassing the JSON path for drawing.

3. **OpenCV `unwrap_or_default()` is a trap** — it silently swallows errors. Use explicit `is_err()` checks with `eprintln!` logging. Never ignore OpenCV failures in a detection hot loop.

4. **Frame copies add up** — every `Mat::clone()` or `data.to_vec()` is a 2.7MB allocation at 720p. The annotation path must do exactly one copy: source numpy → writable buffer → draw → return.

5. **opencv crate OutputArray type compatibility** — `detectBoard` requires pre-populated `InputOutputArray` containers for marker data. Pass empty containers → C++ assertion failure. Solution: run `detectMarkers` first to populate marker vectors, then pass them to `detectBoard` for charuco corner interpolation.

6. **Dictionary enum values match across Python and Rust** — `cv2.aruco.DICT_4X4_250 = 2` (same as OpenCV C++ `DICT_4X4_250`). Do not assume enum values from one binding match another without verifying.

7. **`ndarray::from_shape_fn` closure overhead** — 2.77M closure calls per 720p frame (~3ms). Use `to_owned()` for straight copies (single memcpy). Always profile per-frame allocations.

## Build & Test

```bash
poe rebuild                                    # Rebuild Rust + Python
python skellytracker-rust/webcam_demo.py       # Webcam demo (Rust default)
python skellytracker-rust/webcam_demo.py --python  # Python fallback

# Hotkeys in demo:
#   b — switch to BrightestPointTracker
#   c — switch to CharucoTracker
#   t — switch to RTMPoseTracker
#   r — toggle Rust ↔ Python (works for BrightestPoint, Charuco, AND RTMPose)
#   m — switch to MediaPipe
#   h — show controls    i — toggle info    q — quit
```
