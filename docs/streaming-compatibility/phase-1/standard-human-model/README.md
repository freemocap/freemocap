# Standard Human Model — VRM-aligned canonical human + kinematics engine

> A **sub-plan of Phase 1**. Front-loaded from WS-5 because the streaming work (WS-2/3/4) can't be done
> cleanly until the canonical human is defined against a real avatar standard. Parent design:
> [01](../../01-canonical-data-model.md), [11](../../11-kinematics-fold-in.md),
> [12](../../12-standard-human-model.md), [13](../../13-tracker-to-canonical-mapping.md).
>
> Status: **plan — IMPLEMENT (SH-1 first). All design decisions LOCKED 2026-08-11.**

## The goal (one sentence)

Redefine the SkellyForge canonical "human" as a **VRM 1.0-aligned humanoid** — VRM 1.0 bones, hierarchy, and
T-pose — whose per-bone **position + orientation** are computed from tracker landmarks by a rigid-body
kinematics engine (folded in from `bs/kinematics_core`), so that **any tracker yields the same standard human**
that streams (schema + samples, with both world AND local quaternions) and exports to Blender identically.

## Decisions (LOCKED — 2026-08-11 — do not re-litigate)

1. **Bone standard: VRM 1.0 humanoid.** Bones/hierarchy/finger model per VRM 1.0 (thumb =
   metacarpal/proximal/distal). VMC (Unity `HumanBodyBones`, PascalCase, VRM 0.x names) is reached by the
   Phase-3 VMC adapter's name map — **not** the canonical key.
2. **Naming: snake_case primary + separate alias table.** Every bone is keyed by snake_case (`left_upper_arm`)
   in Python and the model. Aliases live in a **separate file** (`human_bone_aliases.py`) as
   `BONE_ALIASES: dict[str, dict[str, str]]` — NOT as attributes on the Bone object. A bone doesn't know it
   has alternate names. `resolve_alias(bone_name, target) → str` is the single helper. Missing aliases fall
   back to the canonical name + log a warning.
3. **Bones subsume segments — full rewrite, no backwards compatibility.** The old `segment_connections` in
   `canonical_body.yaml` / `canonical_hand.yaml` is replaced by bone definitions carrying proximal/distal
   joint centers in their `ReferenceGeometry`. `AnatomicalStructure`, `ModelInfo`, `AspectInfo`, `Actor`,
   `Human`, `Animal`, `Board` are **rewritten** onto the standard human. Legacy tracker model-info YAMLs
   (`rtmpose_model_info.yaml`, `mediapipe_model_info.yaml`) are **retired**. There is exactly one version of
   this code: the current one.
4. **Face = 52 ARKit blendshapes, declared but undriven.** The schema declares the 52 blendshape channels;
   values are `null`/`NaN` until wired from skellytracker face tracking (mirrors positions-first / rotations-NaN
   pattern). VRM expression mapping (ARKit→VRM) lives in the VMC adapter, not the canonical model.
5. **Rotation channels: BOTH world AND local quaternions.** The standard stream carries two rotation channel
   groups: `ROTATIONS_WORLD` (per-bone quaternion relative to world frame) and `ROTATIONS_LOCAL` (per-bone
   quaternion relative to parent). Both share identity == T-pose. The orientation solve computes both — local
   is one quaternion multiply from world. Wire cost is negligible (~53 KB/s for 55 bones at 60fps).
6. **No single-word file names.** `bones.py`→`human_bones.py`, `aliases.py`→`human_bone_aliases.py`,
   `blendshapes.py`→`human_blendshapes.py`. Same rule for the kinematics engine.
7. **Full scope:** the VRM-aligned model **and** the kinematics engine (copy/adapt `bs/kinematics_core`) **and**
   the live per-bone orientation solve land in this sub-plan.
8. **Replace, don't parallel (zero-backwards-compat).** The standard-human model becomes the **one** model
   layer; old code is rewritten, not shimmed.

## File structure (SH-1 deliverable)

```
skellyforge/skellymodels/standard_human/
├── human_bones.py              # Bone, ReferenceGeometry, CoordinateFrameDefinition, TwistPolicy
├── human_bone_aliases.py       # BONE_ALIASES table + resolve_alias()
├── human_blendshapes.py        # 52 ARKit blendshape channel declarations
├── standard_human_model.py     # StandardHuman model: bones + blendshapes + hierarchy + T-pose
└── (standard_human.yaml        # TBD — or defined purely in Python)
```

## Boundary (unchanged, reinforced)

- **SkellyTracker** owns tracker **keypoints + connections + `*_to_canonical_mapping.yaml`**.
- **SkellyForge** takes mapped **canonical landmarks** → builds the **standard human** (bones, hierarchy,
  T-pose, orientations). Tracker-agnostic output; **SkellyForge never imports FreeMoCap**.
- Blender / stream / BVH all consume the standard human, never the tracker.

## What we build on (real code)

- **Engine (reference):** `bs/python_code/kinematics_core` — `ReferenceGeometry` + `CoordinateFrameDefinition`
  (T-pose keypoints + body frame: origin + exact axis + approximate axis → cross product), `Quaternion`,
  `RigidBodyKinematics` (position + wxyz-quaternion trajectories + lazy derivatives + tidy serialization),
  `StickFigureTopology`. **Copy/adapt, do NOT import** (it's a different project).
- **Existing model layer (to be REPLACED):** `skellyforge/skellymodels/models/{anatomical_structure,
  tracking_model_info,aspect,trajectory}.py`, `managers/{actor,human,animal,board}.py` — rewritten onto the
  standard-human model.
- **Realtime rigidifier (pattern for the per-frame solve):**
  `freemocap/core/tasks/mocap/rigid_body/skeleton_rigidifier.py`.
- **Advanced methods to fold in:** `freemocap/core/kinematics/` (inertial/, streaming_kinematics,
  segment_lengths); the **vestigial** `skellyforge/skellymodels/bvh_exporter/advanced_bvh_rotation.py` is
  **replaced** by the new engine.

## Decomposition (ordered)

| WS | Scope | Where | Depends |
|---|---|---|---|
| **SH-1 — Standard-human model** | VRM 1.0 bones + hierarchy + alias table + connections + per-bone **reference geometry (T-pose + coordinate frame)** + 52 blendshape channel declarations. The canonical landmark set = bone joint-centers. | `skellyforge/skellymodels/standard_human/` (new) | — |
| **SH-2 — Tracker→canonical mappings** | Produce the model's landmarks (joint centers) from tracker keypoints; add `anatomical_offset` form for off-surface centers (SC/GH/hip). | skellytracker `*_to_canonical_mapping.yaml` + `TrackerMapping` | SH-1 |
| **SH-3 — Kinematics engine fold-in** | Copy/adapt `bs/kinematics_core` → `skellyforge/kinematics/`; align `freemocap/core/kinematics`; retire `advanced_bvh_rotation`. | `skellyforge/kinematics/` (new) | — (parallel with SH-1) |
| **SH-4 — Orientation solve** | Per-bone orientation from observed landmarks vs reference geometry (basis-alignment); **twist policy** encoded declaratively per bone (full-frame → chain/hinge → damped-minimal, with singularity gate at ~5° parallel). Batch + realtime variants. Produces BOTH world + local quaternions. Identity == T-pose. | `skellyforge/kinematics/` + a realtime solve mirroring the rigidifier | SH-1, SH-3 |
| **SH-5 — Wire it up** | Aggregator invokes the solve → fills BOTH `ROTATIONS_WORLD` + `ROTATIONS_LOCAL` channels. Rebuild posthoc `Human` on the standard human + mapping; retire `rtmpose_model_info.yaml`/`mediapipe_model_info.yaml`; BVH via the new engine. | `freemocap` aggregator + posthoc; skellyforge managers | SH-1..4 |
| **SH-6 — Spec docs** | Update `01/11/12/13` + `IMPLEMENTATION_PLAN` to describe the standard human as built (model + engine = SSOT). | `docs/streaming-compatibility/` | continuous |

## Sequence

```
SH-1 (model) ─┬─▶ SH-2 (mappings) ─┐
              │                     ├─▶ SH-4 (solve) ─▶ SH-5 (wire)
SH-3 (engine) ┴─────────────────────┘
SH-6 (docs) — continuous
```

Recommended order: **SH-1 → SH-3 → SH-2 → SH-4 → SH-5**. SH-1 unblocks the streaming WS-3 adapter
immediately (the schema builds from the model even before rotations are live).

## Model shape (SH-1 concretely)

The standard human is **data**, validated once:

- **Bones** — VRM 1.0 set: torso `hips → spine → chest → upper_chest → neck`; head `head, left_eye,
  right_eye, jaw`; arms ×2 `shoulder → upper_arm → lower_arm → hand`; legs ×2 `upper_leg → lower_leg → foot
  → toes`; fingers ×2 (thumb `metacarpal/proximal/distal`; index/middle/ring/little
  `proximal/intermediate/distal`). Each bone carries: `name` (snake_case), `parent`, `required` bool,
  `reference_geometry` (T-pose joint centers + `CoordinateFrameDefinition`), and `twist_policy`.
  **No `vrm_alias` field** — aliases live in `human_bone_aliases.py`.
- **Landmarks** — the canonical joint-centers the bones connect (e.g. `hips_center`, `neck_center`,
  shoulder/elbow/wrist, SC/GH via `anatomical_offset`). This is the set SH-2 mappings must produce and
  the standard stream `POINTS` channels enumerate.
- **Reference geometry per bone** — T-pose local keypoint positions + a `CoordinateFrameDefinition` (exact
  axis = bone long axis; approximate axis = twist source per twist policy). Identity quaternion == T-pose.
- **Blendshapes** — the 52 ARKit channel names declared (VRM expression mapping noted for when face
  tracking is wired), values `null` for now.
- **Aliases** — `BONE_ALIASES` table in `human_bone_aliases.py`: `canonical_name → {target: alias}`.
  Initial targets: `vrm`, `unreal`. `resolve_alias(name, target)` helper; missing → canonical name + warning.

## Per-bone twist policy (declarative, not procedural)

Each bone declares its twist resolution tier and source:

```
Priority 1 — full_frame:    ≥3 non-collinear markers → Kabsch alignment (head, pelvis, thorax, hands, feet)
Priority 2 — chain_resolved: child/hinge direction supplies twist reference (upperArm←elbow, upperLeg←knee)
Priority 3 — damped_minimal: hold zero/rest twist, critically damped (fallback when source is occluded)
```

Bones declare which tier they're in and (for tier 2) which bone is the twist source. The engine reads the
policy and applies the corresponding math. **Singularity gate:** when parent and child bone are within ~5°
of parallel (arm straight), Priority 2 degrades to Priority 3 to avoid the cross-product blowup.

## Definition of done

- The standard human loads + validates: VRM 1.0 bones, hierarchy, alias table, T-pose reference geometry,
  52 blendshape channels declared.
- skellytracker mappings produce every canonical landmark the model needs (rtmpose + mediapipe).
- The engine (folded into SkellyForge) produces per-bone **wxyz quaternions** (identity == T-pose), both
  world and local, batch + realtime; `bs/`-parity unit tests on quaternion / reference-geometry math.
- The realtime aggregator fills BOTH `ROTATIONS_WORLD` and `ROTATIONS_LOCAL` channels live; the streaming
  golden tests still pass; posthoc `Human` rebuilt on the standard human (tracker model-infos retired).
- Face channels present + `null`. Docs `01/11/12/13` + plan updated. `bs/` **not imported** anywhere.

## Verify (per the cross-repo model)

skellyforge + skellytracker changes verify in **their own** envs; the **user commits** them; freemocap
`uv sync`s to pick them up, then the freemocap-side wiring (SH-5) + streaming golden tests verify end-to-end.
Never `import` from `bs/` (reference only).
