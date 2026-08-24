# Glossary

The shared vocabulary, defined once here — every other doc links.

## The model nouns (the ontology layers that exist in code)

- **keypoint** — a tracker-measured 3D world point, tracker-named (e.g. `left_shoulder` as mediapipe
  emits it). Pure measurement; no body meaning. *(skellytracker)*
- **landmark** — a named point declared in a segment's local frame: anatomical `definition`, owning
  `reference_frame` (= segment), `local_position` in millimetres. Its per-frame world hydration is a
  trajectory. Aliases (e.g. `femur` → `upper_leg`) resolve to canonical lowercase names once at load.
  *(skellyforge)*
- **segment** — a VRM-1.0-aligned rigid body: origin landmark at `[0, 0, 0]`, orientation, length.
  Local `+z` runs proximal → distal. **Fully specified** when its `reference_geometry` pins three
  non-collinear points (roll measured); otherwise **direction-only** (origin + primary direction,
  roll supplied by transport). Exactly three segments are fully specified today: `pelvis`, `chest`,
  `skull`. *(skellyforge)*
- **linkage** — two segments sharing a point: the child's rest-pose `connect_at` is a parent-owned
  joint landmark. Layer pending (`SegmentLinkage` placeholder) — see
  [../01-data-model/segment-model.md](../01-data-model/segment-model.md).
- **chain** — a path of linked segments from a `start` to an `end`; the future unit of IK/FABRIK.
  Layer pending (`KinematicChain` placeholder). No chains are declared yet.
- **skeleton** — every landmark + segment of one model, loaded and validated as one unit
  (`SkeletonDefinition`). The standard human is 61 segments / 124 landmarks (+52 face blendshapes,
  which are not skeleton components).

## Pose vocabulary

- **rest pose (T-pose)** — the authored reference pose (`RestPose`): per segment a `parent`, an optional
  `connect_at` (a parent-owned landmark the origin sits on), and an optional parent-relative `[w, x, y, z]`
  quaternion; walking the tree yields world transforms + landmark positions. Identity orientation means
  "continues straight on from the parent". Authored in `rest_pose.yaml`, derived against a VRM humanoid —
  see [../01-data-model/reference-geometry.md](../01-data-model/reference-geometry.md).
- **hydration** — recovering each segment's pose for one frame from observed landmark world positions:
  **rigid fit** (closed-form Kabsch over ≥3 observed landmarks) or **direction fit** (shortest-arc
  rotation taking the origin→primary-direction ray onto its observed ray). Output is a `SkeletonPose`
  of frozen `SegmentPose`s, each tagged with how it was solved.
- **`PoseSolution`** — `{RIGID_FIT | DIRECTION | TRANSPORTED_ROLL}`; read it before trusting a pose's roll.
- **roll resolution** — supplying the roll direction-only segments cannot measure:
  `ContinuousRollResolver` parallel-transports each such segment's basis frame-to-frame within a take
  (stateful per take; `reset()` starts a new one; rigid-fit poses pass through untouched and output is
   tagged `TRANSPORTED_ROLL`). There is no damping anywhere in the engine.
- **partial hydration** — `hydrate_skeleton(..., require_all=False)` skips segments whose landmarks are
  absent or degenerate this frame (occlusion is data); callers must tolerate missing segments rather
  than fake them.
- **connections** — the `(parent_segment, child_segment)` name pairs derived once from the rest-pose
  parent tree and shipped inside `ModelDefinition`; no client ever re-derives hierarchy from `parent`
  fields.

## Mapping vocabulary

- **mapping** — the skellytracker-owned rule turning tracker keypoints into standard-human landmark
  observations (direct / mean / weighted / `anatomical_offset`). Applied in freemocap *before*
  hydration — see [../01-data-model/tracker-mapping.md](../01-data-model/tracker-mapping.md).
- **articulated model** — driven by whatever landmarks the tracker can observe this frame; there is no
  load-time "every landmark must be produced" contract.

## Transport nouns (see ../03-transport/message-protocol.md)

- **message** — the unit of the stream: a typed, versioned, self-describing value with an envelope
  (kind, version, timestamp, sequence) plus a kind payload. There is no schema and no sample.
- **kind** — a message-type tag (`frame`, `log`, `framerate`, `app_state`, `progress`). A new data type
  is a new kind.
- **frame** — the per-frame kind: convention + cameras + models + instances + trackers + image, with
  index-keyed channel blocks.
- **self-describing** — a message carries everything needed to decode AND render it — the full model
  rides every frame; no external descriptor, no cached schema to drift, no decode-vs-render split.
- **idempotent** — an update whose effect is the same however many times it is applied (full-snapshot
  replace, never a delta).
- **envelope** — the kind/version/timestamp/sequence header every message carries.
