# Current Work Plans

> **New here? Start with [`HANDOFF.md`](HANDOFF.md)** — a one-file orientation on the current state,
> the decisions already made, and the next work.

Engineering plans + design for the FreeMoCap **human-reconstruction rebuild** and its **self-describing
message stream** — the two intertwined efforts that turn synchronized camera frames into a
self-describing stream of a standard-human, VRM-1.0-aligned human.

> **How this folder is organized.** Split **by architectural layer** (below). Older spec sets (the
> `00–14` streaming-compatibility specs, `phase-1/`, and the message-model-cutover snapshot) are
> preserved verbatim under [`archive/`](archive/) — they are history, not guidance. These docs and the
> code are two faces of one design conversation — neither is authoritative on its own; where they
> disagree, reconcile (see House rules below).

## Layers (read in order)

**Start with [`ontology.md`](ontology.md)** — the seven-layer kinematic architecture, the now/future line, and the VMC Definition of Done. Then the layers below.

| # | Layer | Covers |
|---|-------|--------|
| **00** | [foundation/](00-foundation/) | Conventions (frames, units, quaternions), the keypoint/segment vocabulary, testing philosophy. |
| **01** | [data-model/](01-data-model/) | The standard-human structures: the VRM segment model, T-pose reference geometry, tracker→standard-human mappings, and the message contract. |
| **02** | [pipeline/](02-pipeline/) | The engine: kinematics, segment-length estimation, the realtime loop, the posthoc path. |
| **03** | [transport/](03-transport/) | The wire: the message protocol, the backend relay, the streaming hub + adapters, the HTTP control plane, on-disk serialization. |
| **04** | [ui/](04-ui/) | The frontend: the message dispatcher (TransportService), the client homes, the renderers, the test-suite plan. |
| — | [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | The one cross-cutting tracker: scope table + progress log. |

## Status

The **first milestone is reached**: the full end-to-end pipeline works — cameras → keypoints → mapping →
length estimation + fit → orientation solve → self-describing frame message → transport → decode → 3D
rigid-body render. The wire is a self-describing CBOR stream of five kinds (`frame` / `log` /
`framerate` / `app_state` / `progress`); the frame is a fully self-describing document (convention +
cameras + models + instances + trackers + image).

**The current iteration** rebuilds the skellyforge standard human onto the full seven-layer ontology —
keypoint → mapping → landmark → segment → linkage → chain → skeleton — defined in **YAML** and compiled
into typed objects (references are objects, not strings):

1. **Ontology classes** — `AnatomicalLandmark` / `RigidBodySegment` / `JointLinkage` / `KinematicChain` /
   `HumanSkeleton` / `StandardHumanTPose` (+ `FaceBlendShapes` for the 52 ARKit blendshapes). Done.
2. **YAML definitions** — the standard human split into flat part files (pelvis, axial, arm, hand, leg,
   foot, face) with sidedness + Y-mirroring + `$include` composability. The full hand (8 carpals + 5
   metacarpals + 14 phalanges ×2 sides) and foot (7 tarsals + 5 metatarsals + 14 phalanges ×2 sides)
   anatomy is authored. Done — 95 segments / 94 linkages / 25 chains / 146 landmarks.
3. **Solve/hydration port** — `build_standard_human_tpose` + the re-pointed `solve_frame_orientations`
   (Kabsch for 3+ landmarks, swing+twist for 2, `(result, state)` split) + the stateless
   `rigidify_landmarks`. Done.
4. **Per-segment length estimation** — `estimate_segment_lengths` (a pure `(result, state)`
   rolling-median action) adapts each segment to the live subject independently — no uniform scaling.
   Done.
5. **Realtime re-point** — the aggregator, message model, producers, and websocket now load
   `HumanSkeleton.standard_human()` + the new solve; the old freemocap `RealtimeSkeletonRigidifier` and
   `tracker_contract.py` were deleted. Done (the live loop runs + overlays match).
6. **Lazy heavy-dependency imports** — `mediapipe` + `onnxruntime` are imported inside their detector /
   session functions, not at module scope, so sub-process startup stays cheap. Done.

## Next work (in order)

1. **Validate the realtime loop** — confirm the live loop runs the new core end to end (T-pose identity at
   start, arm bend without pop, hidden-hand degradation, overlay match).
2. **Charuco re-implementation** — author the calibration board as a YAML skeleton (one rigid segment +
   marker-corner landmarks, `sided: false`) + re-point the charuco path. This tests extensibility and
   forces the rename (`HumanSkeleton` → a neutral `Skeleton`; `StandardHumanTPose` → a neutral
   rest-pose).
3. **Posthoc alignment** — re-point `skeleton_from_mediapipe_observations.py` + the `Human` actor to the
   new loader + solve; share the model + solver with realtime (realtime = damped, posthoc = batch).
4. **Unhydrated-segment fallback** — an unhydrated segment must follow its parent at its own T-pose rest
   direction (not the hardcoded `[0,1,0]`), so a hidden hand doesn't stick out sideways.
5. **Delete the old skellyforge system** — only after charuco + posthoc migrate: `segment_definition.py` /
   `dead_reference_geometry.py` / `rest_pose.py` / `body_part.py` / `hand_part.py` / `face_part.py` /
   `standard_human_model.py` / `segment_parts.py` / `human_bone_aliases.py` / `human_blendshapes.py` + `skellymodels/models/` + `managers/` + `tracker_info/*.yaml`.
6. Then: the VMC adapter, the frontend test suite.

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the live scope table + progress log.

## Conventions (the one-liner; full form in [00-foundation/conventions.md](00-foundation/conventions.md))

**mm · right-handed · +Z up · +X forward**, quaternions **wxyz**, **identity == T-pose**,
`q_local = conj(q_parent) · q_child`. Segments are VRM 1.0 rigid bodies; the standard human is
**95 segments**, composed from YAML parts (single-sourced in the [glossary](00-foundation/glossary.md)).

## House rules for these docs

- **Single source** — each fact lives in exactly one doc, cross-linked from the others. A fact stated
  twice is a bug.
- **Positive definitions** — a doc says what a thing *is*, not the infinite set of what it isn't.
- **Vocabulary** — keypoint (measured) · landmark (segment-local point) · segment (oriented volume), per
  [ontology.md](ontology.md).
- **Reconcile, don't defer** — no single artifact (code, docs, conversation) is authoritative. Where they
  disagree, resolve what is *right* and fix whichever one is stale; never treat one as gospel.
- **Scope lives here, not in history** — the current iteration's scope is this README +
  [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md); `archive/` and the progress log are history.
