# Current Work Plans

> **STATUS — the realtime pipeline runs the rebuilt core end to end.** The standard human is the
> VRM-aligned re-authoring: **61 segments / 124 landmarks / 52 face blendshapes**, loaded by
> `SkeletonDefinition.from_default_yaml()` + `RestPose.from_default_yaml(skeleton=...)`, solved
> closed-form by `hydrate_skeleton(require_all=False)` + `ContinuousRollResolver`, in the Blender
> convention (+X right, +Y forward, +Z up) with one conversion at skellycam ingest. The wire is a
> self-describing CBOR stream and the frontend consumes it data-driven; Center of Mass / XCoM ride
> every frame. The old `skellymodels`/`post_processing`/`data_models` system is **deleted from
> skellyforge**; freemocap's posthoc paths still import it behind lazy imports and are therefore
> broken-if-invoked — deferred by decision (see
> [02-pipeline/posthoc-rebuild.md](02-pipeline/posthoc-rebuild.md)).

Engineering plans + design for the FreeMoCap **human-reconstruction rebuild** and its **self-describing
message stream** — the two intertwined efforts that turn synchronized camera frames into a
self-describing stream of a standard-human, VRM-1.0-aligned human.

> **How this folder is organized.** Split **by architectural layer** (below). Older spec sets live
> verbatim under [`archive/`](archive/) — they are history, not guidance. These docs and the code
> are two faces of one design conversation — neither is authoritative on its own; where they
> disagree, reconcile (see House rules below).

## Layers (read in order)

**Start with [`ontology.md`](ontology.md)** — the seven-layer kinematic architecture, the now/future line,
and the VMC Definition of Done. Then:

| # | Layer | Covers |
|---|-------|--------|
| **00** | [foundation/](00-foundation/) | Conventions (frames, units, quaternions, mirroring), the vocabulary, testing philosophy. |
| **01** | [data-model/](01-data-model/) | The standard-human structures: component YAMLs + loader, rest-pose reference geometry, tracker→landmark mappings, the message contract. |
| **02** | [pipeline/](02-pipeline/) | The engine: math kernel + solve, the biomechanics layer, length estimation, the realtime loop, the posthoc path. |
| **03** | [transport/](03-transport/) | The wire: protocol, backend relay, hub + adapters, HTTP control plane, on-disk serialization. |
| **04** | [ui/](04-ui/) | The frontend: TransportService dispatch, client homes, renderers. |
| — | [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | The cross-cutting scope tracker: scope table + progress log. |

## Status (what has landed)

1. **Core classes** — `AnatomicalLandmark` / `RigidBodySegment` / `SkeletonDefinition` / `RestPose`
   / `SegmentPose`–`SkeletonPose`–`PoseSolution` / `FaceBlendShapes`. `SegmentLinkage` +
   `KinematicChain` exist as typed placeholders; nothing constructs them yet.
2. **YAML definitions** — seven `$include` components (pelvis, spine, skull, arm, hand, leg, foot)
   with sidedness + x-mirroring; `rest_pose.yaml` (parent tree + relative quats) derived against a
   real VRM humanoid (`default-vrm.gltf.json5`). Loads green: 61 segments / 124 landmarks /
   zero chains declared.
3. **Closed-form solve** — Kabsch rigid fit for fully-specified segments (≥3 observed landmarks),
   shortest-arc direction fit otherwise; `ContinuousRollResolver` supplies direction-only roll by
   per-take parallel transport. No damping anywhere; partial hydration skips unobservable segments.
4. **Realtime loop** — ingest-time frame conversion → One Euro filter → velocity gate →
   mapping-before-hydration → hydrate → resolve → local/world rotations → reprojection overlay →
   CoM/XCoM → self-describing frame (producers emit `ModelDefinition` including `connections`).
   Verified by `test_full_loop.py` + pipeline e2e tests.
5. **Biomechanics layer** — de Leva anthropometry, partial-CoM-aware segment CoMs, whole-body
   inertia, XCoM/CoP/CMP, derived kinematics; wired into the aggregator
   ([02-pipeline/biomechanics-layer.md](02-pipeline/biomechanics-layer.md)).
6. **Old system excised upstream** — `skellymodels`/`post_processing`/`data_models`/
   `tracker_info/*.yaml` no longer exist in skellyforge; tracker mapping YAMLs moved into
   skellytracker and are consumed read-only by freemocap.

## Next work (in order)

1. **Build the linkage/chain layer** — reconcile the hierarchy currently living in
   `rest_pose.yaml`'s `parent`/`connect_at` with the placeholder `SegmentLinkage`/`KinematicChain`
   classes; unblocks joint angles + IK later.
2. **Length-estimation cleanup** — live lengths are wired (rolling median in the aggregator); owed:
   delete-or-drive the dead `segment_length_window_s` config field, and decide inline-mirror vs.
   calling skellyforge's estimator directly
   ([02-pipeline/segment-length-estimation.md](02-pipeline/segment-length-estimation.md)).
3. **Implement the face component** — currently commented out of the composition (`#TODO`);
   blendshape plumbing exists.
4. **Posthoc rebuild** — deferred by decision; the old imports are already dead upstream, so the
   offline mocap/calibration paths are broken-if-invoked. Scope in
   [02-pipeline/posthoc-rebuild.md](02-pipeline/posthoc-rebuild.md).
5. Then `[LATER]`: the VMC adapter, the HTTP control plane, the frontend test suite, on-disk
   tidy serialization.

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the scope table + progress log.

## Conventions (the one-liner; full form in [00-foundation/conventions.md](00-foundation/conventions.md))

**mm · right-handed · Blender axes (+X right, +Y forward, +Z up)**, quaternions **wxyz**,
`q_local = conj(q_parent) · q_child`, ground plane at `z = 0`. Segments are VRM 1.0-aligned rigid
bodies; the standard human is **61 segments**, composed from YAML parts (vocabulary single-sourced
in the [glossary](00-foundation/glossary.md)).

## House rules for these docs

- **Single source** — each fact lives in exactly one doc, cross-linked from the others. A fact stated
  twice is a bug.
- **Positive definitions** — a doc says what a thing *is*, not the infinite set of what it isn't.
- **Vocabulary** — keypoint (measured) · landmark (segment-local point) · segment (oriented volume),
  per [ontology.md](ontology.md).
- **Reconcile, don't defer** — no single artifact (code, docs, conversation) is authoritative. Where they
  disagree, resolve what is *right* and fix whichever one is stale; never treat one as gospel.
- **Scope lives here, not in history** — current scope is this README + IMPLEMENTATION_PLAN.md;
  `archive/` and the progress log are history.
