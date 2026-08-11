# Phase 1 Handoff — 2026-08-11 (updated: SH-1 complete)

## Start here (do this before touching code)

- **Read the spec in order first:** `docs/streaming-compatibility/` → `README` → `00`–`13` →
  `IMPLEMENTATION_PLAN.md` → `phase-1/README.md` → `phase-1/NN-*.md` → this file. It is the **source of
  truth for the plan**. Do **not** re-derive the design by reading the source tree.
- **Workspace layout + cross-repo dev model:** `project/CLAUDE.md`. Key fact: freemocap installs the skelly
  packages **from git, not from the local checkouts** — a local skellyforge edit is invisible to the
  freemocap venv until the **user** commits it upstream. Verify skellyforge changes in **skellyforge's own**
  env.
- Paths here are workspace-relative. The freemocap **package** is double-nested: `freemocap/freemocap/…`.
- **Never commit** (user owns git). beartype is on package-wide → keep annotations clean.
- If scope/sequence is unclear after reading the spec, **ask — don't guess.**

## Env

- freemocap venv is **synced** (`uv sync` in `freemocap/`; heavy — mediapipe/onnx).
- Contract tests (baseline, 12 green):
  `cd freemocap && uv run pytest freemocap/tests/test_standard_stream_contract.py freemocap/tests/test_stream_schema_builder.py -q`
- skellyforge venv is **now synced** (`cd skellyforge && uv sync` — pydantic added as a new dependency).
  Smoke-test the standard human model:
  `cd skellyforge && uv run python -c "from skellyforge.skellymodels.standard_human import StandardHuman, HumanBone, get_blendshape_count; print(f'OK — {get_blendshape_count()} blendshape channels')"`

## Where we are (all threads)

| Thread | Status | Plan |
|---|---|---|
| WS-1 — standard-stream contract (schema+sample+codecs) | **done**, 8 tests | [phase-1/01](01-standard-stream-contract.md) |
| WS-3 — schema **builder** (pure) | **done**, 4 tests | [phase-1/03](03-canonical-frame-extensions.md) |
| SkellyModels model layer → pure first-class landmarks | **done (skellyforge local — awaiting user commit)** | [13](../13-tracker-to-canonical-mapping.md) |
| Route **posthoc** through the mapping + retire legacy tracker model-infos | **remainder** | [13 — Remaining work](../13-tracker-to-canonical-mapping.md) |
| **SH-1 — Standard-human model** | **DONE** | [standard-human-model/](standard-human-model/README.md) |
| **SH-3 — Kinematics engine fold-in** | **NEXT (parallel track)** | [11](../11-kinematics-fold-in.md) |
| **SH-2 — Tracker-to-canonical mappings + anatomical_offset** | **NEXT (parallel with SH-3)** | [13](../13-tracker-to-canonical-mapping.md) |
| SH-4 — Orientation solve | gated on SH-1 + SH-3 | [standard-human-model/](standard-human-model/README.md) |
| SH-5 — Wire it up | gated on SH-1..4 | [standard-human-model/](standard-human-model/README.md) |
| WS-3 — SkellyForge adapter + aggregator wiring | pending (gated on SH-1) | [phase-1/03](03-canonical-frame-extensions.md) |
| WS-2 / WS-4 / WS-5 | not started | [02](02-backend-encoder-and-ws-reshape.md), [04](04-ui-wedge.md), [05](05-kinematics-foldin-rotations.md) |

**User's current priority:** SH-3 (kinematics engine) in parallel with SH-2 (tracker-to-canonical mappings).

## Where the last person stopped

**SH-1 is complete.** `skellyforge/skellymodels/standard_human/` contains the full standard human model:
`human_bones.py` (dataclasses), `human_bone_aliases.py` (55 bones, vrm+unreal targets),
`human_blendshapes.py` (52 ARKit + VRM expression mapping), `standard_human_model.py`
(Pydantic model with tree/hierarchy validators). Pydantic added as skellyforge dependency.
All smoke-tested green in the skellyforge venv.

**Next in priority order: SH-3 then SH-2, running in parallel.**

## Load-bearing decisions (all LOCKED — 2026-08-11)

These decisions were finalized in a strategic review of the streaming compatibility plan against
VRM/VMC/Unreal ecosystem realities. Each is stated with its rationale so subsequent work doesn't drift.

### 1. Canonical bone set: VRM 1.0 humanoid (full body + hands + face)
- Bones/hierarchy/finger model per VRM 1.0 spec.
- `upperChest` is included (optional in VRM 1.0, but required for full mocap fidelity).
- Thumb bones use VRM 1.0 naming: `metacarpal/proximal/distal`.
- **Rationale:** VRM 1.0 is a superset of VMC's HumanBodyBones; maps cleanly to Unreal Mannequin via
  a mechanical name swap; has a path to Khronos/ISO standardization.
- **VMC wire compatibility:** the Phase-3 VMC adapter maps VRM 1.0 thumb names → VRM 0.x names
  (`metacarpal` → `Proximal`, etc.) and expression names downward. The canonical model stays VRM 1.0.

### 2. Naming convention: snake_case Python + separate alias table
- Every bone is keyed `snake_case` in Python and the model (`left_upper_arm`).
- Aliases live in a **separate table** (`human_bone_aliases.py`), NOT as attributes on the Bone object.
- A bone does not know it has alternate names for different wire protocols — that's a serialization concern.
- The alias table maps `canonical_name → {target: alias}` — adding a new target adds a column to the
  table, no bone definitions change.
- `resolve_alias(bone_name, target) → str` is the single helper. Missing aliases fall back to the
  canonical name + log a warning.
- **Rationale:** a bone shouldn't know it's called `upperarm_l` in Unreal. The alias table is a single
  source of truth, testable independently, and cheap to extend.

### 3. Bones subsume segments — full rewrite, no backwards compatibility
- The old `segment_connections` in `canonical_body.yaml` / `canonical_hand.yaml` is replaced by a bone
  list where each bone carries its proximal/distal joint centers as part of `ReferenceGeometry`.
- `AnatomicalStructure`, `ModelInfo`, `AspectInfo`, `Actor`, `Human`, `Animal`, `Board` are **rewritten**
  onto the standard human model — not extended, not shimmed.
- The legacy tracker model-info YAMLs (`rtmpose_model_info.yaml`, `mediapipe_model_info.yaml`) are
  **retired**.
- **Rationale:** the old model mixes COCO-WholeBody landmarks, tracker-specific segment connections, and
  biomechanics CoM definitions. The new model is a single VRM-1.0-aligned humanoid with per-bone reference
  geometry. Two parallel structures that can disagree violates "fail loudly."

### 4. Face: 52 ARKit blendshape channels, declared now, wired later
- The model declares 52 ARKit blendshape channels in the schema.
- Values are `null`/`NaN` on the stream until SkellyTracker's face tracking populates them.
- The VMC adapter will carry an ARKit→VRM expression mapping (well-documented, ~1:1 for most shapes).
- **Rationale:** declaring the maximal channel set now avoids changing the wire format later. Consumers
  that only want body bones ignore the face channels. Same pattern as LSL's fixed-channel-count
  `StreamInfo`.

### 5. Rotation channels: stream BOTH world AND local quaternions
- The canonical frame carries two rotation channel groups:
  - `ROTATIONS_WORLD` — per-bone quaternion relative to world frame
  - `ROTATIONS_LOCAL` — per-bone quaternion relative to parent bone
- Both share the identity == T-pose contract.
- The orientation solve computes both (local is one quaternion multiply from world).
- Wire cost: ~53 KB/s extra for 55 bones at 60fps — negligible.
- **Rationale:** research users (LSL) want world; avatar adapters (VMC, Unreal) want local. Neither
  is derivable from the other without walking the bone chain. Streaming both means adapters don't need
  to know the hierarchy.

### 6. File naming: no single-word names
- `bones.py` → `human_bones.py`; `aliases.py` → `human_bone_aliases.py`
- `blendshapes.py` → `human_blendshapes.py`
- The kinematics engine follows the same rule: `rigid_body_kinematics.py`, `coordinate_frame.py`,
  `quaternion_trajectory.py`, `orientation_solver.py`
- **Rationale:** single-word filenames collide across packages. `bones.py` could mean anything;
  `human_bones.py` is unambiguous.

### 7. Alias mechanism: external table, NOT bone attribute
- **Rejected:** `Bone.vrm_alias: str` as a field on the bone dataclass.
- **Adopted:** `BONE_ALIASES: dict[str, dict[str, str]]` in `human_bone_aliases.py`.
- Adding a target adds a column; missing aliases fail safely (fallback to canonical name + warning).
- **Rationale:** keeps the bone model clean; one lookup point; testable without constructing bone objects.

### 8. Reference geometry per bone (the engine foundation)
- Each bone carries a `ReferenceGeometry` with:
  - `proximal_joint_center`, `distal_joint_center` (T-pose positions)
  - `CoordinateFrameDefinition` (exact axis = bone long axis, approximate axis = twist source)
- Identity quaternion == bone in T-pose reference orientation.
- Twist policy encoded **declaratively** per bone (tier + twist source), not procedurally in the engine.
- The engine reads the policy and applies the corresponding math.

## Standard-human model file structure (SH-1 deliverable)

```
skellyforge/skellymodels/standard_human/
├── human_bones.py              # Bone, ReferenceGeometry, CoordinateFrameDefinition, TwistPolicy
├── human_bone_aliases.py       # BONE_ALIASES table + resolve_alias()
├── human_blendshapes.py        # 52 ARKit blendshape channel declarations (VRM expression mapping noted)
├── standard_human_model.py     # StandardHuman model: bones + blendshapes + hierarchy + T-pose
└── (standard_human.yaml        # TBD — or defined purely in Python/Pydantic)
```

No single-word file names. The alias mechanism lives alongside the model, not inside it.

## Built so far — `freemocap/freemocap/core/streaming/standard_stream/`

`coordinate_convention.py` (`FREEMOCAP_CANONICAL_CONVENTION`; forward_axis=+Y is an unconfirmed TODO) ·
`stream_schema.py` (msgspec `StreamSchema`; `ChannelKind = POINTS | ROTATIONS | OVERLAY_2D`) ·
`stream_sample.py` (binary; header/block sizes **32/28 locked by test**) · `stream_schema_builder.py`
(`build_stream_schema`, pure) · `lsl_bridge.py`. Tests:
`freemocap/freemocap/tests/test_standard_stream_contract.py`, `test_stream_schema_builder.py`.

## Load-bearing invariants (with status)

- **Computed landmarks come only from the tracker→canonical mapping** (string / list-mean / weighted-sum);
  the canonical model is a pure landmark list + anatomy. — *established (realtime); posthoc to follow.*
  [13](../13-tracker-to-canonical-mapping.md)
- **`anatomical_offset`** mapping form for off-surface centers (SC / GH / hip). — *active.*
- **SkellyForge never imports FreeMoCap**; kinematics consolidates INTO skellyforge. — *rule.*
- **Rotations owned by SkellyModels**, streamed as world+local quaternions; identity == T-pose. — *locked.*
- LSL: fixed channel count per stream; topology change → teardown+rebuild. Timestamp is the primary key;
  images = separate stream (linked by frame#). Quality naming: 3D→`reprojection_error`, 2D→`visibility`.
  `msgspec` schema. — *decided.*
- **Bone aliases live in a separate table**, not as bone object attributes. — *locked.*
- **No single-word file names** anywhere in skellyforge or the streaming module. — *active.*
- **Bones subsume segments** — full rewrite of `AnatomicalStructure`/`ModelInfo`/managers onto the
  standard human. No backwards compatibility. — *locked.*
- **VRM 1.0 is the canonical bone set**; VMC adapter maps down to VRM 0.x names on the wire. — *locked.*

## Open decisions

- Batched `TrackerMapping.apply` for posthoc (per-frame loop vs. vectorized).
- Forward-axis of the canonical convention (`TBD` — confirm against the ground-plane calibration basis).
- T-pose joint positions: defined explicitly in YAML vs derived from anthropometric ratios + hierarchy.
- Whether the standard human model is a Python/Pydantic definition or a YAML file (or both — YAML for
  readability, Pydantic for validation). Current canonical model uses YAML; Pydantic `BaseModel` is
  already used for `AnatomicalStructure`.

## Next actions (ordered, for SH-1)

1. [ ] Create `skellyforge/skellymodels/standard_human/` package — mechanical
2. [ ] Define `human_bones.py`: `Bone`, `ReferenceGeometry`, `CoordinateFrameDefinition`, `TwistPolicy`
       — needs decision on dataclass vs Pydantic vs msgspec
3. [ ] Define `human_bone_aliases.py`: `BONE_ALIASES` table + `resolve_alias()` — mechanical
4. [ ] Define `human_blendshapes.py`: 52 ARKit channel declarations — mechanical (standard list)
5. [ ] Define `standard_human_model.py`: `StandardHuman` model assembling bones + blendshapes + hierarchy
       + T-pose — the core SH-1 deliverable
6. [ ] Define T-pose reference positions (either explicit coordinates or derived from anthropometric
       ratios from `canonical_body.yaml` / `canonical_hand.yaml`)
7. [ ] Verify: model loads, validates, hierarchy is a tree, all bones have reference geometry, aliases
       resolve for `vrm` and `unreal` targets

## Per-target bone alias map (reference — not exhaustive)

This is the shape of `human_bone_aliases.py`. Documented here for clarity; the file is the SSOT.

```
canonical (snake_case)     VRM/VMC wire (camelCase)     Unreal Mannequin
─────────────────────────  ─────────────────────────    ────────────────
hips                        hips                        pelvis
spine                       spine                       spine_01
chest                       chest                       spine_03
upper_chest                 upperChest                  spine_05
neck                        neck                        neck_01
head                        head                        head
left_eye                    leftEye                     —
right_eye                   rightEye                    —
jaw                         jaw                         —
left_shoulder               leftShoulder                clavicle_l
left_upper_arm              leftUpperArm                upperarm_l
left_lower_arm              leftLowerArm                lowerarm_l
left_hand                   leftHand                    hand_l
left_upper_leg              leftUpperLeg                thigh_l
left_lower_leg              leftLowerLeg                calf_l
left_foot                   leftFoot                    foot_l
left_toes                   leftToes                    ball_l
(right side mirrors left)
```

Note: `left_eye`/`right_eye`/`jaw` have no standard Unreal Mannequin equivalent — they're VRM/MetaHuman
only. The Unreal adapter handles these via morph targets or omits them.
