# Handoff — the standard-human ontology rebuild (2026-08-18)

**Read this first.** It orients a fresh agent on the state of the rebuild, the architecture, the decisions
already made, and the next work. The layered plans live in this folder (start with `README.md` →
`ontology.md` → the `0X-*` layers). This file is the shortcut.

## Where we are

The **standard human was rebuilt onto a seven-layer ontology** and the **realtime pipeline now runs on it**.
The app starts, tracks, and renders. Two consumers of the model remain to migrate (charuco + posthoc), after
which the old skellyforge system is deleted.

The seven layers: **keypoint → mapping → landmark → segment → linkage → chain → skeleton** (see
`ontology.md`). Each layer is a typed object with a static (authored) face + a hydrated (per-frame) face.

## What is landed (committed across skellyforge + skellytracker + freemocap)

**skellyforge (`skellymodels/standard_human/` + `kinematics/`):**
- The entities: `AnatomicalLandmark`, `RigidBodySegment` (+ `AxisDefinition`), `JointLinkage`,
  `KinematicChain`, `HumanSkeleton`, `StandardHumanTPose`, `FaceBlendShapes`. Frozen `slots=True`
  dataclasses. References are **objects**, not strings.
- The YAML definitions in `definitions/` (flat files: `standard_human`, `pelvis`, `axial`, `arm`,
  `hand`, `leg`, `foot`, `face`). `$include: path` composes them. `sided: true` parts instantiate
  `left_* + right_*` (the right side mirrors only `rest_direction`, not `rest_position`). The full
  hand (8 carpals + 5 metacarpals + 14 phalanges ×2) and foot (7 tarsals + 5 metatarsals + 14 phalanges
  ×2) anatomy is authored: 95 segments / 94 linkages / 25 chains / 146 landmarks.
- The actions in `kinematics/`: `build_standard_human_tpose`, `solve_frame_orientations`
  (Kabsch for 3+ landmarks, swing+twist for 2, returns `(FrameOrientationResult, SolveState)`),
  `rigidify_landmarks`, `estimate_segment_lengths` (per-segment rolling median). **Entities carry
  pure accessors (`length`, `segments`, `segment_names`); anything that mutates/solves is a separate
  typed function** — no state-carrying solver classes.

**freemocap (the realtime path, re-pointed):**
- `realtime_aggregator_node.py` loads `HumanSkeleton.standard_human()`, builds the T-pose once, maps
  tracker keypoints → standard-human landmarks (`biomechanics.tracker_mapping.apply(...)`), runs
  `rigidify_landmarks` → `solve_frame_orientations`.
- `message_model.py`, `channel_helpers.py`, `producer_contexts.py`, `keypoints_producer.py`,
  `websocket_server.py` re-pointed to `HumanSkeleton` + the new accessors.
- Deleted: the old freemocap `RealtimeSkeletonRigidifier` wrapper (rigidification is now skellyforge's
  `rigidify_landmarks`) and skellyforge's `tracker_contract.py` (see "Decisions" below).

## The decisions already made (do NOT re-litigate without the user)

1. **Local-frame authoring.** Every landmark's `rest_position` is in its `reference_frame` segment's LOCAL
   frame. The primary direction's target sits at `+Y` (body) / `+Z` (face); the twist target at `+X`.
   Left and right are **identical local geometry** — only the world `rest_direction` mirrors Y.
2. **Primary/twist, not exact/approximate.** The axes tuple is the Gram-Schmidt recipe: the FIRST axis is
   the primary direction (hard seed), the SECOND is the twist direction (soft hint). No `kind` field.
3. **Lengths are derived, then estimated per-segment.** `RigidBodySegment.length = |primary target's
   rest_position|` is the empty-window seed; `estimate_segment_lengths` refines it per frame by a
   per-segment rolling median (window 2.5 s), adapting each segment to the live subject independently.
4. **Derived landmarks.** The model is **articulated**: a tracker hydrates the landmarks it can see (body +
   hand keypoints + `anatomical_offset`); the rest (toes, condyles, deep points) ride the segment's rigid
   solve. There is **no load-time "every landmark must be produced" completeness contract** — that was
   removed (`tracker_contract.py`).
5. **No `upper_chest`.** The axial chain is pelvis → spine → chest → neck → head; the
   sternoclavicular joints are landmarks on `chest`. The full skeleton is 95 segments / 94 linkages /
   25 chains / 146 landmarks.
6. **The face** is 52 ARKit blendshapes (`FaceBlendShapes`), all 0.0 for now. Eyes/ears/nose are LANDMARKS
   on the head, not segments.
7. **Full-word hand/foot anatomy, no abbreviations.** Every hand landmark carries `hand_`, every foot
   landmark `foot_`, every finger landmark `_finger_`, every toe landmark `_toe_`. Joints are written
   out (`metacarpophalangeal_joint`, `proximal_interphalangeal_joint`, `distal_interphalangeal_joint`,
   `interphalangeal_joint`) — no `mcp`/`pip`/`dip`/`ip`. Finger chains carry `finger`; toe chains
   carry `toe`. The pinky is `pinky` (never `little`).

## The gotchas that bit us (do not repeat)

1. **Map BEFORE `rigidify_landmarks`.** `filtered_keypoints` is keyed by TRACKER names; the rigidifier +
   solver + reprojection expect STANDARD-HUMAN names. Apply
   `biomechanics.tracker_mapping.apply(filtered_keypoints)` first.
2. **`config.width` / `config.height` are ALREADY rotated** (skellycam's `CameraConfig` swaps them for
   PORTRAIT). Do **not** swap them again when building `CalibratedCamera.image_size`.
3. **The camera ID is unstable** (a hash of the USB device path; changes on replug/reboot). It is a
   known-open problem (see `02-pipeline/` + the camera-ID notes), not the cause of the recent overlay
   bugs. The freemocap matching already falls back exact-id → index.
4. **Workflow:** skellyforge/skellytracker edits are inert until the **user** commits+pushes+\`uv sync\`s
   freemocap (installed from git, not a local editable link). Never commit/push — the user owns git.

## Next work (in order)

1. **Validate the realtime loop** — confirm the live loop runs the new core end to end (T-pose identity at
   start, arm bend without pop, hidden-hand degradation, overlay match).
2. **Charuco re-implementation** — author the calibration board as a YAML skeleton (one rigid segment +
   marker-corner landmarks, `sided: false`) + re-point the charuco path. This tests the extensibility and
   forces the rename (`HumanSkeleton` → a neutral `Skeleton`; `StandardHumanTPose` → a neutral
   rest-pose) so the human + board are two instances of one core.
3. **Posthoc alignment** — re-point `skeleton_from_mediapipe_observations.py` + the `Human` actor to the
   new loader + solve; share the model + solver with realtime (realtime = damped, posthoc = batch).
4. **Unhydrated-segment fallback** — an unhydrated segment must follow its parent at its own T-pose rest
   direction (not the hardcoded `[0,1,0]`), so a hidden hand doesn't stick out sideways.
5. **Delete the old skellyforge system** — only after charuco + posthoc migrate: `segment_definition.py`,
   `dead_reference_geometry.py`, `rest_pose.py`, `body_part.py`, `hand_part.py`, `face_part.py`,
   `standard_human_model.py`, `segment_parts.py`, `human_bone_aliases.py`, `human_blendshapes.py`, `skellymodels/models/` + `managers/` + `tracker_info/*.yaml`.
6. Then: the VMC adapter, the frontend test suite.

See `IMPLEMENTATION_PLAN.md` for the live scope table + progress log.
