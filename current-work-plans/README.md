# Current Work Plans

> **STATUS — the realtime pipeline runs the rebuilt core end to end.** The standard human is the
> VRM-aligned re-authoring: **61 segments / 124 landmarks / 52 face blendshapes / 60 joints /
> 5 chains**, authored as **body-height proportions** (`H = 1.0`) in the Blender convention
> (+X right, +Y forward, +Z up), loaded by `SkeletonDefinition.from_default_yaml()` +
> `RestPose.from_default_yaml(skeleton=...)`, solved closed-form by `hydrate_skeleton(require_all=False)`
> + `ContinuousRollResolver` (anchored roll + twist backfill). The wire is a self-describing CBOR stream
> (including named joint angles) and the frontend consumes it data-driven; CoM / XCoM ride every frame.
> The old `skellymodels`/`post_processing`/`data_models` system is **deleted from skellyforge**;
> posthoc has an initial shared-core implementation, with the recording contract and restartable
> stage rebuild now planned in [02-pipeline/posthoc-rebuild.md](02-pipeline/posthoc-rebuild.md).

Engineering plans + design for FreeMoCap's **kinematic reconstruction rebuild** and its
**self-describing message stream** — the two intertwined efforts that turn synchronized camera frames
into a self-describing stream of tracked skeletons.

> **"Skeleton" is generic here.** A `SkeletonDefinition` describes any rigid named thing — the
> VRM-aligned standard human at one end, a one-segment charuco board at the other — and a frame
> carries several of them. Read "the human" throughout as the worked example, never as the contract
> ([ontology.md](01-data-model/ontology.md), [07-generic-skeletons/design.md](07-generic-skeletons/design.md)).

> **How this folder is organized.** Split **by architectural layer** (below). Older spec sets live
> verbatim under [`archive/`](archive/) — they are history, not guidance. These docs and the code
> are two faces of one design conversation — neither is authoritative on its own; where they
> disagree, reconcile (see House rules below).

## Layers (read in order)

**Start with [`ontology.md`](01-data-model/ontology.md)** — the seven-layer kinematic architecture, the now/future line,
and the VMC Definition of Done. Then:

| # | Layer | Covers |
|---|-------|--------|
| **00** | [foundation/](00-foundation/) | Conventions (frames, units, quaternions, mirroring), the vocabulary, testing philosophy. |
| **01** | [data-model/](01-data-model/) | The skeleton structures: component YAMLs + loader, rest-pose reference geometry, tracker→landmark mappings, the message contract. |
| **02** | [pipeline/](02-pipeline/) | The engine: math kernel + solve, the biomechanics layer, model-scale fitting, the realtime loop, the posthoc path. |
| **03** | [transport/](03-transport/) | The wire: protocol, backend relay, hub + adapters, HTTP control plane, on-disk serialization. |
| **04** | [ui/](04-ui/) | The frontend: TransportService dispatch, client homes, renderers. |


## Status (what has landed)

1. **Core classes** — `AnatomicalLandmark` / `RigidBodySegment` / `SkeletonDefinition` / `RestPose`
   / `SegmentPose`–`SkeletonPose`–`PoseSolution` / `JointDefinition` / `KinematicChain` /
   `FaceBlendShapes`. All seven ontology layers are constructed, none are placeholders.
2. **YAML definitions** — seven `$include` components (pelvis, spine, skull, arm, hand, leg, foot)
   with sidedness + x-mirroring; bilateral **segments, landmarks, and joints** authored once via
   `sided: true`; `rest_pose.yaml` (relative quats) derived against `default-vrm.gltf.json5`.
   Every segment declares its `anatomical_segment` (de Leva chunk). Loads green: 61 segments /
   124 landmarks / 60 joints / 5 chains.
3. **Closed-form solve** — Umeyama similarity rigid fit (≥3 observed landmarks), shortest-arc direction fit
   otherwise; `ContinuousRollResolver` supplies underspecified roll by anchored secondary axes with
   parallel-transport fallback and twist-backfill from measured rigid-fit terminals. No damping;
   partial hydration skips unobservable segments.
4. **Linkage + chain layers** — `relative_orientation` + per-joint euler `decompose/compose` →
   named joint angles with input provenance; FK synthesis, two-bone IK + FABRIK (fail-loud on
   unreachable targets), twist backfill; joint angles ride the wire as a `JOINT_ANGLES` channel.
5. **Spine/thorax redesign** — the trunk is partitioned at tracker-solid lines (hip center, shoulder
   midpoint, ear mean): `sacrolumbar` → `thoracic` → `cervical_spine` → `skull`, with the
   sternoclavicular joints anteriorly offset and xiphoid as the thoracic volume reference
   ([06-spine-thorax-redesign/design.md](06-spine-thorax-redesign/design.md)).
6. **Realtime loop** — ingest conversion → One Euro filter → velocity gate → mapping-before-hydration
   → hydrate → resolve → local/world rotations → reprojection overlay → CoM/XCoM → self-describing
   frame. Verified by `test_full_loop.py` + pipeline e2e tests.
7. **Biomechanics layer** — de Leva anthropometry, partial-CoM-aware segment CoMs, whole-body inertia,
   XCoM/CoP/CMP, derived kinematics; wired into the aggregator.
8. **Proportional authoring** — landmark coordinates are fractions of the skeleton's reference unit
   (`H = 1.0` = floor-to-skull-top for the human), so a template is size-agnostic.
9. **Model-scale fit** — a template gets its size from the data. The local→world map is a
   **similarity**, so hydration's rigid fit is Umeyama and every `SegmentPose` carries a
   `scale_estimate`; those pool into one fitted scale plus a per-segment scale field that relaxes to
   it where nothing was seen. Only segments the tracker mapping genuinely *measures* set the scale.
   Robust to partial views by construction — seated, with only the arms voting, an unseen foot fits
   within 0.2mm of its standing measurement
   ([02-pipeline/model-scale-fitting.md](02-pipeline/model-scale-fitting.md)).
10. **Generic skeletons** — a charuco board is a one-segment `SkeletonDefinition`, tracked,
   reconstructed and rendered on the human's machinery with no board-specific branch anywhere in the
   pipeline. Landmark + connection groups carry structure and tags; a palette resolves tags to colours
   backend-side; under-specified skeletons get defaults (single-root rest pose, unweighted CoM) while
   everything exotic is `derived_quantities` opt-in that fails loud at load; scale generalizes to each
   skeleton's own reference unit, so the board's fitted scale IS its measured square length. Models,
   instances and trackers are plural end to end, and the frontend iterates them
   ([07-generic-skeletons/design.md](07-generic-skeletons/design.md)).

## Next work (in order)

1. **One complete posthoc recording into canonical storage** — the recording contract and stage
   planner have focused tests. The mocap path saves observations/timing/raw 3D, world landmarks,
   segment origins/rotations and the complete frozen fit. Complete remaining channels, scientific
   definitions and checkpoint signatures. Prove saved-data
   reconstruction opens no video and constructs no detector. Verify keep/overwrite through worker
   execution. See [posthoc rebuild](02-pipeline/posthoc-rebuild.md) and
   [processing/playback contract](02-pipeline/processing-and-playback-integration.md).
   Timestamp-based playback and the default annotated `.freemocap.mp4` follow this milestone;
   the raw grid and additional formats are optional outputs.
2. **Pelvis split** — deferred from the spine redesign (ownership/cascade got tangled); a
   `left_pelvis`/`right_pelvis` pair under the root pelvis, for better shoulder/SC visuals.
3. **Implement the face component** — currently commented out (`#TODO`); blendshape plumbing exists.
4. **Finger coupling ratios** — authored per-finger MCP↔PIP↔DIP ratio constraints, enforced in
   synthesis/IK/backfill; the remaining deferred linkage/chain piece.
5. Then `[LATER]`: the VMC adapter, the HTTP control plane and the frontend test suite.

| Scope | Work |
|---|---|
| IN — next milestone | Canonical observation/timing ingestion, 3D outputs, detector-free reprocessing, worker keep/overwrite validation. |
| IN — follows milestone | Timestamp-based playback and shared-UI-overlay annotated grid output. |
| LATER | Optional raw grid/additional exports, remaining anatomy work, VMC adapter and broader frontend tests. |
| Separate SkellyCam follow-up | Unambiguous per-group acknowledgments/backpressure. |

**Check-in gate:** plans updated; no further implementation until the user confirms continuation.
Live camera operation after the SkellyCam buffer fix was confirmed by the user. See
[buffer validation](03-transport/skellycam-payload-ownership.md) for test coverage and limits.

## Conventions (the one-liner; full form in [00-foundation/conventions.md](00-foundation/conventions.md))

**Proportions of the skeleton's reference unit (`1.0` = body height for the human) · right-handed ·
Blender axes (+X right, +Y forward, +Z up)**, quaternions **wxyz**,
`q_local = conj(q_parent) · q_child`, ground plane at `z = 0`. Segments are VRM 1.0-aligned rigid
bodies; the standard human is **61 segments**, composed from YAML parts. Two principles decide
arguments: **sensible defaults, never runtime fallbacks**, and **structure travels in the model,
never in string patterns** (vocabulary single-sourced in the
[glossary](00-foundation/glossary.md), principles in
[00-foundation/conventions.md](00-foundation/conventions.md)).

## House rules for these docs

- **Typed construction** — prefer dataclasses/Pydantic models, enum values, named fields and factory
  methods over raw domain strings, string Literal types, positional channel indexing and long lists
  of unrelated keyword arguments. Keep serialized spellings at format boundaries. Group related
  processing inputs into validated request/domain objects; dynamic IDs and user names remain data.

- **Single source** — each fact lives in exactly one doc, cross-linked from the others. A fact stated
  twice is a bug.
- **Positive definitions** — a doc says what a thing *is*, not the infinite set of what it isn't.
- **Vocabulary** — keypoint (measured) · landmark (segment-local point) · segment (oriented volume),
  per [ontology.md](01-data-model/ontology.md).
- **Reconcile, don't defer** — no single artifact (code, docs, conversation) is authoritative. Where they
  disagree, resolve what is *right* and fix whichever one is stale; never treat one as gospel.
- **Scope lives here, not in history** — current scope is this README;
  `archive/` is history.
