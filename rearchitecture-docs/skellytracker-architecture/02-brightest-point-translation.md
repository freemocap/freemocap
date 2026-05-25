# BrightestPointTracker — Python → Rust Translation

> The complete worked example. Every algorithmic step mapped, every divergence documented.

## The Problem

Find the N brightest regions in a camera frame by thresholding, contour detection, moment computation, and centroid extraction. Draw markers at detected centroids and polygon outlines around the blobs.

### Invariants

- BGR → grayscale conversion
- Binary threshold at a configurable luminance value
- External contour detection (RETR_EXTERNAL)
- Moment-based centroid computation (m10/m00, m01/m00)
- Sort by area descending, keep top N
- Draw cross markers at centroids
- Draw polygon outlines around detected blobs
- Same OpenCV function calls, same parameters

## Side-by-Side Algorithm

| Step | Python (`brightest_point_tracker.py`) | Rust (`src/trackers/brightest_point/mod.rs`) |
|------|------|------|
| 1. Grayscale | `cv2.cvtColor(image, COLOR_BGR2GRAY)` | `imgproc::cvt_color(image, &mut gray, COLOR_BGR2GRAY, 0, ALGO_HINT_DEFAULT)` |
| 2. Threshold | `cv2.threshold(gray, threshold, 255, THRESH_BINARY)` | `imgproc::threshold(gray, &mut thresh, threshold, 255.0, THRESH_BINARY)` |
| 3. Contours | `cv2.findContours(thresh, RETR_EXTERNAL, CHAIN_APPROX_SIMPLE)` | `imgproc::find_contours(&thresh, &mut contours, RETR_EXTERNAL, CHAIN_APPROX_SIMPLE, Point::default())` |
| 4. Per-contour moments | `cv2.moments(patch)` | `imgproc::moments(&contour, false)` |
| 5. Centroid | `m10/m00`, `m01/m00` (m00 != 0 guard) | `moments.m10 / moments.m00`, `moments.m01 / moments.m00` (m00 == 0 guard + area > 0 guard) |
| 6. Area | `cv2.contourArea(patch)` | `imgproc::contour_area(&contour, false)` |
| 7. Sort | `sorted(patches, key=lambda p: p.area, reverse=True)` | `sort_by(\|a, b\| b.area.partial_cmp(&a.area)...)` |
| 8. Top N | `[: self.num_points]` | `.truncate(self.num_points)` |
| 9. Marker draw | `cv2.drawMarker(img, (x,y), (0,0,255), MARKER_CROSS, 20, 2)` | `imgproc::draw_marker(img, Point(x,y), MARKER_COLOR, MARKER_CROSS, 20, 2, LINE_8)` |
| 10. Outline draw | (not in Python — added in Rust) | `imgproc::polylines(img, &pts, true, OUTLINE_COLOR, 2, LINE_8, 0)` |

## Rust-Specific Improvements

### 1. Error handling — no silent failures

**Before (broken):**
```rust
imgproc::cvt_color(image, &mut gray, COLOR_BGR2GRAY, 0, ALGO_HINT_DEFAULT)
    .unwrap_or_default();  // SILENTLY RETURNS EMPTY MAT ON FAILURE
```

**After (fixed):**
```rust
if imgproc::cvt_color(image, &mut gray, COLOR_BGR2GRAY, 0, ALGO_HINT_DEFAULT).is_err() {
    eprintln!("[skellytracker-rust] cvt_color failed — returning empty observation");
    let empty_points = self.build_point_cloud(&[]);
    return Box::new(BrightestPointObservation::new(frame_number, empty_points, vec![]));
}
```

Same pattern applied to `threshold` and `find_contours`. OpenCV errors are logged to stderr and the function gracefully returns empty results rather than silently producing garbage.

### 2. Single drawing source of truth

```rust
// Drawing constants at module level — match Python exactly.
const MARKER_COLOR: Scalar = Scalar::new(0.0, 0.0, 255.0, 0.0);  // BGR red
const MARKER_TYPE: i32 = imgproc::MARKER_CROSS;
const MARKER_SIZE: i32 = 20;
const MARKER_THICKNESS: i32 = 2;

// One method used by BOTH the trait impl and the PyO3 bridge.
pub fn draw_markers_into(&self, image: &mut Mat, obs: &dyn Observation) {
    // 1. Draw blob outlines from contour data
    if let Some(bp) = obs.as_any().downcast_ref::<BrightestPointObservation>() {
        for patch in &bp.patches {
            if patch.contour.len() < 3 { continue; }
            let pts: Vector<Point> = patch.contour.iter().copied().collect();
            imgproc::polylines(image, &pts, true, OUTLINE_COLOR, 2, LINE_8, 0);
        }
    }
    // 2. Draw cross markers at centroids
    let pc = obs.point_cloud();
    for i in 0..pc.n_points() {
        if pc.visibility[i] <= 0.0 { continue; }
        imgproc::draw_marker(image, Point(xy[i,0], xy[i,1]), MARKER_COLOR, MARKER_CROSS, 20, 2, LINE_8);
    }
}
```

Both the Rust `Tracker::annotate_image` and the PyO3 bridge's `annotate_image` call `draw_markers_into`. No duplicate drawing logic can diverge.

### 3. Contour storage for blob outlines

```rust
pub struct BrightPatch {
    pub area: f64,
    pub centroid_x: i32,
    pub centroid_y: i32,
    pub contour: Vec<Point>,  // ← NEW: stored for outline drawing
}
```

Python discarded contour points after computing centroids. Rust stores them so the annotator can draw the actual blob boundary. Not serialized to JSON (annotation-only).

### 4. Memory: single frame copy in annotation

```rust
// Copies source numpy data ONCE into a writable ndarray.
let out = Array3::<u8>::from_shape_fn(shape, |(y, x, c)| arr[[y, x, c]]);

// Wraps as non-owning Mat, draws directly, drops Mat reference.
let mut annotated = unsafe { Mat::new_rows_cols_with_data_unsafe_def(...) };
self.inner.draw_markers_into(&mut annotated, obs);
drop(annotated);

// Transfers ownership to Python — no second copy.
let bound_arr = out.into_pyarray(py);
```

Previous code did `Mat::clone()` + `data.to_vec()` = two frame copies per annotation. Now: one `from_shape_fn` copy, draw into it, transfer to Python.

## Data Flow

```
process_image(frame, image)
  ├─ cvt_color BGR→GRAY
  ├─ threshold
  ├─ find_contours
  ├─ per-contour: moments + area + centroid
  ├─ sort by area desc, truncate to top N
  ├─ build PointCloud { names, xyz, visibility }
  ├─ build BrightestPointObservation { frame_number, points, patches (with contours) }
  ├─ .to_json() → JSON string → Python dict (xy + visibility, NO contour data)
  └─ store clone in self.last_obs  ← for annotate_image

annotate_image(frame, _observation_dict)
  ├─ copy numpy → ndarray (single allocation)
  ├─ wrap ndarray as Mat (non-owning header)
  ├─ self.draw_markers_into(&mut mat, self.last_obs)  ← uses stored obs, NOT the dict
  │   ├─ downcast to BrightestPointObservation
  │   ├─ draw polylines for each patch contour (magenta outline)
  │   └─ draw cross markers at centroids (red)
  ├─ drop Mat header
  └─ return ndarray as numpy array
```

## Guidance for Next Trackers

1. **Map every OpenCV call 1:1** — same function, same constants, same parameter order
2. **Extract drawing constants at module level** — `MARKER_COLOR`, `LINE_TYPE`, etc.
3. **`draw_markers_into()` as single source of truth** — prevents annotation drift
4. **Store extra detection data (contours, raw keypoints) in the observation** — the annotator can use it without re-computation
5. **Error handling: `is_err()` + `eprintln!` + graceful fallback** — never `unwrap_or_default()` on an OpenCV call in a hot loop
6. **One frame copy for annotation** — never `Mat::clone()` + `data.to_vec()`. Use `ndarray::from_shape_fn` + `Mat::new_rows_cols_with_data_unsafe` for a single allocation.
