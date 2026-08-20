# Glossary

The vocabulary shared across every layer, grounded in [the ontology](../ontology.md). The seven layers
are **keypoint → mapping → landmark → segment → linkage → chain → skeleton**; the data nouns are
**keypoint** (measured), **landmark** (segment-local anatomical point), and **segment** (rigid body).

## Data (the seven layers — see [ontology.md](../ontology.md))

- **keypoint** — a measured 3D world point, tracker-named. Pure measurement: exactly what the tracker
  emits — never derived, never added to. Produced by **skellytracker**.
- **mapping** — the one seam: hydrates a landmark from keypoints (direct / weighted / offset). The
  skellytracker ↔ skellyforge interface.
- **landmark** (`AnatomicalLandmark`) — a **named point defined in the local frame of a segment**.
  Static face: `name` + a precise `anatomical_definition` (medical language, e.g. "midpoint of the
  intercondylar fossa") + `rest_position` (a 3-vector, in the local frame named by
  `reference_frame`). Hydrated face: a per-frame world position (a trajectory). A landmark is a direct
  copy of a keypoint, or **built** from keypoints (mean / weighted sum / `anatomical_offset`, e.g.
  `head_vertex` / `foot_ball` / `jaw`).
- **segment** (`RigidBodySegment`) — a **rigid body**: origin + orientation + length, solved from its
  landmarks. **Fully specified** with 3+ non-collinear landmarks; **partially specified** with only 2
  (roll carried by the damped minimal-roll tier). Its `length` is **derived** from its landmarks'
  `rest_position` values.
- **linkage** (`JointLinkage`) — **two segments that share a point** (upper arm + lower arm at the
  elbow). Derived from the `parent` edges; the shared point is the child's `origin_landmark`.
- **chain** (`KinematicChain`) — **three or more linked segments**: a `start` → `end` path in the
  tree. Straight (a limb) or branching (the wrist fan = several chains sharing a start). The unit
  IK/FABRIK solves.
- **skeleton** (`HumanSkeleton`) — **a collection of chains** composing one standard human.
- **rigid child** — a segment authored `rigid_with_parent` that inherits its parent's pose instead of
  solving independently (declared, never inferred). Not used for the face: the eyes / ears / nose are
  LANDMARKS on the skull, not segments.

## The T-pose

- **standard human T-pose** (`StandardHumanTPose`) — the **whole** built reference pose: every
  segment's resolved reference geometry + every landmark's rest position, at `identity == T-pose`.
  Keyed to the standard human (other model families will each have their own T-pose).
- **reference geometry** — the **per-segment** resolved rest math: `origin` (3-vector), `basis` (3×3
  rest frame), `length`. A *part of* the segment, built from its landmarks + axes.

## Frame construction

- **axis (declaration)** — one of a segment's tagged local-frame axes: a **name** (`x`/`y`/`z`, which
  basis vector it defines) and a **`target_landmark`** (in the segment's `landmarks`). Its direction is
  `positions[target_landmark] − positions[origin_landmark]` — the segment's own geometry only. The axes
  tuple is a **construction recipe in order**: the first axis is the primary direction, the second (if
  present) is the twist direction.
  - **primary direction** — the segment's defining direction (the frame's hard seed), resolved directly
    every frame.
  - **twist direction** — a soft direction reference for a second basis axis, Gram-Schmidt'd against the
    primary direction; when absent, the segment's roll falls to the damped minimal-roll tier.
- **`exact` / `approximate` (the mapping's frame, NOT a segment's)** — the tracker→landmark
  `anatomical_offset` (skellytracker) builds its *own* construction frame from keypoints; its two seed
  axes are tagged `exact` (hard seed) and `approximate` (Gram-Schmidt'd hint). Same Gram-Schmidt recipe
  as a segment's primary/twist, but a *different object*: the mapping's keypoint frame that places a
  landmark, not a segment's local frame. The older words are kept deliberately here — don't conflate the
  two vocabularies (this resolves AUDIT §8.1).
- **standard human** — the composed `HumanSkeleton` (body midline + limbs ×2 + hands ×2 + face),
  defined in YAML and loaded by `HumanSkeleton.from_yaml`.

## Twist tiers (a *consequence* of the declaration, not a separate policy)

1. **Resolved** — a twist direction is declared and usable this frame → the roll resolves from the
   segment's own geometry.
2. **Damped-minimal** — otherwise → swing-only, roll carried by the critically-damped filter.

> The linkage/chain layers now own the constraint/solve math (joint angles, IK, twist-backfill) — see
> [ontology.md](../ontology.md). Twist at the *segment* level is still own-geometry-or-damped.

## Transport (the message model — see ../03-transport/message-protocol.md)

- **message** — the unit of the stream: a typed, versioned, self-describing value with an envelope
  (kind, version, timestamp, sequence) plus a kind payload. There is no schema and no sample.
- **kind** — a message type tag (frame, log, framerate, app_state, progress). A new data type is a new kind.
- **frame** — the per-frame kind: self-describing named column blocks (names inline) plus images.
- **self-describing** — a message carries everything needed to *decode* and *render* it — the full model
  rides every frame; no external descriptor, no cached schema to drift, and no decode-vs-render split.
- **idempotent** — an update whose effect is the same however many times it is applied (full-snapshot
  replace, never a delta).
- **envelope** — the kind/version/timestamp/sequence header every message carries.
