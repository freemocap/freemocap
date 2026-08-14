# 11 — Kinematics Fold-In

> Three codebases currently model "a human's kinematics." This doc maps their overlap and the work to
> fold them into one aligned engine — which is where the standard human's **segment rotations** come
> from ([01](01-canonical-data-model.md#segment-rotations--owned-by-skellymodels-a-module-within-skellyforge)).
>
> Testing for the folded-in engine is specified in
> [14 — Engine Testing Strategy](14-engine-testing-strategy.md).
>
> Status: **executed** — the engine lives in `skellyforge/kinematics/` and the orientation solve runs in the
> realtime aggregator. Remaining: the `[LATER]` alignment of the disabled centroidal-kinematics code, and
> the test suite ([14](14-engine-testing-strategy.md)), which does not yet exist.

## The three codebases

| Codebase | Role today | Maturity |
|---|---|---|
| **SkellyModels** (in SkellyForge) | The canonical model (landmarks, `segment_connections`, `joint_hierarchy`, `bone_length_ratios`, CoM defs) + the posthoc `Human` actor + batch biomechanics | Model = mature & SSOT; batch-only |
| **FreeMoCap `core/kinematics`** | An early, **mostly-disabled** alignment attempt (`BodyKinematicsState`, `StreamingKinematics`, `inertial/`) + live `segment_lengths.py` | Thin / stubbed / disabled |
| **`bs/kinematics_core`** | A **mature rigid-body kinematics engine**: per-segment pose + quaternion orientation + linear/angular velocity & acceleration + `ReferenceGeometry` + tidy serialization | Complete; **not integrated** |

(C:\Users\jonma\github_repos\freemocap_organization\bs\python_code\kinematics_core)


`clients/bs/python_code/kinematics_core/` contents: `RigidBodyKinematics` (position + `orientation`
quaternions + cached `velocity`/`acceleration`/`angular_velocity_[global|local]`/`angular_acceleration_*`
+ `keypoint_trajectories` + `reference_geometry`), `Quaternion` / `QuaternionTrajectory`,
`ReferenceGeometry` (rest pose + body-frame axis definition), `StickFigureTopology`, `Timeseries` /
`Vector3Trajectory`, and the tidy serialization ([10](10-serialization-and-tidy-format.md)).

## The overlap, precisely

- **`bs/kinematics_core` is the mature implementation of what FreeMoCap `core/kinematics` only stubbed.**
  The disabled `StreamingKinematics` / `BodyKinematicsState` gesture at orientation + angular kinematics;
  `bs/` actually implements them (per rigid body, with derivatives and body/world frames).
- **`bs/kinematics_core` is the rotation/kinematics engine** (confirmed) — the "segment-rotation code that
  lives elsewhere" referenced early on. Its `Quaternion` + `RigidBodyKinematics` produce the per-segment
  quaternions. There is **no separate pending dependency** — we have everything we need.
- **It is a *per-rigid-body* engine, not a human.** A human = **one rigid body per segment** (each a
  `ReferenceGeometry` + an orientation trajectory) **+** the landmark set attached to those segments.
  SkellyModels supplies the *model* (which landmarks, on which segments, rest pose); `bs/` supplies the
  *rigid-body kinematics* (orientation + derivatives per segment). They compose; they don't compete.
- **It is batch/posthoc-oriented** (whole-trajectory arrays, lazy derivatives). Realtime needs a
  per-frame streaming variant — exactly as `skeleton_rigidifier.py` is the streaming counterpart of the
  posthoc rigid-segment step.
- **Duplication to align on the FreeMoCap side**: the disabled `core/kinematics` path, and the
  hardcoded/misaligned segment lists (`LIMB_SEGMENTS` / `_SEGMENT_CHAINS`, already flagged by a
  `# TODO - Why tf is this not aligned with our skellyforge canonical skeleton defs??`).

## The fold-in plan (direction)

1. **Copy/adapt `bs/kinematics_core` — do NOT import it.** `bs/` is our code from a *different project*;
   it is **reference**, not a dependency. Re-implement its approach as a new engine in **SkellyForge**
   (do not `import python_code.kinematics_core`), aligned with SkellyModels. **Align, don't discard** the
   existing FreeMoCap `core/kinematics` (see Decisions).
2. **SkellyModels owns the anatomy; the engine owns the kinematics.** The canonical model provides each
   segment's definition + rest pose (→ a `ReferenceGeometry` per segment); the engine computes the
   per-segment orientation quaternions + derivatives. This is how "SkellyModels outputs segment
   quaternions" is actually implemented.
3. **Add a realtime (per-frame) variant** of the orientation solve for the live pipeline, mirroring the
   rigidifier pattern; the batch version stays for posthoc. Both share the definitions (no re-hardcoding).
4. **Replace/augment the vestigial BVH exporter.** The current skellyforge BVH rotation code
   (`skellymodels/bvh_exporter/advanced_bvh_rotation.py`) is largely vestigial — the new engine **replaces**
   (or augments) it, rather than converging with it.
5. **Feed the standard model**: the per-segment quaternions become the `rotations` channels of the
   standard stream ([09](09-standard-stream-protocol.md)) and the `orientation` trajectories of the tidy
   serialization ([10](10-serialization-and-tidy-format.md)).

## Connection to the standard human

This is the engine half of the **standard human** ([12](12-standard-human-model.md), decided: a VRM/VMC rig):
each humanoid segment is a `bs/`-style rigid body (reference geometry + orientation), and the copied-in kinematics
engine is what animates it.

## Decisions

- **Source (confirmed):** `bs/kinematics_core` is the rotation/kinematics engine — **copy/adapt, not import**.
- **Home (confirmed):** the engine lives in **SkellyForge**. Kinematics **consolidates** there — likely
  *moving* `freemocap/core/kinematics` into SkellyForge rather than keeping two kinematics folders (decide the
  move when we reach it). **Hard rule: SkellyForge never imports from FreeMoCap** (FreeMoCap imports SkellyForge).
- **Realtime variant:** a per-frame orientation solve for the live pipeline, sharing definitions with the
  batch engine (no re-hardcoding).
- **Existing `core/kinematics` — align, don't discard.** Do **not** delete the on-disk kinematics (there's
  good material there — e.g. the centroidal-CoM work — but it needs testing). Align it to the new models as
  much as possible, and keep **unvalidated paths out of the hot loop** until tested. Point the misaligned
  hardcoded segment lists (`LIMB_SEGMENTS` / `_SEGMENT_CHAINS`) at the canonical model.
