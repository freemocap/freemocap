# Realtime Loop

**Describes:** `freemocap/core/pipeline/realtime/` — `realtime_aggregator_node.py`, `realtime_pipeline.py`,
`realtime_pipeline_manager.py`.

## What this covers

The full live path: cameras → tracker (keypoints) → mapping → length + rigid fit → orientation solve
→ frame message → transport. The `RealtimeAggregatorNode` is where per-frame reconstruction happens and the
aggregator output message is produced.

## Key facts (committed code)

- Frame source is the skellycam multiframe number (camera-group-monotonic); the aggregator output carries
  `frame_number` + `segment_lengths` + per-segment quaternions.
- Feeds the transport via `get_latest_aggregator_outputs(if_newer_than=…)` (newest-wins).

## The stabilization stack

The stream is stabilized by the measurement stack alone; the future constraint/solve layer is **not**
needed for it:

1. **Euro filter** (skellycam) on the keypoints.
2. **Tree/fit rigidification** — enforced segment lengths/shapes: the 2-landmark tree pass **is** the old
   skeleton-rigidifier (same stabilizing effect, same math home); the 3+ per-group rigid fits (head 7 /
   hips 4 / feet 3 / toes 3, MDS template + rotation-only Procrustes) are strictly stronger.
3. **Critically-damped orientation solve** — per-segment, framerate-independent, tangent-space.

## Status

**Closed end to end (2026-08-18).** The loop now runs on the new core — `rigidify_landmarks` + the
re-pointed `solve_frame_orientations` (see [kinematics-engine.md](kinematics-engine.md)). The old
`SegmentLengthEstimator` / `StreamingSegmentLengthMonitor` were deleted with the freemocap rigidifier
wrapper.
