# WS-5 — Kinematics Engine Fold-In → Rotations (parallel track)

> The largest workstream. Runs **parallel** to WS-1…4 and **fills the rotation channels they declare** (per the
> positions-first decision — it does *not* block the Phase-1 stream reshape). Realizes
> [11](../11-kinematics-fold-in.md), [12](../12-standard-human-model.md), [13](../13-tracker-to-canonical-mapping.md).
> **Status: plan for agreement (decomposition) — no code until agreed; likely spawns its own sub-folder.**

## Goal

Copy/adapt `bs/kinematics_core` into SkellyForge, build the standard-human rig, produce per-segment quaternions
live, and populate the declared rotation channels — the same engine serving realtime + posthoc + BVH.

## Sub-workstreams

- **5a — Engine copy-in (SkellyForge).** Copy/adapt (**do not import**) from
  `clients/bs/python_code/kinematics_core`: `RigidBodyKinematics`, `Quaternion`/`QuaternionTrajectory`,
  `ReferenceGeometry` + `CoordinateFrameDefinition`, and the tidy serialization. → SkellyForge `kinematics/`
  module, aligned with SkellyModels. **Kinematics consolidates in SkellyForge** — we likely **move**
  `freemocap/core/kinematics` there rather than keep two kinematics folders (decide the move together when we
  reach it). Hard rule: **SkellyForge never imports from FreeMoCap** (FreeMoCap imports SkellyForge).
- **5b — Standard-human model.** VRM rig (bones), landmark→bone retarget, T-pose rest pose, and the
  **`anatomical_offset`** mapping form (SC / GH / hip centers) in the skellytracker mappings + canonical model.
  Also **finish removing the "virtual marker" concept** ([13](../13-tracker-to-canonical-mapping.md)).
- **5c — Twist policy.** Per-bone axis-source policy (full-frame → chain/hinge-resolved → damped-minimal
  fallback) — [12](../12-standard-human-model.md).
- **5d — Realtime per-frame solve.** A streaming variant of the orientation solve (mirrors
  `skeleton_rigidifier.py`), producing per-segment quaternions each frame.
- **5e — Wire into the frame.** The aggregator calls the solve; rotations fill the WS-3-declared channels. The
  same engine feeds posthoc; the **vestigial** skellyforge BVH exporter is **replaced/augmented** by the new
  engine (not converged-with).
- **5f — Consolidate + align into SkellyForge.** Move most/all of `freemocap/core/kinematics` into SkellyForge
  (FreeMoCap imports it; **SkellyForge never imports FreeMoCap**). Point `LIMB_SEGMENTS` / `_SEGMENT_CHAINS` at
  the canonical model; align the disabled centroidal-CoM code (out of hot loops until validated).

## Task checklist (high level — each sub-WS gets its own detail when we reach it)

1. [ ] 5a engine copy-in + unit tests (quaternion math, reference geometry).
2. [ ] 5b standard-human rig + retarget + `anatomical_offset` mappings + virtual-marker removal.
3. [ ] 5c twist policy.
4. [ ] 5d realtime solve.
5. [ ] 5e wire rotations into the frame / declared channels.
6. [ ] 5f align existing kinematics.

## Tests

- Engine: quaternion / reference-geometry unit tests (port bs/'s).
- `anatomical_offset`: SC joint lands anterior; deterministic; subject-scaled.
- Twist: chain-resolved vs. fallback; identity == T-pose.
- End-to-end: rotations populate the channels; VMC (Phase 3) can consume them.

## Not in scope (Phase 1)

VMC adapter (Phase 3); full scapula (later); face blendshapes (later — null).

## Note on depth

WS-5 is large enough that, once we start it, it should get its own `phase-1/ws5/` sub-folder of
increasingly-specific plans (engine → rig → solve → wire). Planned at decomposition depth here so the
positions-first slice (WS-1…4) isn't blocked.
