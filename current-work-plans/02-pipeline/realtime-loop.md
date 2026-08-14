# Realtime Loop

> **Scaffold (2026-08-14) — pending ontology revision.** Full prose after the ontology discussion + the
> F5 gate.

**Describes:** `freemocap/core/pipeline/realtime/` — `realtime_aggregator_node.py`, `realtime_pipeline.py`,
`realtime_pipeline_manager.py`.
**Salvage:** [`archive/phase-1-work-plans/11-realtime-loop-completion.md`](../archive/phase-1-work-plans/11-realtime-loop-completion.md).

## What this covers
The full live path: cameras → tracker (keypoints) → mapping → length estimation + fit → orientation solve
→ stream schema/sample → transport. The `RealtimeAggregatorNode` is where per-frame reconstruction
happens and the aggregator output message is produced.

## Key facts (committed code)
- Frame source is the skellycam multiframe number (camera-group-monotonic); the aggregator output carries
  `frame_number` + `segment_lengths` + per-segment quaternions.
- Feeds the transport via `get_latest_aggregator_outputs(if_newer_than=…)` (newest-wins).

## Open
- **F5 (the gate):** full-loop tests + a manual run close this loop before the posthoc rebuild.
- **S2:** remove the per-frame old-model `StreamingSegmentLengthMonitor` from the aggregator.
- Transport robustness (**A2/B1/B2**) lives in [../03-transport/backend-encoder-ws.md](../03-transport/backend-encoder-ws.md).

## Reconciliation notes
Describe the loop in terms of the current segment model + length estimation, not the old bootstrap /
`_BONE_TO_LANDMARK` machinery (deleted).
