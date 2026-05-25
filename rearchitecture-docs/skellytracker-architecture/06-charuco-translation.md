# Charuco Tracker — Python → Rust Translation

> Second tracker translated after BrightestPoint. Proof that the pattern scales — but with new challenges: complex data models, opencv crate output type issues, and the `InputOutputArray` gotcha.

## What was translated

The full Charuco detection + annotation pipeline from `skellytracker/trackers/charuco_tracker/`:

| Python file | Rust equivalent |
|-------------|-----------------|
| `charuco_detector.py` | `src/trackers/charuco/mod.rs` — `CharucoTracker::detect()` |
| `charuco_annotator.py` | `src/trackers/charuco/mod.rs` — `draw_markers_into()` |
| `charuco_observation.py` | `src/trackers/charuco/observation.rs` |
| `charuco_tracker_config.py` | Tracker constructor parameters |
| `charuco_board_definition.py` | Tracker constructor — `CharucoBoardDefinition` → constructor args |

## Detection pipeline

Python's single call:
```python
(charuco_corners, charuco_ids, aruco_corners, aruco_ids) = detector.detectBoard(grey_image)
```

Rust's equivalent (decomposed because of opencv crate limitation):
```rust
// Step 1: Detect aruco markers (populates marker containers)
let (marker_corners, marker_ids) = detect_aruco_markers_raw(&gray);

// Step 2: Pass pre-populated markers to detectBoard for charuco corner interpolation
detector.detect_board(&gray,
    &mut charuco_corners,  // output: corner positions (Vector<Point2f>)
    &mut charuco_ids,       // output: corner IDs (Vector<i32>)
    &mut marker_corners,    // input: pre-detected markers
    &mut marker_ids,        // input: pre-detected marker IDs
);
```

**Why decomposed?** The opencv crate cannot pass `noArray()` for `InputOutputArray` defaults. Empty containers trigger a C++ assertion (`size_t(i) < vv->size()`). Running `detectMarkers` first populates the containers, and `detectBoard` reads them as valid input. This is what `detectBoard()` does internally anyway — the decomposition makes the internal steps explicit without changing the algorithm.

## Data model (Rule #0 applied)

The Rust `CharucoObservation` has 18 fields matching every Python field:

| Category | Fields | Status |
|----------|--------|--------|
| Core | `tracker_type`, `frame_number`, `image_size`, `points` | ✅ |
| Board definition | `all_charuco_ids`, `all_charuco_corners_in_object_coordinates`, `all_aruco_ids`, `all_aruco_corners_in_object_coordinates` | ✅ |
| Raw detection | `raw_charuco_corners`, `detected_charuco_corner_ids`, `detected_charuco_corners_image_coordinates`, `detected_charuco_corners_in_object_coordinates`, `detected_aruco_marker_ids`, `detected_aruco_marker_corners` | ✅ |
| Board pose | `charuco_board_translation_vector`, `charuco_board_rotation_vector`, `detected_charuco_corners_in_camera_coordinates`, `detected_aruco_markers_in_camera_coordinates` | `None` (deferred — requires `solvePnP`) |

**Key design decision:** Object coordinates are pre-computed at tracker construction from `board.get_chessboard_corners()` and `board.get_obj_points()`, then stored in the observation. `detected_charuco_corners_in_object_coordinates` is the subset of `all_charuco_corners_in_object_coordinates` indexed by `detected_charuco_corner_ids`.

## Annotation pipeline

Rust `draw_markers_into()` draws the exact same elements as Python `CharucoImageAnnotator.annotate_image()`:

1. **Aruco marker bounding boxes** — green polylines around each detected marker's 4 corners, with "ArUco#N" labels
2. **Charuco corner markers** — magenta diamonds at each detected corner, with "Corner#N" labels
3. **Undetected corners list** — right-side panel listing corner IDs not found in the current frame

Deferred: motion trails (`show_tracks` config), faded marker scaling.

## Performance optimization

Per-frame allocation audit in `draw_markers_into`:

| Allocation | Before | After |
|-----------|--------|-------|
| `Vector<Point>` per marker | `collect()` per marker (17 allocs/frame) | One reusable `Vector::with_capacity(4)`, cleared per marker |
| `String` per label | `format!()` per marker/corner (41 allocs/frame) | One reusable `String`, `write_fmt` per label |
| Frame copy | `from_shape_fn` closure (2.77M calls/frame) | `to_owned()` memcpy (single copy) |

## OpenCV API mapping

| Python (`cv2.aruco`) | Rust (`crate::objdetect`) |
|---------------------|--------------------------|
| `cv2.aruco.CharucoBoard(size, sqLen, mkLen, dict)` | `CharucoBoard::new_def(Size, sqLen, mkLen, &Dictionary)` |
| `cv2.aruco.CharucoDetector(board)` | `CharucoDetector::new_def(&CharucoBoard)` |
| `detector.detectBoard(image)` | decomposed: `detect_markers_def()` + `detect_board(image, ..., &markers, &marker_ids)` |
| `cv2.aruco.getPredefinedDictionary(DICT_4X4_250)` | `get_predefined_dictionary_i32(2)` |
| `cv2.drawMarker(img, pt, color, MARKER_DIAMOND, ...)` | `imgproc::draw_marker(img, pt, color, MARKER_DIAMOND, ...)` |
| `cv2.polylines(img, [pts], True, color, 2)` | `imgproc::polylines(img, &pts, true, color, 2, LINE_8, 0)` |
| `cv2.putText(img, text, pos, font, scale, color, thick)` | `imgproc::put_text(img, text, pos, font, scale, color, thick, LINE_AA, false)` |
| `board.getChessboardCorners()` | `board.get_chessboard_corners()` → `Vector<Point3f>` |
| `board.getObjPoints()` | `board.get_obj_points()` → `Vector<Vector<Point3f>>` |
| `board.getIds()` | `board.get_ids()` → `Vector<i32>` |

## Files created/modified

```
skellytracker-rust/src/trackers/charuco/
├── mod.rs              # CharucoTracker struct + Trait impl + draw_markers_into + helpers
└── observation.rs      # CharucoObservation (18 fields, full Python parity)

skellytracker-rust/src/trackers/mod.rs         # + pub mod charuco;
skellytracker-rust/src/pyo3_bridge/mod.rs      # + PyCharucoTracker pyclass (Mutex wrapped)

skellytracker/trackers/charuco_tracker/
└── rust_bridge.py      # RustCharucoTracker(BaseTracker) adapter + factory

skellytracker/io/demo_viewers/
└── webcam_demo_viewer.py  # c-key Charuco + r-key within-Charuco toggle
```

## Verification results

- **Detection parity:** 35/35 frames match between Python and Rust (222-frame test video, 0 mismatches)
- **Corner count:** Frame 023: both Python and Rust detect 24/24 corners with identical IDs
- **Annotation:** Markers drawn correctly — magenta diamonds, green aruco boxes, text labels
- **Object coordinates:** `all_charuco_corners_in_object_coordinates` populated, `detected_charuco_corners_in_object_coordinates` = correct subset
- **Hot-swap:** `c` key switches Charuco, `r` key toggles Rust↔Python within Charuco mode
