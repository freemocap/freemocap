# The FreeMoCap Kinematic Ontology

The layered architecture for how FreeMoCap turns measured points into a kinematic model. It exists so
FreeMoCap can be a **boundary object** — one neutral core that biomechanics, robotics, and animation
each consume in their own format.

> **"Skeleton" is the generic term, not the human one.** A `SkeletonDefinition` is a hydratable
> specification of a rigid, named thing, and the same seven layers describe all of them:
>
> - a **fully specified** skeleton — the standard human: landmarks, segments, joints, chains, a rest
>   pose, biomechanics, roll conventions;
> - a **simple** skeleton — a charuco board: one segment carrying a set of landmarks.
>
> Everything in between works without new machinery. A layer a skeleton does not use is simply
> absent, not stubbed. Read every "the human does X" below as an *example* of a layer, never as its
> definition — that conflation is what let single-human assumptions accumulate in the first place.

The ontology is **seven layers**, and each layer is an object with two faces and its own math:

| # | Layer | Class | Static face (authored once) | Hydrated face (per frame) | Math it owns |
|---|-------|-------|------------------------------|---------------------------|--------------|
| 1 | keypoint | *(skellytracker)* | name | tracked position | — (measurement) |
| 2 | mapping | *(skellytracker)* | rule (keypoints → weights/offset) | the computation | weighted sum / offset |
| 3 | landmark | `AnatomicalLandmark` | name + anatomical definition + `local_position` + `reference_frame` | world position | trajectory |
| 4 | segment | `RigidBodySegment` | name + aliases + landmarks + reference geometry + `anatomical_segment` | pose (origin + orientation + `PoseSolution`) | rigid-body math (Umeyama similarity, shortest-arc) |
| 5 | linkage | `JointDefinition` | parent + child segments + shared landmark + euler convention | joint angle | relative orientation `conj(q_parent)·q_child` + decomposition |
| 6 | chain | `KinematicChain` | `start` → `end` segment path | chain pose | FK synthesis / IK / FABRIK / twist-backfill |
| 7 | skeleton | `SkeletonDefinition` | its landmarks + segments (+ joints, chains, rest pose) | whole pose | the composition |

Layers 1–4 and 7 are required of every skeleton. Layers 5–6 are what an *articulated* skeleton adds;
a rigid one simply has none.

## The layers

**keypoint** — a measured 3D world point, tracker-named. Pure measurement, no body meaning. It is
whatever the tracker emits — never derived, never added to. *(skellytracker)*

**mapping** — the one seam: the rule that **hydrates a landmark from keypoints** (direct / mean /
weighted / `anatomical_offset`). It converts measurement into an observation of a model point; it does
*not* define landmarks. *(the skellytracker ↔ skellyforge interface)*

**landmark** — a **named point defined in the local frame of a segment**. Its static face is a precise
**anatomical definition** plus a `local_position` in a named segment's frame (`reference_frame` —
explicit ownership, never "whoever declares it first"). Its hydrated face is a per-frame world position.
*(skellyforge)*

**segment** — a **rigid body**: origin + orientation + length, solved from its landmarks. **Fully
specified** when its reference geometry names a secondary axis (roll measured via Gram-Schmidt);
otherwise **underspecified** — origin + primary direction are measured, and roll is supplied by
convention: anchored to the parent's origin direction where available, parallel transport otherwise,
and twist-backfill where a measured rigid-fit terminal pins it (`ContinuousRollResolver`). Its `length`
derives from its rest-pose local positions, authored as body-height proportions. Each segment also
declares its `anatomical_segment` (the de Leva mass chunk it contributes to) in its component YAML.
*(skellyforge)*

**linkage** — **two segments that share a point** (e.g. upper arm + lower arm at the elbow). Authored
in the skeleton's `joints:` section as a `JointDefinition` — parent + child segments, the shared
`connect_at` landmark, and a per-joint euler convention that decomposes the relative orientation into
named angles. Its hydrated face is a `JointPose` carrying input provenance (which `PoseSolution`s fed
it). *(skellyforge)*

**chain** — **three or more linked segments**: a **path** from a `start` segment to an `end` segment
in the tree. Straight (a limb) or branching (the wrist fan). Authored in `chains:` and compiled into
`KinematicChain`; owns multi-segment math — FK synthesis, IK/FABRIK, twist-backfill. *(skellyforge)*

**skeleton** — **the composition**: every landmark + segment of one model, loaded and validated as a
unit, plus its rest pose. Layers 5 and 6 are optional — a skeleton of one segment has no joints and
no chains, and that is a complete skeleton, not a deficient one. What a skeleton does not declare it
gets by **sensible default** (a one-segment rest pose is its segment's rest pose; an undeclared mass
distribution gives an unweighted centre of mass); what a default cannot answer raises at load. See
[00-foundation/conventions.md](00-foundation/conventions.md). *(skellyforge)*

## The two faces (static vs. hydrated)

Every layer is defined once (static) and then **hydrated** with tracker data per frame (hydrated). The
static face lives in **YAML**; the hydrated face is computed at runtime. "When a landmark is hydrated
with data, it becomes a trajectory" — that is the spine of the whole system.

## Data in YAML, structure in code

Authored values (names, anatomical definitions, positions, parent edges, rest orientations) live in
**YAML**. The classes carry only structure, validation, and the per-layer math. Every *reference* in
the loaded model is an **object**, not a string — a typo fails the load at the offending line, never
silently.

- **Composability** — a dict with a single `$include: path` key loads that file in place; anything else
  is a plain value (a bare string is always a string, never a path). A model can be one file or many
  nested files.
- **Ownership** — a landmark declares its segment explicitly. No ordering convention.
- **Sidedness** — bilateral segments, landmarks, and joints are authored once with `sided: true` and
  compiled into `left_*` / `right_*` pairs; the right side mirrors x. No hand-duplicated left/right.
- **Scale** — coordinates are **proportions of the skeleton's own reference unit** (`1.0` = body height
  for the human, = square length for a charuco board), so a template is size-agnostic and the map from
  a segment's frame into the world is a **similarity**, not a rigid motion. Every hydrated segment
  carries a `scale_estimate`, and the **model-scale fit** pools those into one fitted scale plus a
  per-segment scale field — a segment nobody can see is sized by the pooled one
  ([02-pipeline/model-scale-fitting.md](02-pipeline/model-scale-fitting.md)).
- **Structure, never string patterns** — if a consumer needs to know that four landmarks form a
  square, the skeleton declares it as a connection group. Nothing downstream parses a name to recover
  structure it should have been handed.

## The constitution — invariants at every layer

- **Global unique IDs**, authored as side-agnostic **types** → compiled to **instances**.
- **Two faces** — static definition + per-frame hydration, at every layer.
- **Object references, not strings** — after load, every cross-reference is an object.
- **Each layer owns its math** — a landmark is a trajectory, a segment is a rigid body, a linkage is a
  joint, a chain is an IK path, a skeleton is the composition. No layer reaches into a higher layer;
  biomechanics reads skeleton+pose and is never imported by them.
- **Observation-first** — direct/FK where measured; closed-form fits, never iterative repair; roll by
  transport convention where unmeasurable.
- **Lean core + adapters** — VMC / URDF / VRM / OpenSim / C3D / LSL are edge projections.

## The boundary — who owns what

```
skellytracker  →  [ mapping: the one seam ]  →  skellyforge            →  freemocap
  keypoints          hydrate landmarks           landmark→segment→skeleton   pipelines + adapters
```

- **freemocap has two consumers of one model:** realtime (online, per-frame, partial hydration +
  transported roll) and posthoc (batch over full recordings — currently broken-if-invoked, deferred:
  [02-pipeline/posthoc-rebuild.md](02-pipeline/posthoc-rebuild.md)).
- **Adapters project the one skeleton outward:** VMC / LSL later
  ([03-transport/hub-and-adapters.md](03-transport/hub-and-adapters.md)).

## More than one skeleton at a time

A frame carries **several skeletons**, and several **instances** of each — the wire's `models`,
`instances` and `trackers` have always been plural. A tracked human and a tracked charuco board are
two skeletons; two people are two instances of one skeleton. Nothing in the pipeline may assume there
is exactly one of either ([01-data-model/message-contract.md](01-data-model/message-contract.md),
[07-generic-skeletons/design.md](07-generic-skeletons/design.md)).

*Status:* layers 1–7 are implemented and run in the realtime loop's stack: `AnatomicalLandmark`,
`RigidBodySegment` (with `anatomical_segment` declared per component), `SkeletonDefinition.from_default_yaml()`
(compiling `JointDefinition`s from `human_skeleton.yaml`'s `joints:` section — the authoritative
topology, bilateral joints authored once via `sided: true` — plus declared `chains:`), `RestPose`
(orientation-only; its tree comes from the joints), `hydrate_skeleton(require_all=False)`,
`ContinuousRollResolver` (anchored secondary axes + transport fallback + twist backfill from measured
rigid-fit terminals), and the derived biomechanics layer. Linkage hydrated math: `relative_orientation`,
euler `decompose/compose` under per-joint conventions, `JointPose`s with input provenance. Chain layer:
`KinematicChain` declarations, forward synthesis, two-bone IK + FABRIK (both fail-loud), twist backfill.
Coordinates are authored as proportions of each skeleton's reference unit (`H = 1.0` for the human);
the model-scale fit that turns them into measured millimetres is landed. The shipped human is 61
segments / 124 landmarks / 60 joints / 5 declared chains. Worked example:
[01-data-model/segment-model.md](01-data-model/segment-model.md).
