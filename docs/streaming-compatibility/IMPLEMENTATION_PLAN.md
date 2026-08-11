# Implementation Plan & Progress

> **Living document.** This is the authoritative source for *scope* (what we're building and when)
> and *progress* (what's done). The spec docs (`00`–`08`) describe the target system; this file
> tracks the work to get there. Update the [Progress log](#progress-log) as work lands; move items
> between scope buckets deliberately, never silently.

## How to use this document

- The [Scope table](#scope-table-authoritative) is the single source of truth for
  `[IN]` / `[LATER]` / `[FUTURE]` tags used throughout the spec docs.
- Each phase has a checklist. Check items only when they're done and verified per
  [08 — Testing Strategy](08-testing-strategy.md).
- Unknowns are `TBD` with an explicit **trigger** — the event that unblocks them, listed in
  [Dependencies & blockers](#dependencies--blockers).

## Scope table (authoritative)

### `[IN]` — near-term build
- **Standard-human model** (SF-SH-1…SF-SH-6): VRM 1.0 bones + hierarchy + alias table + 52 ARKit blendshape
  declarations + per-bone reference geometry (T-pose + `CoordinateFrameDefinition`) — see
  [phase-1/standard-human-model/](phase-1/standard-human-model/README.md).
- **Kinematics engine fold-in**: copy/adapt `bs/kinematics_core` into **SkellyForge**; rewrite
  `AnatomicalStructure`/`ModelInfo`/managers onto the standard human; produce per-bone world+local
  quaternions (identity == T-pose). ([11](11-kinematics-fold-in.md)).
- **Tracker→canonical mapping**: every canonical landmark produced from tracker keypoints via the
  `*_to_canonical_mapping.yaml` forms; add the `anatomical_offset` mapping form for off-surface joint
  centers (clavicle SC/GH) ([13](13-tracker-to-canonical-mapping.md)).
- **The LSL-shaped standard stream**: a schema (channels, joint hierarchy, T-pose, convention, units)
  sent once + timestamped samples per frame (with both `ROTATIONS_WORLD` + `ROTATIONS_LOCAL` channel
  groups), mirroring LSL's data model, over the existing WebSocket. Backend standard-stream encoder +
  frontend consumption.
- Canonical-frame extensions: **segment-rotation channels** (world + local, via the folded-in engine),
  **subject dimension**, **convention/rest-pose in the schema**, **per-point confidence / reprojection
  error**.
- **On-disk serialization**: migrate the **parquet** schema to tidy-long ([10](10-serialization-and-tidy-format.md)).
- Streaming hub: frame tap, latest-frame mailbox, derived views, `StreamingManager`, supervision.
- `/streaming/*` HTTP control plane (list / start / streams / stop); scoped fail-loud; **start idle**;
  **ephemeral server-side** config.
- **LSL transport route** (near-free pass-through of the standard stream; `pylsl` is a **core** dep).
- **VMC protocol adapter** (derived from the standard stream; maps VRM 1.0→0.x names + expressions).
- Adapter registry (extracted after VMC).
- **UI:** streaming controls in the **Realtime UI** (dropdown of toggles + per-option modal); the
  `ServerContextProvider` **wedge** (message-routing + connection-lifecycle extraction) → full
  decomposition; **3D data → rolling-window time-series stores** (default ~100 frames, settable).
- **`websocket_server.py` breakup** (fused with the standard-stream reshape).
- **Audit `app_state` / inbound "settings"** end-to-end; flag dead paths for removal.

### `[LATER]`
- VRChat OSC adapter; Rokoko JSON adapter.
- **Align** the disabled kinematics code to the new engine/models; keep it out of hot loops until validated
  ([06](06-backend-refactor-and-cleanup.md), [11](11-kinematics-fold-in.md)).
- Scapula (scapulothoracic detail) via the `anatomical_offset` mechanism ([12](12-standard-human-model.md)).
- Face blendshapes driven from tracked face landmarks (null until wired).
- Dedicated high-frequency `streaming_status` WS message (if `app_state` cadence proves insufficient).
- One-way-WS decision + authoritative-reconnect fix for the stale-UI-after-crash issue.
- UI-side persistence of stream configs.

### `[FUTURE]` / out
- Xsens MVN, Qualisys RT, native Unreal Live Link route (Unreal reachable via VMC today).
- **Not doing:** NatNet, Vicon.
- Retirement of any **confirmed-dead** `app_state` / "settings" fields found during the wedge. (The disabled
  kinematics code is **aligned, not retired** — see `[LATER]`.)

## Dependencies & blockers

| Dependency | Blocks | Trigger that resolves it |
|---|---|---|
| *(Resolved — see progress log: kinematics engine → `bs/` copy-in; serialization → parquet tidy-long; standard-human → VRM rig; rest pose → canonical T-pose; incoming-code dependency gone.)* | — | — |
| Forward-axis confirmation of FMC canonical convention | Coordinate converter | Confirm against ground-plane calibration basis |
| Multi-subject keying detail | Subject addressing on the frame | Multi-person tracking design |
| `app_state` / inbound "settings" audit | Status feed; one-way-WS decision; dead-path removal | Audit during the wedge |
| Rokoko plugin licensing/source acceptance | Rokoko adapter `[LATER]` | Read Rokoko's open-source plugins |

## Phased build order

### Phase 0 — Documentation `[in progress]`
This spec folder. Agree architecture, scope, and open questions before code.
- [x] Architecture decided; then **inverted** to standard-stream-first + LSL-shaped (schema + samples).
- [x] Spec docs `00`–`08` written and revised to the new architecture.
- [x] This implementation plan revised.
- [ ] Final review pass with the team.

### Phase 1 — The LSL-shaped standard stream (the foundation) `[planning]`
Detailed workstream plans live in [`phase-1/`](phase-1/README.md) (FMC-WS-1…FMC-WS-5; **positions-first**, rotations
via FMC-WS-5 parallel). Reshape FreeMoCap's own streaming into schema + timestamped samples; the UI is its first
consumer.
- [ ] Backend **standard-stream encoder**: schema once (channels, joint hierarchy, T-pose, convention,
      units) + timestamped sample per frame; fused with the `websocket_server.py` send-path reshape.
- [ ] Canonical frame carries subject dimension, convention (in schema), confidence/reprojection error.
- [ ] Segment-rotation channel defined in the schema; the folded-in `bs/` engine produces rotations live
      (copy/adapt into SkellyForge — [11](11-kinematics-fold-in.md)). *(not blocked — we have the code)*
- [ ] UI wedge: extract message-routing + connection lifecycle from `ServerContextProvider` into a
      connection/transport service that consumes the standard stream (schema then samples).
- [ ] Tests: schema round-trip, standard-stream golden bytes, sample reconstruction.

### Phase 2 — Streaming hub + control plane + LSL route `[not started]`
- [ ] `StreamingManager` on `FreemocapApplication`; frame tap subscribes to `AggregationNodeOutputTopic`;
      latest-frame mailbox.
- [ ] `/streaming/*` router; scoped fail-loud; `stream_id` first-class; start-idle; ephemeral.
- [ ] LSL transport route (`pylsl` core dep) — near-mechanical pass-through of the standard stream.
- [ ] UI streaming controls in the Realtime UI (dropdown + modal); status via `app_state`.
- [ ] Tests: LSL pass-through via LabRecorder; mailbox drop-oldest/rate-decoupling; control-plane/failure.

### Phase 3 — VMC adapter + extract interface + finish refactors `[not started]`
- [ ] Coordinate converter + humanoid retarget derived views.
- [ ] VMC adapter ported from `freemocap_vmc/`; MTU-aware; per-socket error handling.
- [ ] Extract the adapter interface/registry (now that a transport route + a foreign adapter both exist).
- [ ] Complete the `ServerContextProvider` decomposition: **3D-data fan-out → rolling-window stores**,
      frame/canvas loop, remaining stores.
- [ ] Complete the `websocket_server.py` breakup.
- [ ] Tests: VMC golden bytes, loopback (+ cross-machine), converter vectors, one real third-party
      consumer (VSeeFace/VMC).

### Phase 4+ — Later adapters & future cleanup `[not started]`
- [ ] VRChat OSC; Rokoko JSON (pending licensing check).
- [ ] One-way-WS decision + stale-UI-after-crash reconcile.
- [ ] `[LATER]` align disabled kinematics to the new engine/models (out of hot loops until validated); retire
      only confirmed-dead `app_state`/settings fields.

## Todo (current focus)

1. ✅ **SF-SH-1 — Standard-human model** — DONE. `skellyforge/skellymodels/standard_human/`
2. ✅ **SF-SH-3 — Kinematics engine** — DONE. `skellyforge/kinematics/`
3. ✅ **SF-SH-4 — Orientation solver** — DONE. `skellyforge/kinematics/orientation_solver.py`
4. ✅ **ST-SH-2 — Tracker→canonical mappings + anatomical_offset** — DONE. `skellytracker/core/io/tracker_mapping.py`
5. **SF-SH-5 — Wire-up** (CURRENT): aggregator invokes solver, fills standard-stream rotation
   channels, rebuilds posthoc `Human` on standard model, retires legacy tracker model-infos.
6. **FMC-WS-3 — SkellyForge adapter**: wire `StandardHuman` model into schema builder.
7. Confirm the FMC canonical forward-axis and lock the convention value (goes in the schema).

## Progress log

- **2026-08-11 (ST-SH-2 implemented)** — Tracker-to-canonical mapping extended with
  ``anatomical_offset`` form in skellytracker. ``TrackerMapping`` now supports 4 forms: string
  (1:1), list (mean), dict (weighted sum), and dict with ``form: anatomical_offset`` for
  off-surface joint centers. ``_AnatomicalOffsetDef`` / ``_FrameAxisDef`` frozen dataclasses
  hold parsed definitions; ``_apply_anatomical_offset`` builds a right-handed anatomical frame
  from keypoint-defined axes (Gram-Schmidt + cross product), scales anthropometric offsets by a
  subject-derived reference length, and places the landmark. Two-pass ``apply()`` resolves basic
  mappings first, then anatomical_offsets (which may reference computed landmarks like
  ``hips_center``). ``sternoclavicular`` landmark added to RTMPose body mapping (anterior offset
  from shoulder midpoint via ``shoulder_width`` reference). End-to-end verified: SC joint placed
  ~49mm anterior, ~28mm inferior to shoulder midpoint — biologically correct.
  **Next: SF-SH-5 (wire-up — aggregator + canonical frame + retire legacy model-infos).**
- **2026-08-11 (SF-SH-4 implemented)** — Orientation solver built in `skellyforge/kinematics/`.
  ``orientation_solver.py`` ties SF-SH-1 (bone model) + SF-SH-3 (kinematics math) + live skeleton
  positions together. ``solve_frame_orientations()`` walks the bone hierarchy root-first, dispatches
  ``TwistPolicy`` per bone (full-frame / chain-resolved with singularity gate at ~5 deg /
  damped-minimal with temporal SLERP), produces both world + local quaternions in
  ``FrameOrientationResult`` — output maps directly to ``ROTATIONS_WORLD`` and ``ROTATIONS_LOCAL``
  standard-stream channel groups. ``solve_bone_world_orientation()`` for per-bone use;
  ``solve_bone_full_frame()`` for Kabsch alignment when >=3 markers per segment. Tested: T-pose
  identity, 90 deg bend (correct world quats + identity local for uniform bend), per-bone swing
  (Z->Y), singularity gate (chain-resolved degrades to damped-minimal when parallel).
  **Next: ST-SH-2 (tracker->canonical mappings + anatomical_offset) in skellytracker.**
- **2026-08-11 (SF-SH-3 implemented)** — Kinematics engine built in `skellyforge/kinematics/`.
  Three modules, zero Pydantic, all hot-path safe (dataclasses + numpy): `quaternion_math.py`
  (``Quaternion`` with ``__slots__`` + 12 vectorized numpy fns — single home for Hamilton product,
  SLERP, rotation matrix, Euler, angular velocity, composition, collapsing 3–5 duplicate copies from
  bs/); `coordinate_frame_ops.py` (``build_orthonormal_basis``, ``rotation_between_vectors`` for
  swing-only, ``align_point_sets_kabsch`` for full-frame bones, ``compute_rotation_from_live_basis``
  for twist resolution, ``compute_live_bone_basis``); `rigid_body_kinematics.py`
  (``RigidBodyKinematics`` dataclass with lazy ``cached_property`` for all derived kinematics +
  module-level ``compute_linear_velocity``/``compute_linear_acceleration``/
  ``compute_angular_acceleration``/``compute_keypoint_world_positions`` for hot-loop use).
  23 exported symbols. Smoke-tested: quaternion algebra, SLERP, angular velocity from identity,
  basis round-trip, Kabsch exact/noisy, circular motion kinematics. **Next: ST-SH-2**
  (tracker-to-canonical mappings) in skellytracker, then SF-SH-4 (orientation solver) in
  skellyforge.
- **2026-08-11 (SF-SH-1 implemented)** — Standard-human model built in
  `skellyforge/skellymodels/standard_human/`. Four modules, zero single-word names:
  `human_bones.py` (`HumanBone`, `BoneReferenceGeometry`, `CoordinateFrameDefinition`,
  `TwistPolicy` — dataclasses, identity-quaternion==T-pose contract, twist tiers: full_frame /
  chain_resolved / damped_minimal, singularity-gate-aware); `human_bone_aliases.py` (55-bone
  `BONE_ALIASES` table with `vrm` + `unreal` targets, `resolve_alias()` with safe-fallback
  for missing entries); `human_blendshapes.py` (52 ARKit `BlendShapeChannel` enum +
  `VRM_EXPRESSION_ARKIT_MAPPING` for the Phase-3 adapter); `standard_human_model.py`
  (`StandardHuman` Pydantic model with validators: duplicate-name rejection, single-root
  enforcement, bad-parent/cycle/twist-source detection, hierarchy + chain + children
  accessors, `from_bone_definitions()` factory, anthropometric ratio table). Validated:
  smoke-test green (construction, hierarchy, validators). `pydantic` added as skellyforge
  dependency. **Next: SF-SH-3 (kinematics engine fold-in) in parallel with ST-SH-2 (tracker→canonical
  mappings + anatomical_offset).**
- **2026-08-11 (standard-human decisions locked)** — Strategic review of the canonical human model
  against VRM/VMC/Unreal ecosystem realities. **Decisions locked (do not re-litigate):**
  - Bone set = VRM 1.0 humanoid (full body + hands + face); VMC adapter maps down to VRM 0.x names.
  - Naming = `snake_case` Python + separate alias table (`human_bone_aliases.py`), NOT bone attributes.
  - Bones subsume segments — full rewrite of `AnatomicalStructure`/`ModelInfo`/managers; no backwards compat.
  - Face = 52 ARKit blendshapes declared now, `null` until wired from skellytracker.
  - Rotation channels = **both** `ROTATIONS_WORLD` and `ROTATIONS_LOCAL` in the standard stream.
  - File naming = no single-word file names (`human_bones.py`, not `bones.py`).
  - Alias mechanism = external table (`canonical → {target: alias}`), one `resolve_alias()` helper.
  - Reference geometry per bone (T-pose + `CoordinateFrameDefinition`); twist policy declarative per bone.
  Updated `phase-1/HANDOFF.md` and `phase-1/standard-human-model/README.md`.
- **2026-08-11** — Consolidated the SkellyModels model layer onto first-class canonical landmarks:
  `AnatomicalStructure` / `AspectInfo` / `Trajectory` (skellyforge) now carry only tracked landmarks;
  computed landmarks (`head_center`/`neck_center`/`trunk_center`/`hips_center`) are produced solely by the
  skellytracker `*_to_canonical_mapping.yaml` (list-mean). Canonical body/hand models verified (27/21
  landmarks). Env `uv sync`'d (green baseline, 12 tests). Documented the **cross-repo dev model** (freemocap
  installs skellies from **git, not local** — local edits need a commit to reach freemocap): new
  `project/CLAUDE.md`, `docs/streaming-compatibility/HANDOFF_GUIDE.md`, restructured `phase-1/HANDOFF.md`.
  **Remaining:** the **posthoc** `Human` pipeline still builds from the legacy tracker model-infos
  (`rtmpose_model_info.yaml` / `mediapipe_model_info.yaml`) — route it through the mapping + canonical model
  and retire those files; plus the UI midpoint helper (`freemocap-ui`) and the legacy blender addon.
- **2026-08-10 (FMC-WS-3 builder)** — FMC-WS-3 schema builder coded: `standard_stream/stream_schema_builder.py`
  (`build_stream_schema` — pure, canonical data → `StreamSchema`; declares skeleton+derived POINTS,
  ROTATIONS, per-camera OVERLAY_2D; added `camera_ids` to the schema). `SCALARS` kind dropped — CoM/xcom are
  POINTS. **12 tests green** (8 contract + 4 builder). **Boundary hit:** the SkellyForge adapter (feed the
  canonical body/hand model) + aggregator wiring (`reprojection_error`/`subject_id`) need the **freemocap env**
  (skellyforge + pipeline), which isn't synced locally.
- **2026-08-10 (FMC-WS-1 coded)** — Phase 1 started. **FMC-WS-1 (standard-stream contract) implemented** in
  `freemocap/core/streaming/standard_stream/` (`conventions.py`; `schema.py` — msgspec StreamInfo + JSON codec;
  `sample.py` — binary encode/decode; `lsl_bridge.py`) + `tests/test_standard_stream_contract.py` — **8 tests
  green**. Pure contract + codecs, no wiring. (freemocap's uv env isn't synced locally; ran via the skellycam
  venv, since FMC-WS-1 only needs numpy/msgspec/beartype/skellylogs.) **Next:** FMC-WS-3 (canonical-frame extensions).
- **2026-08-10 (consistency-pass)** — Full start-to-finish pass reconciling evolved decisions from review
  notes. Reversals/locks: **don't defer** the derived-joint-center fix — added the **`anatomical_offset` mapping
  form** (deterministic, anthropometric, no runtime fit) that produces the anterior clavicle SC/GH centers
  ([13](13-tracker-to-canonical-mapping.md), [12](12-standard-human-model.md)); **keep the parquet file**,
  migrate its schema to tidy-long ([10](10-serialization-and-tidy-format.md)); **align, don't delete** the
  disabled `core/kinematics` (out of hot loops until validated — [06](06-backend-refactor-and-cleanup.md));
  **timestamp is the primary time key** (frame # secondary; image data is a separate stream linked by frame #);
  `stream_id` unique vs `stream_name` label; subjects are a **sample** dimension (not a schema field);
  quaternion order **`wxyz`**; keypoint(tracker)/landmark(canonical) terminology. The "incoming SkellyModels
  code" dependency is **resolved** — it's `bs/kinematics_core`.
- **2026-08-10 (standard-human)** — Confirmed: `bs/kinematics_core` **is** the rotation/kinematics engine
  (copy/adapt, **not** import — reference only); adopt the tidy-long serialization; **VMC/VRM humanoid as
  the standard human**, rigid-body-per-bone; SkellyForge owns the model+engine, FreeMoCap holds the realtime
  variant. Agreed the **twist policy** (full-frame → chain/hinge-resolved twist → damped minimal-twist
  fallback) and the **derived-joint-center** approach (the clavicle *should* root at an anterior SC joint, not the shoulder
  midpoint / C7-T1). *(Superseded by the consistency-pass above — the anterior fix is **not** deferred; it
  uses the `anatomical_offset` mapping form.)* Wrote
  [12 — Standard Human Model](12-standard-human-model.md). **Open:** face blendshapes; offset magnitudes;
  VRM bone subset for v1; scapula modeling.
- **2026-08-10 (investigation)** — Investigated the overlap between SkellyModels' `Human` actor,
  FreeMoCap `core/kinematics`, and `clients/bs/python_code/kinematics_core`. Findings: the canonical
  human *model* is already SkellyModels-SSOT; the biomechanics *math* is duplicated (batch vs realtime)
  with a few misaligned hardcoded segment lists; and **`bs/kinematics_core` is a mature per-segment
  rigid-body engine (quaternion orientation + angular kinematics + tidy serialization) that appears to be
  the "segment-rotation code that lives elsewhere."** Its on-disk serialization (reference-geometry JSON +
  tidy long CSV) is the disk twin of the standard stream's schema+samples, and a cleaner format than the
  SkellyForge parquet. Wrote [09](09-standard-stream-protocol.md) (wire contract), [10](10-serialization-and-tidy-format.md)
  (serialization), [11](11-kinematics-fold-in.md) (kinematics fold-in). **Open:** confirm bs/ is the rotation
  source; adopt tidy format?; resolve the standard-human shape.
- **2026-08-10 (revised)** — Architecture **inverted** after a review pass over the first draft. New
  keystone: reshape FreeMoCap's own streaming into an **LSL-shaped standard stream** (schema once +
  timestamped samples), make it the central representation, and derive everything from it — the LSL
  route becomes a near-free pass-through, foreign adapters (VMC) derive from the standard. Also locked:
  convention/static metadata live in the **schema** not per-sample; **positive definitions only** (no
  `discarded_fields`); **`pylsl` is a core dependency**; streaming controls integrate into the
  **Realtime UI** (dropdown + modal); 3D data moves into **rolling-window stores**; `start idle`;
  **ephemeral** server-side config; SkellyModels is a module **within** SkellyForge. Build order is now
  standard-stream → LSL route/hub → VMC → later adapters. All spec docs updated. **Next:** team review;
  await incoming SkellyModels quaternion code; audit `app_state`/settings during the wedge.
- **2026-08-10 (initial)** — Architecture established and documentation set drafted. Liveness of the
  realtime path audited: pub/sub canonical frame + rigidified skeleton positions are live; the
  centroidal-kinematics path is disabled and reference-only.
