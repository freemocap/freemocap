# Aggregator

> Step 4 (Design Rust Architecture) — fan-in collection, triangulation, and filtering.
>
> **Status: Implemented** (2026-05-26) — the aggregator in `src/pipeline/aggregator.rs` follows this design closely. Key diffs: (1) `calibration` is `Option<HashMap<String, CameraModel>>` (no hot-reload yet — open feature), (2) triangulation calls the standalone `triangulate_charuco_corners()` function rather than a method, (3) shutdown uses channel disconnection via sender drops instead of explicit `Shutdown` command.

## The Problem

Collect per-camera charuco observations for frame N, triangulate 3D points if calibration is available, apply velocity gating and temporal filtering, and publish the aggregated output for frontend delivery.

### Invariants

- All camera outputs must be for the same frame_number
- Charuco triangulation uses existing calibration (stereo camera parameters)
- Velocity gate rejects teleportation spikes
- One Euro filter smooths keypoint trajectories
- Output must include the pre-bundled frontend payload (images)
- Calibration hot-reload: detect new calibration file on disk without restart

## Python's Solution

The `RealtimeAggregatorNode` (single `multiprocessing.Process`):
- Drains `CameraNodeOutputTopic` subscription until all cameras report for `latest_requested_frame`
- `CalibrationStateTracker` polls calibration file on disk every 1 second
- Triangulation via `calibration.try_angulate()` per observation type
- `SimpleRealtimeKeypointFilter` (One Euro) → `RealtimePointGate` (velocity) → `RealtimeSkeletonFilter` (FABRIK bone constraints)
- Optimistically requests next frame before processing current (pipeline parallelism)
- Publishes `AggregationNodeOutputMessage` via PubSub
- Backpressure via `result_ready_event` / `result_consumed_event`

## Rust's Solution

### Aggregator Thread

```rust
struct Aggregator {
    cmd_rx: mpsc::Receiver<PipelineCommand>,
    camera_rxs: Vec<(CameraId, mpsc::Receiver<CameraNodeOutput>)>,
    output_slot: Arc<Mutex<Option<AggregatorOutput>>>,
    calibration: CalibrationState,
    keypoint_filter: OneEuroFilter,
    velocity_gate: RealtimePointGate,
    config: AggregatorConfig,
}

impl Aggregator {
    fn run(&mut self) {
        loop {
            // ── Handle commands ──
            match self.cmd_rx.try_recv() {
                Ok(PipelineCommand::UpdateConfig(config)) => self.apply_config(&config),
                Ok(PipelineCommand::Shutdown) => break,
                Err(TryRecvError::Empty) => {}
                Err(TryRecvError::Disconnected) => break,
            }

            // ── Collect all camera outputs for the next frame ──
            // All cameras are at the same frame_number (guaranteed by barrier)
            let mut outputs = Vec::with_capacity(self.camera_rxs.len());
            for (cam_id, rx) in &self.camera_rxs {
                match rx.recv() {  // BLOCKING — camera WILL send
                    Ok(output) => {
                        if outputs.first().map_or(false, |o: &CameraNodeOutput| {
                            o.frame_number != output.frame_number
                        }) {
                            eprintln!("[freemocap] Aggregator: frame_number mismatch!");
                            outputs.clear();
                            break;
                        }
                        outputs.push(output);
                    }
                    Err(_) => break, // camera disconnected → shutdown
                }
            }
            if outputs.len() != self.camera_rxs.len() { break; }

            let frame_number = outputs[0].frame_number;

            // ── Calibration hot-reload ──
            self.calibration.maybe_reload();

            // ── Triangulate charuco observations ──
            let mut raw_keypoints: HashMap<String, [f64; 3]> = HashMap::new();
            if self.config.triangulation_enabled && self.calibration.is_valid() {
                self.triangulate_charuco(&outputs, &mut raw_keypoints);
            }

            // ── Velocity gate ──
            let gated = if self.config.filter_enabled {
                self.velocity_gate.gate(raw_keypoints)
            } else {
                raw_keypoints
            };

            // ── One Euro filter ──
            let filtered = if self.config.filter_enabled {
                self.keypoint_filter.filter(gated)
            } else {
                gated
            };

            // ── Publish output ──
            *self.output_slot.lock() = Some(AggregatorOutput {
                frame_number,
                keypoints_raw: filtered.clone(),
                keypoints_filtered: filtered,
                frontend_payload: self.current_frontend_payload.clone(),
            });
        }
    }
}
```

### Triangulation

Charuco triangulation uses the calibration's stereo parameters. Each charuco corner detected in 2+ cameras with known extrinsics produces a 3D point. The math is:
- Undistort 2D corner points using camera intrinsics
- Triangulate via DLT (Direct Linear Transform) using projection matrices
- (n cameras) choose the pair with the smallest reprojection error
- Filter by max reprojection error threshold

```rust
fn triangulate_charuco(
    &self,
    outputs: &[CameraNodeOutput],
    keypoints: &mut HashMap<String, [f64; 3]>,
) {
    // Group observations by corner ID across cameras
    let corners_by_id = group_charuco_corners(outputs);
    for (corner_id, observations) in corners_by_id {
        if observations.len() < 2 { continue; }
        if let Some(point_3d) = self.calibration.triangulate(&observations) {
            keypoints.insert(corner_id, point_3d);
        }
    }
}
```

### Calibration Hot-Reload

```rust
struct CalibrationState {
    path: PathBuf,
    last_modified: Option<SystemTime>,
    params: Option<StereoCalibrationParams>,
}

impl CalibrationState {
    fn maybe_reload(&mut self) {
        let metadata = match fs::metadata(&self.path) {
            Ok(m) => m,
            Err(_) => return,
        };
        let modified = metadata.modified().unwrap();
        if self.last_modified != Some(modified) {
            self.last_modified = Some(modified);
            match StereoCalibrationParams::load(&self.path) {
                Ok(params) => {
                    self.params = Some(params);
                    eprintln!("[freemocap] Aggregator: hot-reloaded calibration");
                }
                Err(e) => {
                    eprintln!("[freemocap] Aggregator: calibration reload failed: {e}");
                }
            }
        }
    }
}
```

## Key Differences

| Concern | Python | Rust |
|---------|--------|------|
| Collection | PubSub subscription with `get(timeout=0.005)` polling | Blocking `recv()` on per-camera channels |
| Frame sync verification | Manual `frame_number` comparison | Barrier guarantees same frame_number; assertion on first output |
| Triangulation | `calibration.try_angulate()` (Python) | Direct DLT implementation or Python callback |
| Filter chain | One Euro → Velocity Gate → FABRIK skeleton filter | Same chain (ported to Rust, or Python callback via PyO3) |
| Calibration poll | `time.perf_counter()` every 1s | `SystemTime` + `fs::metadata` |
| Backpressure | `multiprocessing.Event` pair | `Arc<Mutex<Option<T>>>` — consumer polls, producer swaps |
| Pipeline parallelism | Optimistically requests next frame before processing current | Not needed — camera nodes and aggregator run in parallel by default (different threads) |
