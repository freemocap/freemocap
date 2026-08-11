# Phase 1 Handoff — 2026-08-11 (SF-SH milestone: all model/math workstreams complete)

## Start here (do this before touching code)

1. **Read the spec in order:** `docs/streaming-compatibility/` → `README` → `00`–`13` →
   `IMPLEMENTATION_PLAN.md` → `phase-1/README.md` → this file. These are the **source of truth
   for the plan**. Do **not** re-derive the design by reading the source tree.

2. **Workspace layout:** `project/CLAUDE.md`. Key fact: freemocap installs the skelly packages
   **from git, not from local checkouts** — a local skellyforge/skellytracker edit is invisible
   to the freemocap venv until the **user** commits + pushes it upstream. Then: `uv lock
   --upgrade-package <pkg>` followed by `uv sync`. Never commit — the user owns git.

3. Paths are workspace-relative. The freemocap **package** is double-nested: `freemocap/freemocap/…`.

4. **Cross-repo rules (hard, never violate):**
   - skellyforge NEVER imports from skellytracker, skellycam, or freemocap.
   - skellytracker NEVER imports from skellyforge, skellycam, or freemocap.
   - freemocap IS the integration layer — it imports from all sub-skelly repos.
   - Two pre-existing violations exist in skellyforge (TYPE_CHECKING only, not runtime):
     `data_models/observation.py` and `pipelines/dlc_pipeline.py`.

5. **Naming rules:** No single-word file or class names. All two+ words.

6. **Workstream labels:** `SF-` = skellyforge, `ST-` = skellytracker, `FMC-` = freemocap.

## Env

- **skellyforge** venv synced (`cd skellyforge && uv sync`). Pydantic added.
  Smoke: `uv run python -c "from skellyforge.kinematics import RotationQuaternion, TreeRigidifier, solve_frame_orientations; print('OK')"`
- **skellytracker** venv synced.
- **freemocap** venv synced (`cd freemocap && uv sync`; heavy — mediapipe/onnx).
  **IMPORTANT:** Freemocap locks skellyforge/skellytracker commits in `uv.lock`. After new commits
  to those repos, run `uv lock --upgrade-package skellyforge` (or skellytracker) before `uv sync`.
  Contract tests: `uv run pytest freemocap/tests/test_standard_stream_contract.py freemocap/tests/test_stream_schema_builder.py -q` (12 green).

## Where we are

### DONE

| Workstream | Repo | What |
|---|---|---|
| SF-SH-1 | skellyforge | Standard human model: bones, aliases, blendshapes, validators |
| SF-SH-3 | skellyforge | Kinematics engine: quaternion math, coordinate frames, rigid body |
| SF-SH-4 | skellyforge | Orientation solver: twist dispatch, world+local quaternions |
| ST-SH-2 | skellytracker | 4-form tracker mapping + anatomical_offset |
| SF-SH-5 | freemocap | Solver wired into aggregator, rotation fields on frame message |
| FMC-WS-1 | freemocap | Standard stream contract types + codecs (8 tests green) |
| FMC-WS-3(builder) | freemocap | Schema builder pure function (4 tests green) |

### NEXT

| Workstream | What |
|---|---|
| FMC-WS-3 (adapter) | Wire StandardHuman into schema builder |
| FMC-WS-2 | Backend encoder — reshape websocket to schema+samples |
| FMC-WS-4 | UI wedge — extract connection service, decode standard stream |

## Uncommitted

- **freemocap**: `pubsub_topics.py`, `realtime_aggregator_node.py`, `center_of_mass.py`, `uv.lock`
- These are the SF-SH-5 wiring changes. User must commit.

## Key decisions (LOCKED)

1. VRM 1.0 bones, VMC adapter maps down to VRM 0.x
2. Snake_case Python + separate alias table (human_bone_aliases.py)
3. Bones subsume segments — full rewrite, no backwards compat
4. Both world AND local quaternions in standard stream
5. Identity quaternion == T-pose
6. No single-word names
7. Skellyforge never imports from skellytracker or freemocap
8. Pydantic for config, dataclasses for hot-path, msgspec for wire

## File map

### skellyforge

```
skellyforge/skellymodels/standard_human/
├── human_bones.py              HumanBone, BoneReferenceGeometry,
│                               CoordinateFrameDefinition, TwistPolicy, TwistTier
├── human_bone_aliases.py       55-bone table, vrm+unreal targets
├── human_blendshapes.py        52 ARKit channels + VRM expression mapping
└── standard_human_model.py     StandardHuman Pydantic model + validators

skellyforge/kinematics/
├── quaternion_math.py          RotationQuaternion + 12 vectorized numpy fns
├── coordinate_frame_ops.py     basis, Kabsch, swing rotation
├── rigid_body_kinematics.py    RigidBodyKinematics + vectorized derivatives
├── orientation_solver.py       solve_frame_orientations, twist dispatch
├── skeleton_rigidifier.py      TreeRigidifier
├── online_segment_lengths.py   RollingBoneLengths
├── segment_lengths.py          SegmentDef, stats, report, monitor
└── inertial/
    ├── anthropometric_parameters.py
    ├── composite_inertia.py
    └── ground_reference.py
```

### skellytracker

```
skellytracker/core/io/
└── tracker_mapping.py          4-form system + anatomical_offset
```

### freemocap (new/changed)

```
freemocap/core/streaming/standard_stream/
├── coordinate_convention.py, stream_schema.py, stream_sample.py,
│   stream_schema_builder.py, lsl_bridge.py

freemocap/core/tasks/mocap/
├── body_kinematics_state.py, streaming_kinematics.py, segment_length_io.py
└── rigid_body/skeleton_rigidifier.py   (imports TreeRigidifier from skellyforge)

freemocap/pubsub/pubsub_topics.py       (segment_rotations_world/local)
freemocap/core/pipeline/realtime/realtime_aggregator_node.py
    (_get_standard_human, _build_solver_positions, _BONE_TO_LANDMARK)
```

### GONE

```
freemocap/core/kinematics/      Entire folder deleted
```

## Known issues / cleanup remaining

1. **skellyforge imports from skellytracker** (2 files, TYPE_CHECKING only): pre-existing.
2. **Old managers** not yet rewritten to StandardHuman: deferred to LATER.
3. **_BONE_TO_LANDMARK bridge** is temporary — moves into HumanBone.proximal_landmark.
4. **_get_standard_human()** bootstraps minimal model — should come from canonical definition.
5. **Hand reverse-map** in rigidifier — removed when standard stream lands.
6. **Legacy tracker model-infos** still referenced by posthoc — retire when rebuilt.
7. **Forward-axis** of canonical convention still TBD.
8. **Posthoc Human pipeline** still uses old tracker model-infos.
