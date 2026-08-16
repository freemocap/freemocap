# Realtime Loop

> **Scaffold (2026-08-14) — pending ontology revision.** Full prose after the ontology discussion + the
> F5 gate.

**Describes:** `freemocap/core/pipeline/realtime/` — `realtime_aggregator_node.py`, `realtime_pipeline.py`,
`realtime_pipeline_manager.py`.
**Salvage:** [`archive/phase-1-work-plans/11-realtime-loop-completion.md`](../archive/phase-1-work-plans/11-realtime-loop-completion.md).

## What this covers
The full live path: cameras → tracker (keypoints) → mapping → length estimation + fit → orientation solve
→ frame message → transport. The `RealtimeAggregatorNode` is where per-frame reconstruction
happens and the aggregator output message is produced.

## Key facts (committed code)
- Frame source is the skellycam multiframe number (camera-group-monotonic); the aggregator output carries
  `frame_number` + `segment_lengths` + per-segment quaternions.
- Feeds the transport via `get_latest_aggregator_outputs(if_newer_than=…)` (newest-wins).

## The stabilization stack (settled 2026-08-14 — no new work)

The stream is stabilized by the measurement stack alone; the future constraint/solve layer is **not**
needed for it:

1. **Euro filter** (skellycam) on the keypoints.
2. **Tree/fit rigidification** — enforced segment lengths/shapes: the 2-landmark tree pass **is** the old
   skeleton-rigidifier (same stabilizing effect, same math home); the 3+ per-group rigid fits (head 7 /
   hips 4 / feet 3 / toes 3, MDS template + rotation-only Procrustes) are strictly stronger.
3. **Critically-damped orientation solve** (D3/D4) — per-segment, framerate-independent, tangent-space.

The old rigidifier's effect is fully preserved; the future linkage layer adds constraints, not stability.
See [the ontology](../ontology.md)'s constraint/solve section.

## Open
- **F5 (the gate):** full-loop tests + a manual run close this loop before the posthoc rebuild.
- **S2:** remove the per-frame old-model `StreamingSegmentLengthMonitor` from the aggregator.
- Transport robustness (**A2/B1/B2**) lives in [../03-transport/message-relay.md](../03-transport/message-relay.md).

## Reconciliation notes
Describe the loop in terms of the current segment model + length estimation, not the old bootstrap /
`_BONE_TO_LANDMARK` machinery (deleted).
