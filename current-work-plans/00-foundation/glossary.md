# Glossary

The shared vocabulary, defined once here — every other doc links.

## The model nouns (the ontology layers that exist in code)

- **keypoint** — a tracker-measured 3D world point, tracker-named (e.g. `left_shoulder` as mediapipe
  emits it). Pure measurement; no body meaning. *(skellytracker)*
- **landmark** — a named point declared in a segment's local frame: anatomical `definition`, owning
  `reference_frame` (= segment), `local_position` in body-height proportions (`H = 1.0` = floor to
  skull top). Its per-frame world hydration is a trajectory. Aliases (e.g. `femur` → `upper_leg`)
  resolve to canonical lowercase names once at load. *(skellyforge)*
- **segment** — a VRM-1.0-aligned rigid body: origin landmark at `[0, 0, 0]`, orientation, length.
  Local `+z` runs proximal → distal. Its `reference_geometry` names an `origin` plus signed axes
  (`x_axis`/`y_axis`/`z_axis`, each pointing `exact` or `approximate` at a landmark). **Fully
  specified** when it names a secondary axis (roll measured by Gram-Schmidt); otherwise
  **underspecified** (pins the primary direction, leaves roll free). Exactly three segments are
  fully specified today: `pelvis`, `thoracic`, `skull`. Every segment declares its
  `anatomical_segment` (de Leva chunk) in its component YAML. *(skellyforge)*
- **linkage** — two segments sharing a point: the child's `connect_at` is a parent-owned joint
  landmark. Authored as a `JointDefinition` in the skeleton's `joints:` section (bilateral joints once,
  via `sided: true`); its hydrated face is a `JointPose` carrying input provenance.
- **chain** — a path of linked segments from a `start` to an `end`; the unit of IK/FABRIK/twist-backfill.
  Authored in `chains:` and compiled into `KinematicChain` (5 declared: spine, both arms, both legs).
- **skeleton** — every landmark + segment (+ joint, chain) of one model, loaded and validated as one
  unit (`SkeletonDefinition`). **Generic, not human**: a skeleton is any rigid named thing, from the
  standard human (61 segments / 124 landmarks / 60 joints / 5 chains, +52 face blendshapes which are
  not skeleton components) down to a charuco board (one segment carrying its markers). Joints and
  chains are what an *articulated* skeleton adds; a rigid one has none, and is no less a skeleton.
- **landmark group** — a named set of a skeleton's landmarks (`charuco_corners`, `face`), optionally
  with a colour. How a consumer knows what a landmark *is* without parsing its name.
- **connection group** — a named set of landmark pairs a consumer should draw as edges
  (`charuco_grid`, `aruco_markers`, `skull_outline`), optionally with a colour. Distinct from
  **connections** below, which are segment-level.
- **derived quantity** — a computed property a skeleton opts into (`inertia`, `xcom`, `cop`,
  `roll_resolution`). Declared in the skeleton's `derived_quantities:`; asking for one whose inputs
  are undeclared raises at load. Centre of mass is *not* here — every skeleton has one
  ([../02-pipeline/biomechanics-layer.md](../02-pipeline/biomechanics-layer.md)).

## Pose vocabulary

- **rest pose (T-pose)** — the authored reference pose (`RestPose`): per segment an optional
  parent-relative `[w, x, y, z]` quaternion, defaulting to identity ("continues straight on from the
  parent"). The parent tree and `connect_at` live in the skeleton's `joints:` section, not here; walking
  joints × orientations yields world transforms + landmark positions. Authored in `rest_pose.yaml`,
  derived against a VRM humanoid — see [../01-data-model/reference-geometry.md](../01-data-model/reference-geometry.md).
- **hydration** — recovering each segment's pose for one frame from observed landmark world positions:
  **rigid fit** (closed-form Umeyama similarity over ≥3 observed landmarks) or **direction fit**
  (shortest-arc rotation taking the origin→primary-direction ray onto its observed ray). Both also
  recover a `scale_estimate`, because the authored template is dimensionless. Output is a
  `SkeletonPose` of frozen `SegmentPose`s, each tagged with how it was solved.
- **`PoseSolution`** — `{RIGID_FIT | DIRECTION | TRANSPORTED_ROLL}`; read it before trusting a pose's roll.
- **roll resolution** — supplying the roll underspecified segments cannot measure: anchored secondary
  axes where the parent's origin direction is usable, parallel transport otherwise, and twist backfill
  from measured rigid-fit terminals. `ContinuousRollResolver` (stateful per take; `reset()` starts a new
  one; rigid-fit poses pass through untouched). There is no damping anywhere in the engine.
- **partial hydration** — `hydrate_skeleton(..., require_all=False)` skips segments whose landmarks are
  absent or degenerate this frame (occlusion is data); callers must tolerate missing segments rather
  than fake them.
- **connections** — the `(parent_segment, child_segment)` name pairs derived once from the joint
  topology and shipped inside `ModelDefinition`; no client ever re-derives hierarchy from `parent`
  fields.

## Mapping vocabulary

- **mapping** — the skellytracker-owned rule turning tracker keypoints into landmark observations
  (direct / mean / weighted / `anatomical_offset`, or **pass-through**). Applied in freemocap *before*
  hydration — see [../01-data-model/tracker-mapping.md](../01-data-model/tracker-mapping.md).
- **pass-through mapping** — a mapping that declares every tracked keypoint to be a landmark of the
  same name. The whole file is one flag. For an object whose markers *are* its landmarks (a charuco
  board), authoring a line per marker would be duplication with a chance of typos.
- **articulated model** — driven by whatever landmarks the tracker can observe this frame; there is no
  load-time "every landmark must be produced" contract.

## Transport nouns (see ../03-transport/message-protocol.md)

- **message** — the unit of the stream: a typed, versioned, self-describing value with an envelope
  (kind, version, timestamp, sequence) plus a kind payload. There is no schema and no sample.
- **kind** — a message-type tag (`frame`, `log`, `framerate`, `app_state`, `progress`). A new data type
  is a new kind.
- **frame** — the per-frame kind: convention + cameras + models + instances + trackers + image, with
  index-keyed channel blocks. All three of those are **plural**, always.
- **model** — one skeleton's static definition on the wire (`ModelDefinition`): its segments,
  landmarks, connections, groups, and `scale_reference_name`. Dimensionless.
- **instance** — one tracked *occurrence* of a model this frame (`ModelInstance`): its channels plus
  its `fitted_scale_mm`. Two people are two instances of one model; a person and a board are two
  models. Nothing may assume one of either.
- **tracker observation** — one detector's per-frame keypoints (`TrackerObservation`), 2D and 3D. A
  session runs several — a pose detector and a charuco detector are separate observations.
- **self-describing** — a message carries everything needed to decode AND render it — the full model
  rides every frame; no external descriptor, no cached schema to drift, no decode-vs-render split.
- **idempotent** — an update whose effect is the same however many times it is applied (full-snapshot
  replace, never a delta).
- **envelope** — the kind/version/timestamp/sequence header every message carries.
