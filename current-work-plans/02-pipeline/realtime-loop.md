# The Realtime Loop

**Describes:** the live path — camera frames in, self-describing CBOR frames out.
`freemocap/core/pipeline/realtime/realtime_aggregator_node.py` + the streaming producers +
`freemocap/api/websocket/websocket_server.py`. The solve internals live in
[kinematics-engine.md](kinematics-engine.md); the wire in
[../03-transport/message-protocol.md](../03-transport/message-protocol.md).

## Composition-time (once per run, in the aggregator's `_run`)

1. `CalibrationStateTracker.create_and_try_load(...)` → calibration (hot-reloadable).
2. `load_standard_human_mapping(detector_type)` (`core/tasks/mocap/tracker_mappings.py`) — merges
   skellytracker's body + hand mapping YAMLs into one keypoints→landmark callable
   ([../01-data-model/tracker-mapping.md](../01-data-model/tracker-mapping.md)).
3. `SkeletonDefinition.from_default_yaml()` → `RestPose.from_default_yaml(skeleton=...)` →
   `ContinuousRollResolver.for_skeleton(skeleton=...)`.
4. If CoM enabled: `AnthropometricParameters.from_default_yaml()` +
   `CenterOfMassDefinitions.from_default_yaml()` (validated against the skeleton) + per-segment
   masses at an assumed 70 kg body — see [biomechanics-layer.md](biomechanics-layer.md).

Detector changes reload the mapping; calibration hot-reloads reset the roll resolver and CoM state.

## Per frame (in order)

1. **Triangulate** skeleton + charuco observations across cameras via the calibration.
2. **Convert once:** FreeMoCap's historical keypoint frame (+X forward/+Y left/+Z up) → Blender
   (+X right/+Y forward/+Z up), a single rotation at ingest. Nothing downstream converts again.
3. **Smooth/gate:** One Euro filter (`RealtimeKeypointFilter`, `core/tasks/mocap/realtime_filtering/`)
   then the velocity gate `RealtimePointGate`.
4. **Map:** `standard_human_mapping(filtered_keypoints)` → `{landmark_name: ndarray}` — tracker
   names become standard-human names BEFORE any model code sees them.
5. **Hydrate:** each mapped position wrapped as a `Point`;
   `hydrate_skeleton(skeleton=..., observed=..., require_all=False)` → partial `SkeletonPose`
   (unhydratable segments are absent this frame).
6. **Resolve roll:** `roll_resolver.resolve_pose(pose=...)` — direction-only segments get
   parallel-transported roll; rigid-fit poses pass through.
7. **Extract rotations:** world quats straight from segment poses; local = `conj(parent) · child`,
   falling back to world for the root or when the parent did not hydrate this frame.
8. **Reproject** segment origins into each camera via `origin_landmark_names(skeleton)` +
   the calibration triangulator → 2D overlay points.
9. **Center of Mass / XCoM** (gated by `center_of_mass_enabled`): landmark world positions →
   per-segment CoMs (partial-CoM aware) → whole-body CoM → XCoM from central-difference velocity;
   skipped entirely on frames where nothing hydrated.
10. **Publish** `AggregationNodeOutputMessage`: tracker keypoints, hydrated landmarks, local/world
    rotations, live-measured segment lengths (rolling-median over observed origin→primary
    distances), reprojections, `total_body_com`, `xcom`.

## Send path (the websocket side)

`websocket_server.py` holds its own `SkeletonDefinition` + `RestPose`, wraps them in a
`StreamContext` (recomposed when cameras/detector/live-state change), pulls aggregator outputs,
and hands each to the relay: static parts (`CoordinateConvention`, `CalibratedCamera`s,
`ModelDefinition.from_standard_human(...)` — segments, landmarks, connections) plus per-frame
producer fills:

| Producer | Channels |
|---|---|
| Keypoints | KEYPOINTS_3D (tracker-named, inline names) · LANDMARKS_3D (standard-human named, NaN rows for missing) |
| Segment | SEGMENT_ORIGINS · ROTATIONS_LOCAL · ROTATIONS_WORLD (wxyz) · SEGMENT_LENGTHS (mm) |
| Derived | DERIVED_POINTS (rows: `center_of_mass`, `xcom`) |
| Overlay | OVERLAY_2D (per-camera detections) · OVERLAY_REPROJECTIONS |

Everything encodes to CBOR per [../03-transport/message-relay.md](../03-transport/message-relay.md).

## Segment lengths today

Published lengths are **live-measured**: the median observed origin→primary distance per segment
over a 30-frame rolling window, falling back to the authored rest-pose length until a segment has
measurements — see [segment-length-estimation.md](segment-length-estimation.md).

## The gate

The loop is verified end-to-end by `tests/test_full_loop.py` (synthetic rtmpose pose → mapping →
hydrate → resolve → compose → CBOR round-trip; arm abduction ≈90° with chest still) and
`pipelines/test_realtime_pipeline.py` (MockCameraGroup lockstep incl. CoM assertions). The manual
F5 run remains the user's gate: T-pose identity at start, arm bend without pop, hidden-hand
degradation, overlay match.
