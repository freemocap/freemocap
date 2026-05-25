# RTMPose Tracker — Python → Rust Translation (Phase 1: CPU)

> Third tracker translated after BrightestPoint and Charuco. The most complex so far: a two-stage ONNX Runtime pipeline (YOLOX person detection + RTMPose keypoint estimation) producing 133 full-body keypoints.

## What was translated

The full YOLOX + RTMPose two-stage pipeline from `skellytracker/trackers/rtmpose_tracker/`:

| Python file | Rust equivalent |
|-------------|-----------------|
| `rtmpose_detector.py` | `src/trackers/rtmpose/mod.rs` — `RtmPoseTracker::detect()` |
| `rtmpose_observation.py` | `src/trackers/rtmpose/observation.rs` |
| `rtmpose_session.py` (predict_single path) | `src/onnx_utils/mod.rs` — `RtmPoseOrtSession` |
| `rtm_preprocessing.py` | `src/onnx_utils/preprocessing.rs` |
| `rtm_postprocessing.py` | `src/onnx_utils/postprocessing.rs` |
| `model_registry.py` (URL download) | `src/onnx_utils/mod.rs` — `resolve_model()` |
| `rtmpose_annotator.py` + `_skeleton_viz.py` | `src/trackers/rtmpose/mod.rs` — `draw_markers_into()` |

## Detection pipeline

### Two-stage architecture

```
BGR Image → [YOLOX letterbox] → padded (640,640) → [YOLOX ONNX] → person bboxes
                                                                    ↓
BGR Image + bbox → [affine crop + normalize] → (192,256) → [RTMPose ONNX] → SIMCC heatmaps
                                                                                ↓
                                                           [SIMCC decode + coordinate reconstruction]
                                                                                ↓
                                                    (1, 133, 2) keypoints + (1, 133) scores
```

### Stage 1: YOLOX person detection

```rust
// Preprocessing: letterbox resize + pad (gray=114), uint8 (no normalize — ONNX handles it)
let (padded, ratio) = yolox_letterbox_preprocess(image, (640, 640));

// HWC → CHW → float32 → (1, 3, 640, 640) tensor → ONNX session.run()
let outputs = session.det_session.run(ort::inputs![tensor]);

// Postprocessing: boxes / ratio, NMS (IoU=0.45), score filter (>0.3)
let bboxes = yolox_postprocess(&det_output, ratio, 0.45, 0.7);
```

### Stage 2: RTMPose keypoint estimation

```rust
// Preprocessing: xyxy → (center, scale) with 1.25× padding → affine warp → normalize
let (cropped, center, scale) = rtmpose_letterbox_preprocess(image, &bbox, (192, 256));

// Normalize in ndarray space: (pixel - mean) / std  (BGR mean/std from Python)
// HWC → CHW → (1, 3, 192, 256) tensor → ONNX session.run()
let outputs = session.pose_session.run(ort::inputs![tensor]);

// SIMCC decode: argmax on x/y heatmaps → model-space coords → image coords
let (keypoints, scores) = rtmpose_letterbox_postprocess(
    &simcc_x, &simcc_y, &center, &scale, (192, 256), simcc_split_ratio=2.0
);
```

### The affine warp bug

The most subtle bug was in the affine crop: the third source/destination point pair was computed wrong.

Python's `get_warp_matrix` uses `_get_3rd_point(a, b)`:
```python
def _get_3rd_point(a, b):
    direction = a - b
    return b + [-direction[1], direction[0]]  # perpendicular to direction
```

For `src`: `a=[cx,cy], b=[cx, cy-sw/2]` → `direction=[0, sw/2]` → 3rd = `[cx-sw/2, cy-sw/2]`

The initial Rust code incorrectly computed the third point as `[cx+sw/2, cy]` (right-and-same-height instead of left-and-below), producing a completely wrong affine mapping. The fix was to match Python's exact point computation and feed the three point pairs into OpenCV's `get_affine_transform()`.

## Data model (Rule #0 applied)

```rust
pub struct RtmPoseObservation {
    pub tracker_type: &'static str,   // "rtmpose"
    pub frame_number: u64,
    pub image_size: (u32, u32),
    pub points: PointCloud,           // 133 points in schema order
    pub keypoints: Array3<f64>,       // (num_persons, 133, 2) rtmlib native order
    pub scores: Array2<f32>,          // (num_persons, 133) rtmlib native order
}
```

**Key design decisions:**

- **Two coordinate orderings coexist**: `points` stores in *schema order* (body → right_hand → left_hand → face). `keypoints` and `scores` store in *rtmlib's native COCO-WholeBody order* (body → face → left_hand → right_hand). This matches Python's RTMPoseObservation exactly — the annotation code uses `.keypoints` directly (native order), while the PointCloud is in schema order for downstream consumers.
- **Permutation**: `[0..23, 112..133, 91..112, 23..91]` maps rtmlib source index → schema target index.
- **133 point names**: body(23) + right_hand prefix(21) + left_hand prefix(21) + face_xxxx(68), generated from the YAML composition at construction time.

## Annotation pipeline

Skeleton drawing uses the simplified COCO-133 link format from Python's `_skeleton_viz.py`:

1. **Body edges** (0-22): 26 edges including COCO-17 + foot keypoints (heel→big_toe, heel→small_toe, etc.)
2. **Face chain** (23-90): 67 sequential edges connecting all 68 face contour points
3. **Left hand chain** (91-111): 20 sequential edges connecting 21 hand keypoints
4. **Right hand chain** (112-132): 20 sequential edges connecting 21 hand keypoints

Keypoints are drawn as filled red circles (radius=3), skeleton lines in green (thickness=2). NaN keypoints (undetected) are skipped.

## New dependency: ONNX Runtime via `ort` crate

This is the first tracker requiring a non-OpenCV ML framework:

| Concern | Python | Rust |
|---------|--------|------|
| ONNX Runtime | `onnxruntime` pip package (CUDA/cuDNN) | `ort` crate v2.0.0-rc.12 (`download` feature → prebuilt CPU binaries) |
| Session creation | `ort.InferenceSession(path, sess_options, providers=[...])` | `Session::builder()?.commit_from_file(path)?` |
| Inference | `session.run(None, {"input": array})` | `session.run(ort::inputs![tensor])?` |
| Tensor ↔ ndarray | Transparent (numpy) | `Tensor::from_array(ndarray)` / `output.try_extract_array::<T>()` |
| Model download | Python `requests` + `zipfile` | `ureq` + `zip` crate |

### Phase 1 limitation: CPU only

The `ort` crate's default `download` feature pulls CPU-only ONNX Runtime binaries. At runtime this produces ~500-700ms/frame vs Python's CUDA ~45ms/frame. The Rust *inference itself* is fast — the gap is entirely CPU vs GPU execution provider. Adding the `cuda` feature (Phase 2) will close this gap by linking against GPU ONNX Runtime.

### SIMCC: Simple Multi-Domain Coordinate Classification

RTMPose uses SIMCC rather than 2D heatmaps for keypoint localization:

- Each keypoint gets two 1D classification heads: `simcc_x` (horizontal bins) and `simcc_y` (vertical bins)
- The x-axis gets `model_width × split_ratio` bins, the y-axis gets `model_height × split_ratio` bins
- `argmax` in each head gives the discrete bin → convert back to continuous coordinate
- For a 133-keypoint model with 192×256 input and split_ratio=2: (133 × 384) + (133 × 512) = 119K output values vs. 133 × 192 × 256 = 6.5M for a 2D heatmap — 55× smaller

## Patterns established by this translation

1. **New dependency integration**: Added `ort`, `ureq`, `zip`, `dirs` crates. Bumped `ndarray` 0.16→0.17 to match `ort`'s dependency (version mismatch silently breaks trait implementations).
2. **Separate `onnx_utils/` module** for framework-specific infrastructure (session management, preprocessing, postprocessing, model download) — keeps the tracker module focused on the pipeline.
3. **ndarray-space normalization**: BGR mean/std normalization done in ndarray after Mat→ndarray conversion, avoiding OpenCV channel-splitting complexity.
4. **Row-by-row Mat→ndarray extraction**: OpenCV Mats accessed via raw `data()` pointer with per-row stride (`mat_step()[0]`), copying only the valid pixel region into contiguous ndarray buffers.
5. **Positional ONNX inputs**: `inputs![tensor]` (no name caching) avoids needing to access `Session.inputs[n].name` (which is private in `ort` 2.x).

## File structure

```
skellytracker-rust/src/
├── onnx_utils/
│   ├── mod.rs              # Model download, RtmPoseOrtSession, mode configs
│   ├── preprocessing.rs    # YOLOX letterbox, RTMPose affine crop
│   └── postprocessing.rs   # NMS, SIMCC decode, YOLOX postprocess
├── trackers/
│   └── rtmpose/
│       ├── mod.rs          # RtmPoseTracker + Trait impl + draw_markers_into
│       └── observation.rs  # RtmPoseObservation + 133 names + permutation
└── pyo3_bridge/
    └── mod.rs              # + PyRtmPoseTracker (Mutex-wrapped)

skellytracker/trackers/rtmpose_tracker/
└── rust_bridge.py          # RustRtmPoseTracker(BaseTracker) adapter

skellytracker/io/demo_viewers/
└── webcam_demo_viewer.py   # + 't' hotkey, r-key toggle for RTMPose
```

## What's deferred to Phase 2+

- **CUDA/TensorRT execution providers** (`ort` crate `cuda`/`tensorrt` features)
- **Batched multi-image inference** (`predict_batch` — stack N images into one ONNX call)
- **TRT engine compilation + caching** (FP16 engine cache, first-run compilation ticker)
- **Multi-person support** (currently takes first detected person only)
- **YAML-based skeleton connections** (currently uses hardcoded COCO-133 simplified links from `_skeleton_viz.py`)
