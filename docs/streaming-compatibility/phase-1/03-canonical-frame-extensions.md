# WS-3 — Canonical-Frame Extensions

> Build order: right after WS-1, before WS-2. Realizes [01](../01-canonical-data-model.md).
> **Status: schema builder ✅** (`stream_schema_builder.py`, 4 tests green — declares convention, hierarchy,
> rotation + per-camera 2D-overlay channels, cameras). **SkellyForge adapter + aggregator wiring
> (`reprojection_error` / `subject_id` onto the frame) pending the freemocap env.**

## Goal

Extend the canonical frame + schema so the standard stream carries: coordinate **convention** (schema), a
**subject dimension**, per-point **confidence / reprojection error**, and **declared rotation channels** (NaN
until WS-5, per the positions-first decision).

## Files (evolve)

- `freemocap/pubsub/pubsub_topics.py` — `AggregationNodeOutputMessage` (+ reprojection error surfaced, subject
  dim reserved).
- `freemocap/core/pipeline/realtime/realtime_aggregator_node.py` — surface `raw_errors_px` (already computed
  in the aggregator) onto the frame as a **named** channel: **`reprojection_error`** (never a naked "errors").
- The **schema builder** (new, from WS-1) — build `stream_schema` from `AnatomicalStructure`: convention,
  `joint_hierarchy`, rest pose, and the ordered channel groups (POINTS — skeleton + derived CoM/xcom —
  **declared** ROTATIONS + per-camera OVERLAY_2D).
- SkellyForge canonical model — confirm convention + rest pose are exposed to the schema builder.

## The work

1. **Convention → schema (SSOT).** One definition of the canonical convention (mm / right / +Z; forward-axis
   `TBD`) → a schema value. No per-sample convention.
2. **Quality channels (named, not generic).** 3D trajectories carry **`reprojection_error`** (the POINTS
   block's 4th column, from `raw_errors_px`); 2D tracks/overlays carry **`visibility`** (the OVERLAY_2D 3rd
   column). Never a generic "confidence"/"errors" — name by what it is.
3. **Subject dimension.** Single-subject today; add `subject_id` to the sample (0 for now). The frame stays
   single-subject; the *contract* reserves the dimension so multi-subject needs no reshape.
4. **Rotation channels declared.** The schema declares per-segment rotation channels (names from
   `segment_connections` / hierarchy); samples carry **NaN** until WS-5 fills them.
5. **2D overlays declared.** The schema declares a per-camera 2D-overlay channel group (same landmark names as
   the 3D skeleton, 2D-only); samples carry one `OVERLAY_2D` block per active camera. (The data already exists
   as `skeleton_overlays`; camera *images* stay a separate stream.)

## Task checklist

1. [ ] Convention SSOT → schema value.
2. [ ] Surface reprojection error + confidence onto the canonical frame + into the POINTS block.
3. [ ] `subject_id` on the sample (single-subject → 0).
4. [ ] Schema builder declares the rotation channels (NaN values for now).

## Tests

- Schema built from the canonical model has the right channels / hierarchy / rest-pose / convention.
- Frame carries confidence + error; the sample encodes them.
- Rotation channels present in the schema; sample values are NaN.

## Not in scope

Rotation *values* (WS-5); multi-subject *tracking* (contract dimension only).

## Micro-decisions to confirm

- **Quality (resolved):** 3D trajectories → `reprojection_error`; 2D tracks/overlays → raw `visibility`.
- Forward-axis confirmation (the open convention `TBD`).
