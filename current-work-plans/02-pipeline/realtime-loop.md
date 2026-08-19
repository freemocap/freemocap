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
2. **Rigidification** — `rigidify_landmarks` enforces each segment's rest length along the observed
   direction (a forward-pass tree), and fits each 3+-landmark rigid body (skull, pelvis, hand carpus,
   foot tarsus, chest, thigh, shin) to its rest shape by a rotation-pinned Procrustes.
3. **Critically-damped orientation solve** — `solve_frame_orientations` (Kabsch for 3+, swing+twist for
   2), per-segment, framerate-independent, tangent-space for the damped-minimal-roll tier.

## Status

**Closed end to end (2026-08-18).** The loop now runs on the new core — `estimate_segment_lengths` →
`build_standard_human_tpose(lengths)` → `rigidify_landmarks` → `solve_frame_orientations` (see
[kinematics-engine.md](kinematics-engine.md)). The old `SegmentLengthEstimator` /
`StreamingSegmentLengthMonitor` and the freemocap `RealtimeSkeletonRigidifier` wrapper were retired.
