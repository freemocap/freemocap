# The FreeMoCap Kinematic Ontology

The layered architecture for how FreeMoCap turns measured points into a standard human (and, later,
other) kinematic model. It exists so FreeMoCap can be a **boundary object** — one neutral core that
biomechanics, robotics, and animation each consume in their own format.

The ontology is **seven layers**, and each layer is an object with two faces and its own math:

| # | Layer | Class | Static face (authored once) | Hydrated face (per frame) | Math it owns |
|---|-------|-------|------------------------------|---------------------------|--------------|
| 1 | keypoint | *(skellytracker)* | name | tracked position | — (measurement) |
| 2 | mapping | *(skellytracker)* | rule (keypoints → weights/offset) | the computation | weighted sum / offset |
| 3 | landmark | `AnatomicalLandmark` | name + anatomical definition + `local_position` + `segment` | world position | trajectory |
| 4 | segment | `RigidBodySegment` | name + parent + landmarks + axes | pose (origin + orientation) | rigid-body math (Gram-Schmidt, Kabsch) |
| 5 | linkage | `JointLinkage` | parent + child segments + shared landmark | joint angle | relative orientation `conj(q_parent)·q_child` |
| 6 | chain | `KinematicChain` | `start` → `end` segment | chain pose | IK / FABRIK / twist-backfill |
| 7 | skeleton | `SkeletonDefinition` | its chains + segments | whole pose | the composition |

## The layers

**keypoint** — a measured 3D world point, tracker-named. Pure measurement, no body meaning. It is
whatever the tracker emits — never derived, never added to. *(skellytracker)*

**mapping** — the one seam: the rule that **hydrates a landmark from keypoints** (direct / mean /
weighted / `anatomical_offset`). It converts measurement into an observation of a model point; it does
*not* define landmarks. *(the skellytracker ↔ skellyforge interface)*

**landmark** — a **named point defined in the local frame of a segment**. Its static face is a precise
**anatomical definition** plus a `local_position` in a named segment's local frame (`segment` —
explicit ownership, never "whoever declares it first"). Its hydrated face is a per-frame world position.
*(skellyforge)*

**segment** — a **rigid body**: origin + orientation + length, solved from its landmarks. **Fully
specified** with 3+ non-collinear landmarks; **partially specified** with only 2 (roll is then carried
by the damped minimal-roll tier). Its `length` is **derived** from its landmarks' `local_position`
values. *(skellyforge)*

**linkage** — **two segments that share a point** (e.g. upper arm + lower arm at the elbow). Derived
from the `parent` edges — the child's `origin_landmark` *is* the shared point. *(skellyforge)*

**chain** — **three or more linked segments**: a **path** from a `start` segment to an `end` segment
in the tree. Straight (a limb) or branching (the wrist fan = several chains sharing a start). This is
the unit FABRIK/IK solves. *(skellyforge)*

**skeleton** — **a collection of chains** (arm + leg + axial chains) composing one standard human.
*(skellyforge)*

## The two faces (static vs. hydrated)

Every layer is defined once (static) and then **hydrated** with tracker data per frame (hydrated). The
static face lives in **YAML**; the hydrated face is computed at runtime. "When a landmark is hydrated
with data, it becomes a trajectory" — that is the spine of the whole system.

## Data in YAML, structure in code

Authored values (names, anatomical definitions, positions, parent edges) live in **YAML**. The classes
carry only structure, validation, and the per-layer math. Every *reference* in the loaded model is an
**object**, not a string — a typo fails the load at the offending line, never silently.

- **Composability** — a dict with a single `$include: path` key loads that file in place; anything else
  is a plain value (a bare string is always a string, never a path). A model can be one file or many
  nested files.
- **Ownership** — a landmark declares its `segment` explicitly (the segment whose local frame
  its `local_position` is in). No ordering convention.
- **Length** — derived from `local_position`, not authored as a ratio. Live subject adaptation is
  per-segment (a rolling median of each segment observed length), not a single uniform scale.

## The constitution — invariants at every layer

- **Global unique IDs**, authored as side-agnostic **types** → compiled to **instances**.
- **Two faces** — static definition + per-frame hydration, at every layer.
- **Object references, not strings** — after load, every cross-reference is an object.
- **Each layer owns its math** — a landmark is a trajectory, a segment is a rigid body, a linkage is a
  joint, a chain is an IK path, a skeleton is the composition. No layer reaches into a higher layer.
- **Observation-first** — direct/FK where measured; IK/constraint only where not.
- **Lean core + adapters** — VMC / URDF / VRM / OpenSim / C3D / LSL are edge projections.

## The boundary — who owns what

```
skellytracker  →  [ mapping: the one seam ]  →  skellyforge            →  freemocap
  keypoints          hydrate landmarks           landmark→segment→skeleton   pipelines + adapters
                                                 linkage→chain
```

- **freemocap has two consumers of one model:** realtime (online lengths, per-frame, damped) and posthoc
  (batch, unbounded window).
- **Adapters project the one skeleton outward:** VMC now; URDF / VRM / OpenSim / BVH later.

*Status:* the full seven-layer ontology — including linkage + chain — is defined and the port landed:
`AnatomicalLandmark` / `RigidBodySegment` / `JointLinkage` / `KinematicChain` / `SkeletonDefinition` /
`StandardHumanTPose`, each with `from_yaml`, and the YAML-based standard-human definition (95 segments /
94 linkages / 25 chains / 146 landmarks). The solve (`build_standard_human_tpose` +
`solve_frame_orientations` + `rigidify_landmarks`) and the per-segment length estimator
(`estimate_segment_lengths`) run in the realtime loop. See
[01-data-model/segment-model.md](01-data-model/segment-model.md) for the worked example.
