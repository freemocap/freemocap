# 01 — Canonical Data Model

The canonical frame is the contract at the center of the system. Everything upstream produces
it; everything downstream — the UI, the LSL route, the protocol adapters — consumes its
serialized **standard stream** form. Getting this right is what lets adapters stay thin.

## Single Source of Truth: extend the existing frame

There is **one** canonical per-frame structure, not a parallel streaming-only type. It is the
pipeline's existing aggregation output — `AggregationNodeOutputMessage`
(`freemocap/core/pipeline/realtime/` → published on `AggregationNodeOutputTopic`) —
**extended** with the fields streaming needs. The 3D viewport, BVH export, and the streaming
hub all consume the same frame.

Rationale: two competing "frame" types is exactly the duplication the codebase's
Single-Source-of-Truth rule forbids. One frame, superset-shaped.

## The stream: schema + samples

The canonical frame is an in-process object. Its **streaming** form splits into two parts,
borrowing LSL's data model (and deliberately mirroring it, so the hub's LSL route is a
near-mechanical pass-through — see [02](02-streaming-hub.md)):

- **Schema (StreamInfo)** — the **static** facts, sent **once** on connect and again only when
  they change. This is the "schema" the pipeline needs regardless: it defines the channel /
  **landmark** names (canonical; *keypoints* are the tracker-side inputs — see
  [13](13-tracker-to-canonical-mapping.md)), the **joint hierarchy**, the **T-pose rest pose**
  (positions + reference orientations), the **coordinate convention** and **units**, the
  segment-rotation channels, and the sample layout (dtype / column order).
- **Sample** — the **dynamic** facts, one per frame: the numeric values **+ a timestamp**.
  Nothing static is repeated per frame. **The timestamp is the primary time key** — every sample carries one;
  the frame number is secondary (and won't exist for every sensor as we move toward mixed frame-rate sources).

> This is why coordinate convention, names, hierarchy, and rest pose live in the **schema**,
> not on every frame. A sample is just numbers and a timestamp. See
> [07 — Coordinate Conventions](07-coordinate-conventions.md).

The current protocol already half-does this (it sends `tracker_schemas` on connect, then
binary keypoint frames); this formalizes and completes that split as the standard stream.

## What the frame carries

The canonical frame is a **superset** — designed around what FreeMoCap *has*, not the lowest
common denominator of what consumers want. Adapters use the subset they need; the frame never
pre-discards. The **Where** column shows whether a fact is static (schema) or per-frame
(sample).

| Group | Field(s) | Where | Status | Notes |
|---|---|---|---|---|
| Identity | `frame_number`, `pipeline_id`, `camera_group_id` | sample/schema | exists | frame_number per sample; ids in schema. |
| Keypoints | `keypoints_arrays: dict[name, xyz]` | sample (names in schema) | exists | Filtered triangulated landmarks, **millimeters**. |
| Skeleton (positions) | `skeleton: dict[name, xyz]` | sample (names in schema) | exists | Rigidified canonical body+hand joints (mm), from `RealtimeSkeletonRigidifier`. |
| Center of mass | `center_of_mass_result`, `xcom` | sample | exists | Whole-body + segment CoM; extrapolated CoM. |
| **Segment rotations** | `segment_rotations: dict[segment, quaternion]` | sample (channels in schema) | **`[IN]` new** | Per-segment quaternion vs. rest pose. Owned by SkellyModels — see below. |
| **Subjects** | subject dimension / keying | sample + schema | **`[IN]` new** | Multi-subject from day one — see below. |
| **Convention / hierarchy / rest pose** | units, handedness, axes, joint hierarchy, T-pose | **schema** | **`[IN]` new** | Static — sent once, not per sample. See [07](07-coordinate-conventions.md). |
| Quality | `reprojection_error` (3D) / `visibility` (2D) per point | sample (channels in schema) | **`[IN]` new** | Named by what it is — 3D trajectories carry reprojection error (px, already computed); 2D overlays carry visibility. |

> The disabled `body_kinematics` field (inertia ellipsoid / ground references) is **not** part
> of this contract. See [Live substrate only](#live-substrate-only).

## Segment rotations — owned by SkellyModels (a module within SkellyForge)

Avatar and rig protocols need **rotations**, not just positions. Today the live frame carries
positions only.

**Ownership (decided):** the segment-quaternion representation is owned by **SkellyModels**
(the models module inside **SkellyForge**), extended to output per-segment quaternions. This
is the Single Source of Truth for rotation. The **freemocap realtime pipeline invokes
SkellyModels per-frame** and places the result on the canonical frame (a rotation channel in
the schema); the streaming hub, the 3D viewport, and BVH export all consume it. One
computation path, live and post-hoc.

**What we build on:**
- The **rigid-body / quaternion engine** copied+adapted from `bs/kinematics_core` into SkellyForge
  ([11](11-kinematics-fold-in.md)) — this *is* the segment-rotation engine; no external dependency to wait on.
- `RealtimeSkeletonRigidifier` (`freemocap/core/tasks/mocap/rigid_body/skeleton_rigidifier.py`) — the
  rigidified skeleton + per-bone directions each frame against the canonical `joint_hierarchy`.
- `AnatomicalStructure` (SkellyForge) — `segment_connections`, `joint_hierarchy`, `bone_length_ratios`, and
  the T-pose rest pose ([12](12-standard-human-model.md)).
- The **vestigial** post-hoc BVH exporter (`skellymodels/bvh_exporter/advanced_bvh_rotation.py`) —
  **replaced / augmented** by the folded-in engine, not converged-with.

The contract downstream is a per-segment quaternion channel with **identity == rest pose**.

### The rest-pose / T-pose reference

A rotation is meaningless without a reference orientation, so the **rest pose lives in the
schema**. The contract: **identity rotation == the declared rest pose (T-pose)**. Every
adapter that consumes rotations assumes a bone reading `(0,0,0,1)` is in the rest pose. This
is the single most common source of "my character is in a horrifying pose" bugs downstream, so
the rest pose is a *declared* schema artifact, not an implicit one.

The rest orientation per segment lives in the canonical human model in SkellyForge — the T-pose reference
geometry ([12](12-standard-human-model.md)) — surfaced in the schema, not re-derived per adapter.

## Multi-subject from day one

**`[IN]`** The realtime pipeline emits **one** subject per frame today. The canonical *contract*
nonetheless carries a **subject dimension** from the start, so that when multi-person tracking
lands, no adapter or wire format has to change shape — and so that streaming never reproduces
VMC's one-implicit-avatar flaw one layer up.

- Samples address subjects explicitly (a subject is a first-class key, even when there is
  exactly one).
- Adapters that cannot express multiple subjects (e.g. VMC — one avatar per `IP:port`) map
  **one subject per stream**; two subjects means two streams. See [03 — Emitters](03-emitters.md)
  and [04 — Control Plane](04-http-control-plane.md).

The subject key is a **stable id** where the tracker provides multi-person identity, else a slot index.
Subject **and camera counts are fixed at stream creation** (max persons = 1 for now; cameras = # connected);
a topology change **rebuilds** the stream with a new schema (schema-on-change). See the schema/sample split in
[09](09-standard-stream-protocol.md).

## Units and coordinate frame

FreeMoCap's canonical space is based on robotics/biomechanics standards — **millimeters,
right-handed, approximately Z-up** (ground-plane calibrated). This differs from many
animation-focused targets (VMC is meters / left-handed / Y-up). The convention is a **schema
fact**, declared once; adapters convert. Full treatment and the per-target table live in
[07 — Coordinate Conventions](07-coordinate-conventions.md).

## Live substrate only

The layer builds exclusively on the **live** data path:
- **Live (build on this):** the pub/sub `AggregationNodeOutputTopic`, `keypoints_arrays`, the
  rigidified `skeleton`, `center_of_mass_result`, `xcom`.
- **Disabled today (don't wire into the stream yet):** `StreamingKinematics`, `BodyKinematicsState`, and the
  inertia-ellipsoid / ground-reference code — switched off (per-frame update commented out), so
  `body_kinematics` ships as `None`. This code is **aligned, not deleted**
  ([06](06-backend-refactor-and-cleanup.md), [11](11-kinematics-fold-in.md)): it holds good material, but
  stays out of the hot loop and off the stream until validated.

Segment rotations — the one genuinely new stream capability — are produced by the kinematics engine folded in
from `bs/kinematics_core` ([11](11-kinematics-fold-in.md)).
