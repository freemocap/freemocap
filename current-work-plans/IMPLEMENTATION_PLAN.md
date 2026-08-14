# Implementation Plan & Progress

> **Historical (frozen 2026-08-14).** The scope table, phases, and dependencies below are **frozen at the
> docs reorg** — the live queue lives in [HANDOFF.md](HANDOFF.md) + the layer docs
> ([README.md](README.md)); this tracker gets a fresh rewrite after the F5 gate. The dated Progress log
> is **history**, not current instruction. The old spec set (`00–14`, `phase-1/`) is archived verbatim
> under [`archive/`](archive/).

## How to use this document

- The scope table + phases are **frozen** as of the reorg (2026-08-14); `[IN]`/`[LATER]`/`[FUTURE]` tags
  in the archived specs refer to this table's state at freeze time.
- Live scope + the queue: [HANDOFF.md](HANDOFF.md); live design per layer: [README.md](README.md).
- The Progress log below is history.

## Scope table (frozen at the 2026-08-14 reorg)

### `[IN]` — near-term build
- ✅ **Standard-human model** — DONE 2026-08-13: the composed 60-segment human (55 VRM 1.0 bones + 5 face-detail — body + hands + face
  bones), dict-backed `StandardHuman`, T-pose reference geometry, keypoint-declared solver, one length
  estimator. See [phase-1/09](archive/phase-1-work-plans/09-segment-model.md).
- **Kinematics engine fold-in**: copy/adapt `bs/kinematics_core` into **SkellyForge**; rewrite
  `AnatomicalStructure`/`ModelInfo`/managers onto the standard human; produce per-bone world+local
  quaternions (identity == T-pose). ([11](archive/streaming-compatibility-specs/11-kinematics-fold-in.md)).
- **Tracker→standard-human mapping**: every keypoint the model declares produced from tracker keypoints
  via the `*_to_standard_human_mapping.yaml` forms (string/list/dict/`anatomical_offset` — SC bilateral
  landed; `mid_sternum`/`head_vertex`/`foot_ball`/`jaw` are Phase B). The completeness contract
  (`required_keypoints()` = 76) is the interface ([13](archive/streaming-compatibility-specs/13-tracker-to-canonical-mapping.md), [09 Task 6](archive/phase-1-work-plans/09-segment-model.md)).
- **The LSL-shaped standard stream**: a schema (channels, joint hierarchy, T-pose, convention, units)
  sent once + timestamped samples per frame (with both `ROTATIONS_WORLD` + `ROTATIONS_LOCAL` channel
  groups), mirroring LSL's data model, over the existing WebSocket. Backend standard-stream encoder +
  frontend consumption.
- Canonical-frame extensions: **segment-rotation channels** (world + local, via the folded-in engine),
  **subject dimension**, **convention/rest-pose in the schema**, **per-point confidence / reprojection
  error**.
- **On-disk serialization**: migrate the **parquet** schema to tidy-long ([10](archive/streaming-compatibility-specs/10-serialization-and-tidy-format.md)).
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
- ✅ **Engine test suite** — DONE: `skellyforge/tests/` (94 green: composition convention, solver, damping,
  reference geometry, model, estimator) + `skellytracker/tests/` (222 passing non-video; the mapping
  completeness tests are Phase B). The differential-bend + round-trip cases landed before the D1 fix.

### `[LATER]`
- VRChat OSC adapter; Rokoko JSON adapter.
- **Align** the disabled kinematics code to the new engine/models; keep it out of hot loops until validated
  ([06](archive/streaming-compatibility-specs/06-backend-refactor-and-cleanup.md), [11](archive/streaming-compatibility-specs/11-kinematics-fold-in.md)).
- Scapula (scapulothoracic detail) via the `anatomical_offset` mechanism ([12](archive/streaming-compatibility-specs/12-standard-human-model.md)).
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
| ~~Forward-axis confirmation of FMC canonical convention~~ | — | **Resolved 2026-08-12 — `+X` forward.** Canonical convention is `mm · right-handed · +Z up · +X forward` (robotics/biomechanics standards): a **declared internal standard**, not derived from calibration output. Conversion happens at adapter edges on request; re-orientation is an explicit user action via the HTTP control plane. Code currently says `+Y` (defect D34). See [07](archive/streaming-compatibility-specs/07-coordinate-conventions.md#the-freemocap-canonical-convention). |
| ~~World-quaternion direction convention~~ | — | **Resolved 2026-08-12** — `q_world` maps segment-frame → world; `q_local = conj(q_parent) · q_child`. Stated in [07 § Segment rotation conventions](archive/streaming-compatibility-specs/07-coordinate-conventions.md#segment-rotation-conventions). Confirmed empirically by the round-trip test specified in doc 14 before the fix lands. |
| Multi-subject keying detail | Subject addressing on the frame | Multi-person tracking design |
| `app_state` / inbound "settings" audit | Status feed; one-way-WS decision; dead-path removal | Audit during the wedge |
| Rokoko plugin licensing/source acceptance | Rokoko adapter `[LATER]` | Read Rokoko's open-source plugins |
| ~~Landmark-vs-bone: what do `POINTS` / `OVERLAY_2D` enumerate?~~ | — | **Resolved 2026-08-13 by the reframe** — the landmark layer is retired entirely; the channel groups enumerate tracker **keypoints** (`KEYPOINTS_3D`) and **segments** (`SEGMENT_ORIGINS` + rotations), per [09-standard-stream-protocol § channels](archive/streaming-compatibility-specs/09-standard-stream-protocol.md#channels). FMC-WS-3 implements against it (Phase F). |
| ~~Where the canonical bone definition lives~~ | — | **Resolved 2026-08-13** — **pure Python, composed**: parts authored in `body_part.py`/`hand_part.py`/`face_part.py`, expanded by `compose_parts()`, validated by the frozen `StandardHuman` dataclass. No YAML model; the old aggregator bootstrap is deleted in Phase D (Task 9). |
| ~~Does `ROTATIONS_WORLD` have a committed consumer?~~ | — | **Resolved 2026-08-12** — yes, and it stays. The stream carries **everything** (small data); [FMC-RB](archive/phase-1-work-plans/06-rigid-body-bone-renderer.md) drives the viewport from it directly. |
| ~~Camera parameters for 2D landmark reprojection~~ | — | **Resolved 2026-08-12** — the **existing camera calibration infrastructure**. If we reconstruct 3D, we know the cameras by definition. See [FMC-SR §3](archive/phase-1-work-plans/07-spec-reconciliation.md#3-2d-overlays-carry-both-detections-and-reprojections-new). |
| ~~Testing home for the SkellyForge engine~~ | — | **Resolved 2026-08-12** — new sibling doc [14 — Engine Testing Strategy](archive/streaming-compatibility-specs/14-engine-testing-strategy.md). [08](archive/streaming-compatibility-specs/08-testing-strategy.md) keeps the wire; 14 owns the math. Suite added to `[IN]` scope. |

## Phased build order

### Phase 0 — Documentation `[in progress]`
This spec folder. Agree architecture, scope, and open questions before code.
- [x] Architecture decided; then **inverted** to standard-stream-first + LSL-shaped (schema + samples).
- [x] Spec docs `00`–`08` written and revised to the new architecture.
- [x] This implementation plan revised.
- [ ] Final review pass with the team.

### Phase 1 — The LSL-shaped standard stream (the foundation) `[planning]`
Detailed workstream plans live in [`phase-1/`](archive/phase-1-work-plans/README.md) (FMC-WS-1…FMC-WS-5; **positions-first**, rotations
via FMC-WS-5 parallel). Reshape FreeMoCap's own streaming into schema + timestamped samples; the UI is its first
consumer.
- [ ] Backend **standard-stream encoder**: schema once (channels, joint hierarchy, T-pose, convention,
      units) + timestamped sample per frame; fused with the `websocket_server.py` send-path reshape.
- [ ] Canonical frame carries subject dimension, convention (in schema), confidence/reprojection error.
- [ ] Segment-rotation channel defined in the schema; the folded-in `bs/` engine produces rotations live
      (copy/adapt into SkellyForge — [11](archive/streaming-compatibility-specs/11-kinematics-fold-in.md)). *(not blocked — we have the code)*
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

**Current phase: F — the realtime loop** ([`phase-1/11`](archive/phase-1-work-plans/11-realtime-loop-completion.md):
 six-group schema → encoder + WS reshape → TS decoder/wedge → rigid-body renderer → the manual
 full-loop run) — **Phase D (Task 9) is DONE** and awaits Commit Round 2; the posthoc rebuild
 (Phase E, [`phase-1/12`](archive/phase-1-work-plans/12-posthoc-rebuild.md)) is spec'd as revisit notes and executes
 AFTER the loop. *(previous text, superseded 2026-08-13: D — retire the old models)* —
Round 1 is pushed + synced (freemocap's env runs the new skellies); Task 9 Step 1 fixes the
now-broken freemocap call sites and deletes the bootstrap. Phase B is DONE (the completeness
contract is green, 226 skellytracker tests). *(previous text, superseded 2026-08-13: B — the keypoint
contract)* —
[`phase-1/10`](archive/phase-1-work-plans/10-whole-project-alignment.md) step order; detail in
[`phase-1/09` Task 6](archive/phase-1-work-plans/09-segment-model.md#task-6-the-required-keypoint-contract-per-tracker).
**Phase A is COMPLETE** (2026-08-13): Tasks 1–8 + the 4B+5+7 model-rewrite unit + the mapping rename,
skellyforge suite 94/94, skellytracker 222 passed (non-video). Phase B remaining: the completeness
contract test (parametrized over all four mappings against `required_keypoints()` = 76 — it will fail
RED on `mid_sternum`, `head_vertex`, `foot_ball` ×2, `jaw`), the load-time raise test, the five
`anatomical_offset` definitions in both body mappings (+ the `eye_width` named length), then **Commit
Round 1** (the user pushes skellyforge + skellytracker; freemocap's two mapping-path dicts + the
`SegmentLengthEstimator` import update on disk in the same pass).

Standing done: SF-SH-1/3/4/5, ST-SH-2, FMC-WS-1; canonical convention locked 2026-08-12
(`mm · right-handed · +Z up · +X forward`, quaternions `wxyz` — code still says `+Y`, defect D34);
freemocap test **collection** repaired this session (4 files repointed to
`skellyforge.kinematics.segment_lengths`; full-suite runtime failures deferred by the user).

## Progress log

- **2026-08-13 (face extension + the sanctioned lateral import — round done on disk, awaiting the
  push)** — Per the user: (1) the face part grew five **face-detail segments** — `nose`
  (head_center→nose, rest +X), `left_ear`/`right_ear` (head_center→ear, rest ±Y), `left_mouth`/
  `right_mouth` (corner→nose, rest from the SAME ratios as the mapping's derived-corner offsets) —
  all ORIGIN-attached to head, right sides authored side-agnostically (the geometry's blanket mirror
  derives them, like `left_eye`/`right_eye` — the spec review caught the double-mirror my first
  authored table would have caused). The model is **60 segments / 76 required keypoints**; aliases +5
  rows (`vrm: None, unreal: None`). skellyforge 104 green. (2) **The tracker→model contract moved from
  the golden fixture to a live load-time validator** ("real where available, estimate when possible"
  — MediaPipe mouth corners mapped 1:1; RTMPose corners derived via `anatomical_offset`, lateral
  ∓0.3·eye-width): skellytracker gained the import-light mapping-path registry (`core/io/
  mapping_paths.py`; detector methods delegate) and the mouth entries; the fixture + completeness test
  were DELETED; skellyforge gained `tracker_contract.py` (`validate_mapping_completeness` /
  `validate_all_tracker_families`, fail-loud, family-named errors) over the ONE sanctioned
  skellyforge→skellytracker import (base install, no detector extras — the leaky-abstraction rationale
  recorded at the import site, in `skellyforge/pyproject.toml`, and in both CLAUDE.md files).
  skellytracker 234 green. **NEXT: user pushes skellytracker + skellyforge → freemocap
  `uv lock --upgrade-package skellytracker skellyforge` + `uv sync` → F0b** (the wrapper edge-key fix
  + face-in-tree + 60/76 count updates).
- **2026-08-13 (F0 COMPLETE — the skull rigidifier + the rigid-points reshape, end to end)** — The
  reshape landed in skellyforge (pushed `fd9e73f`; 133 green): `SegmentDefinition` = explicit
  `rigid_points` + TAGGED axes (`AxisDefinition` x/y/z × EXACT/APPROXIMATE × from→to — no preset
  roles; first axis must be EXACT; EXACT axes ⊆ rigid_points, APPROXIMATE may be external like the
  upper arm's `wrist`), the shared `build_segment_frame` dispatch (1 exact → damped fallback; 2 →
  Gram-Schmidt; 2-exact-collinear → raise; 3 → the third declaration resolves only ẑ's sign; soft
  degradation for approximate collinearity), the head's 7-point skull set (incl. `head_vertex` —
  the model doesn't care tracked-vs-derived), and `kinematics/rigid_point_set.py` (bs-repo-derived
  MDS template, chirality-stabilized, per-frame rotation-only Procrustes — reflection-free via the
  existing Umeyama Kabsch; pyceres deliberately not ported). The freemocap wrapper then wired the
  graded dispatch (2 rigid points → the span path; 3+ → the fit): the skull pair estimator (21
  canonical pair keys, wall-clock window — the synthetic-counter bug the quality review caught was
  fixed), the 30-frame chirality-stable template rebuild policy, the fit anchored at the
  tree-corrected `head_center`, the rejected face pass deleted and replaced by the general
  orphan-anchor rule (every axis-referenced keypoint emits from observed — the foot/toes twist
  keypoints `heel`/`small_toe` restored), and the retired-name migration across freemocap.
  **F0 done: freemocap subset 62 green** (skull tests: 21 distances exact, noise→rigid,
  missing-point extrapolation, <3 passthrough, rebuild chirality). NEXT: F1 (the six-group schema).
- **2026-08-13 (the rigid-points ontology reshape — decided, first task dispatched)** — Per the
  user: no new kinds of rigid bodies; the SEGMENT grows the capacity. `SegmentDefinition` reshapes to
  an explicit `rigid_points` list + `origin_keypoint` + exact (`x_axis`) / approximate (`y_axis`)
  from→to axis pairs (bs-repo-style, Gram-Schmidt'd; the T-pose rest fields stay authored). The
  rigidifier grades by declaration: 2 rigid points → the span path (the degenerate Procrustes);
  3+ → the full rigid-body fit (median pairwise distances → MDS template → per-frame rotation-only
  Procrustes anchored at the tree-corrected origin — adapted from the bs repo's ferret skull solver,
  minus pyceres). The skull = the head's 7-point rigid set (incl. `head_vertex` — the model does not
  care whether a mapping derives a point or a tracker measures it). The jaw + mouth corners
  articulate and anchor at observed. The earlier face-pass fix (freemocap, rejected) is superseded.
  Nuance pinned: the EXACT axis's names must be in `rigid_points`; the APPROXIMATE axis is a
  direction reference and may be external (e.g. the upper arm's twist `wrist` is NOT rigid with the
  upper arm). Skellytracker: untouched this round. Order: skellyforge reshape (suite green
  throughout) → the fit module → push → freemocap wiring (dispatch + skull fit + delete the face
  pass).
- **2026-08-13 (sequencing set: realtime loop first, then posthoc; both planned)** — Per the user:
  the full realtime loop (reconstruct → stream over the LSL-compatible WS → 3JS rigid-body meshes)
  completes before the posthoc route is touched, because posthoc must converge on the contracts the
  loop proves (locked decision 8). New detail plans: [`phase-1/11`](archive/phase-1-work-plans/11-realtime-loop-completion.md)
  (the loop: six-group schema incl. D10/D22/D29/D30/D34/D35 → encoder + WS reshape incl. D36 →
  TS decoder/wedge → FMC-RB renderer incl. D5/D6/D14/D15 → the manual full-loop run as the gate) and
  [`phase-1/12`](archive/phase-1-work-plans/12-posthoc-rebuild.md) (the posthoc rebuild spec as REVISIT notes: the old
  layer's consumer map, the four decisions to make at the revisit, E1–E5 outline, the revisit
  checklist). Doc 10 reordered accordingly (F before E).
- **2026-08-13 (TASK 9 COMPLETE — Phase D done)** — Steps 2–4: deleted
  `skellyforge/biomechanics/` (verified byte-identical dead duplicate) + `pipelines/dlc_pipeline.py`
  (verified zero importers); re-expressed the realtime CoM on **de Leva (1996)** — default
  `DE_LEVA_MEAN`, per-sex tables available via `segment_inertial_parameters(sex)`, the 8→14 span mapping
  documented in code (head(+neck)→`neck_center→head_vertex`, trunk→`mid_sternum→hips_center`, foot→
  `ankle→foot_ball` with toes mass 0, unmapped VRM segments mass 0 inside mapped spans), **the
  mass-redistribution policy kept** with `directly_observed_mass` intact (the user's decision);
  repointed the WebSocket handshake at the composed model (`standard_human` schema: 72 keypoints, 54
  segment connections — the old `canonical_body`/`canonical_hand` AnatomicalStructure schemas + their
  silent try/except fallbacks deleted). Remaining old-model-layer consumers (the rigidifier's
  seed/`joint_hierarchy` dependency + the batch diagnostics + `models/`+`managers/`) die in Phase E, per
  the revised Step 4 (no interim YAML strip). Verified: freemocap 33 green (contract+schema+protocol+CoM),
  skellyforge 94, skellytracker 226; imports smoke OK. **NEXT: Commit Round 2 (the user) → Phase E**
  (the posthoc rebuild — write its own detail plan first, per the folder's rule).
- **2026-08-13 (Task 9 Step 1 done — the aggregator runs the composed model)** — The bootstrap is
  deleted (`_BONE_TO_LANDMARK`, `_get_standard_human`, `_build_solver_positions`, `_standard_human_cache`,
  the deleted-symbol imports) and the realtime aggregator now loads `compose_standard_human()` once per
  run, builds the reference geometry from nominal seeds (`length_ratio × 1700` — the solver needs only
  directions), merges body + standard-human-keyed hand positions, and calls the new
  `solve_frame_orientations` signature per frame. **The live `neck`/`head` crash class is structurally
  gone.** Round-1 leftovers fixed in the same pass: the six `canonical_mapping_path()` call sites, the
  rigidifier's three `SegmentLengthEstimator` adaptations (arrow-key labels preserved so the
  `TreeRigidifier` contract is untouched; `RigidifyResult` gained standard-human-keyed hand fields), and
  `stream_schema.py` + its 15 tests minimally adapted to the new model API (the six-group channel rework
  stays Phase F). Verified: imports smoke OK, 31 freemocap tests green, 94 skellyforge, 226
  skellytracker; end-to-end solve 46+46 quaternions; review approved with two trivial fixes applied.
  Next: Task 9 Steps 2–4 (delete `biomechanics/` + `dlc_pipeline.py`; CoM on segments via de Leva with
  the mass-redistribution decision; strip the canonical YAMLs + repoint render connections).
- **2026-08-13 (PHASE B CODE DONE — the completeness contract is green)** — `test_mapping_completeness.py`
  in skellytracker: the required 72-name set travels as a golden fixture (generated from the model;
  regeneration command in its header — skellytracker's tests can't import skellyforge), the family
  union covers both tracker families (rtmpose + mediapipe: body names + each hand name under BOTH side
  prefixes — the hand mapping is authored side-agnostically, mirroring the segment parts), and
  `TrackerMapping` gained `known_tracker_keypoints` — the D24 load-time raise (occlusion stays a silent
  per-frame skip). Went RED on exactly `mid_sternum`, `head_vertex`, `foot_ball` ×2, `jaw`, then green
  via five `anatomical_offset` definitions in BOTH body mappings (+ the `eye_width` named length):
  mid_sternum (SC basis, midline), head_vertex (Winter's 0.040 H as 0.17 × shoulder width),
  foot_ball (0.67 of ankle→big_toe; the shin as the approximate axis — the heel/toe-fan axes are
  degenerate for MediaPipe's foot_index), jaw (0.9 down / 0.2 posterior of eye width). Suites:
  skellytracker **226 passed** (non-video), skellyforge **94**. **NEXT: Commit Round 1 — the user**
  (push skellyforge + skellytracker; freemocap's two path dicts + `SegmentLengthEstimator` import
  update on disk in the same pass; uv lock/sync) → then Phase D.
- **2026-08-13 (tracker mappings renamed to the standard-human vocabulary)** — Per the user: the four
  `*_to_canonical_mapping.yaml` files are now `*_to_standard_human_mapping.yaml`; the four detector
  `canonical_mapping_path()` methods are `standard_human_mapping_path()`; `tracker_mapping.py`'s language
  swept ("canonical landmark" → "standard-human keypoint", `canonical_names` → `keypoint_names`
  property) with the D20 typing modernization applied; the YAML comment headers swept (MediaPipe's own
  `PoseLandmarker`/`HandLandmarker` product names stay — they're Google's API identifiers). Verified:
  zero canonical/landmark hits in the mapping layer, all four mappings load and `apply` works (SC
  bilateral produced with real input). **Deferred to the commit round:** freemocap's two mapping-path
  dicts (`skeleton_rigidifier.py:53`, `center_of_mass.py:62`) call the renamed method — they resolve
  against the installed skellytracker, so they update in the same round as the push. Uncommitted — user
  owns git.
- **2026-08-13 (SF-SM Task 8 done — PHASE A COMPLETE)** — The one length estimator, two windows:
  `SegmentLengthEstimator` (renamed from `RollingBoneLengths` — the bone vocabulary retired with it) in
  `skellyforge/kinematics/online_segment_lengths.py`: keyed by **segment name** with
  `segment_endpoints: {segment → (origin_kp, long_kp)}` + `segment_seeds` + `window_seconds: float | None`
  (None = unbounded posthoc; nothing evicted), endpoints/seeds validated to match, 11 tests incl. the
  unbounded-window-equals-batch-median proof (posthoc is not degraded). The freemocap duplicate AND its
  test are deleted (the estimator's one test home is skellyforge; nothing else imported the copy).
  freemocap's `skeleton_rigidifier.py` import updates at the commit round (Phase D) — the pinned
  skellyforge still exports the old name until then. **Phase A (Tasks 1–8) is complete: 94/94 skellyforge
  tests green.** Next per `phase-1/10`: the final review sweep over the whole Phase-A unit, then Phase B
  (Task 6 — the keypoint contract per tracker, where the derived keypoints incl. jaw land). All
  uncommitted — user owns git.
- **2026-08-13 (face bones driven — VRM 1.0 confirmed against the spec)** — Verified against the official
  `vrm-c/vrm-specification` (`VRMC_vrm-1.0/humanoid.md` + `expressions.md`): VRM 1.0 defines `leftEye`/
  `rightEye`/`jaw` as humanoid bones parented to `head` ("the model's eye movement controlled by bones")
  AND an 18-preset expression system (the 52 ARKit names are our face-tracking input vocabulary; the
  ARKit→VRM mapping stays in the adapter per locked decision 4). Per the user's decision, the three face
  bones are now **driven** segments: ORIGIN-attached to the head (head-center line), eyes rest +X, jaw
  rest ≈12.5° off +Z (derived from the Task 6 jaw-offset design: 0.9·eye-width down / 0.2 posterior of
  `nose`, `reference_length: eye_width` — added to Task 6's derived-keypoint list in both body
  mappings). The `undriven_segments` machinery is deleted; `required_keypoints()` = 76 over all 55
  segments; the shared `nose` keypoint is off-chain (not emitted in the rest-keypoint map — no
  authoritative rest position). Suite **83/83 green**. Uncommitted — user owns git.
- **2026-08-13 (SF-SM Tasks 4–7 done — the model-rewrite unit)** — The hand part (16 segments, fan
  angles from the addon's magnitudes + canonical signs, Buryanov & Kotiuk ratios), the face part (3
  declared-undriven segments + the 52 blendshape channels), the `StandardHuman` rewrite (composed frozen
  dataclass, dict-backed indices — D13's O(n²) is gone — 55 segments matching `BONE_ALIASES`, 69 driven
  required keypoints), `reference_geometry.py` (T-pose build: extrinsic-XYZ `rest_rotation`, right-side
  mirroring with frames rebuilt right-handed, twist-override table for rest-collinear/off-chain twist
  references, name-agreement ORIGIN attachment), and the solver rewrite (keypoint-declared two-tier
  twist, singularity gate, D3/D4 damping kept, `_get_distal_position`/`TwistPolicy`/`HumanBone` deleted —
  `human_bones.py` retired with its last importers). The unit's own bug found and fixed in-pass: the
  ORIGIN-attachment keypoint inconsistency (finger mcps vs. the hand's distal) broke identity-at-T-pose
  by 180° on the middle proximal phalanges — caught by the new `test_identity_at_t_pose` (doc 14 §4's
  contract) and fixed by the name-agreement rule. Suite **82/82 green**. Uncommitted — user owns git.
  Next: SF-SM Task 8 (the one length estimator) — Phase A's last task; then the review sweep and Task 6.
- **2026-08-12 (SF-SM Task 3 done — the body part)** — `skellyforge/.../standard_human/body_part.py`:
  `BODY_MIDLINE_PART` (6 segments) + `BODY_LIMB_PART` (7, authored left-side, instantiated ×2) +
  `compose_body_parts()` → the 20-segment body. Authoring decisions recorded in the plan (plan == code):
  `rest_rotation` derived from canonical T-pose geometry (single-axis Euler triples — the addon's
  `freemocap_tpose` eulers are bone-space, not portable, so it cross-checks only); `rest_roll` = 0 and
  `rotation_limits` = None until Task 5 pins the segment local-frame convention; `shoulder` 0.103 and
  `foot`/`toes` 0.026/0.013 are stated estimates. **Task 3's authoring exposed a Task 2 gap, fixed first:**
  unconditional prefixing broke midline references (`left_shoulder`→`left_upper_chest`), so
  `compose_parts` now resolves parents AND keypoints by name agreement (prefixed → unprefixed fallback,
  kept-as-authored otherwise). Review findings fixed in-pass: exact 20-entry parent map asserted in the
  test; twist-collinearity-at-rest recorded as design intent (the rest pose IS the degenerate case;
  Task 5's rest approximate axis uses the hinge direction, not the twist keypoint). Suite **76/76
  green**. Uncommitted — user owns git. Next: SF-SM Task 4 (hand/face parts + StandardHuman rewrite).
- **2026-08-12 (SF-SM Task 2 done — part composition)** — `skellyforge/skellymodels/standard_human/segment_parts.py`
  (`SegmentPart`, `instantiate_part`, `compose_parts` — parts authored once, instantiated per side via
  `dataclasses.replace` prefixing, duplicate-name detection) + `test_part_composition.py` (9 tests). TDD,
  two-stage review; the quality review's three unpinned seams (empty-prefix midline parts, root
  `parent=None` survival, fully-prefixed `required_keypoints()` — the seams Task 3's body part stands on)
  pinned in the same pass. Plan synced (plan == code). Suite **73/73 green**. Uncommitted — user owns git.
  Next: SF-SM Task 3 (the 13-segment body part).
- **2026-08-12 (SF-SM Task 1 done — `SegmentDefinition`)** — First code of Phase A, in skellyforge:
  `segment_definition.py` (frozen dataclass: origin/long-axis/twist keypoints + rest pose; fail-loud
  validators) + `test_segment_definition.py` (13 tests). TDD per the plan (failing first), two-stage
  subagent review, and the code review's NaN findings fixed in the same pass — `length_ratio` and
  `RotationLimits` bounds now reject non-finite values (NaN slipped both validators, which contradicted
  the fail-loud purpose), with 6 pinning tests added. Plan doc synced (plan == code). Suite **64/64
  green**. Uncommitted in skellyforge — the user owns git. Next: SF-SM Task 2 (part composition).
- **2026-08-12 (whole-project alignment re-derived; D7/D8 disposed)** — The paused D7/D8 work was built
  on the retired tracker→canonical framing and cannot be *finished*: disposition is keep-the-keypoint-half
  (bilateral SC mappings + D39), revert-the-graph-half (`canonical_body.yaml` reroot → HEAD). New
  [`phase-1/10`](archive/phase-1-work-plans/10-whole-project-alignment.md) re-derives the ordered whole-project path (A–G),
  surfaces the **posthoc rebuild as unowned-but-mandatory** (locked decision 8; SF-AL F4 open; `13` §
  Remaining work; blast radius incl. `pipelines/test_pipeline.py`), and records the mapping-YAML rename
  blast radius (4 detector paths + freemocap's 2 path-constant dicts). Also this session: freemocap test
  collection repaired (the kinematics-move commit left 4 test modules importing math names from the I/O
  wrapper; repointed to `skellyforge.kinematics.segment_lengths` — collection clean, 130 tests).
- **2026-08-12 (SF-SM aligned to keypoint → segment reference geometry)** — Per the user's notes on
  [`phase-1/09`](archive/phase-1-work-plans/09-segment-model.md): the "canonical keypoint" vocabulary is retired — segment
  definitions reference keypoints **directly by name** (origin / long-axis / twist), with no intermediate
  canonical-keypoint or landmark set. Absorbed: the `_BONE_TO_LANDMARK`/`proximal_landmark` bridges are
  framed as already-obviated artifacts (deleted, not ported); twist resolution is stated as two-tier
  (declared twist keypoint, else damped minimal roll — the proven D3/D4 fallback) with a best-practices
  research item added to §7; §3 rewritten; the mapping YAMLs are renamed
  `{tracker}_keypoint_mapping.yaml` (Task 6); Task 8's freemocap deletion is clarified as a working-tree
  change; Task 3 records the `freemocap_tpose` name translation and `None` ROM limits for segments the
  addon gives none. Documentation pass only — no code.
- **2026-08-12 (SF-AL architecture agreed)** — Worked the design through before writing code. Decisions
  recorded in [`phase-1/08`](archive/phase-1-work-plans/08-skellyforge-alignment.md#agreed-architecture): **compose what we
  author, generate the flat skeleton at load** (the 55-segment table is 15+15 duplicated fingers — the
  forbidden shape); **parts join by name agreement**, so a hand's local `wrist` becomes `left_wrist` under
  its prefix and unifies with the body's — no attachment mechanism, one joint hierarchy; **mirroring
  reflects rest positions and rebuilds frames right-handed**, never reflects a basis, because reflection
  has determinant −1 and a left-handed frame is still orthonormal so nothing else would catch it; **the
  face is a different kind of thing** — expressions, not segments, composed alongside the skeleton;
  **one human per `StandardHuman`**, multi-subject is a list; **the model layer knows nothing about
  trackers** (the `Aspect` array-slicing job is deleted); **composition replaces the Actor/Human/Animal/
  Board inheritance**. Two guard tests added to [14 §7](archive/streaming-compatibility-specs/14-engine-testing-strategy.md#7-standard-human-model).
- **2026-08-12 (SF-AL — SkellyForge is not aligned to the standard human)** — Surfaced while implementing
  D7/D8. The trigger was cosmetic (arrow-delimited dict keys in `canonical_body.yaml`); the survey found
  the arrow is a symptom. **`canonical_body.yaml` and its consumers predate the standard-human redesign
  and were never brought forward**, and the "all skeleton building in SkellyForge" consolidation is
  partially done. Measured: the same skeleton graph is encoded **three times** (`segment_connections` 25,
  `bone_length_ratios` 28, `joint_hierarchy` 26) with 20 edges stated twice, 16 three times, and 23 edges
  disagreeing across the three. `skellyforge/biomechanics/` is a **byte-identical unreachable duplicate**
  of `skellymodels/biomechanics/`. The old model layer (`models/` + `managers/`, ~1,500 lines) has **zero
  references** to `standard_human/` — two parallel human models. Six skeleton-building files remain in
  FreeMoCap, including a second CoM implementation. **Proof the redundancy already costs:** the clavicle
  reroot updated two of the three encodings and the model silently went inconsistent — nothing could have
  caught it. Plan: [`phase-1/08-skellyforge-alignment.md`](archive/phase-1-work-plans/08-skellyforge-alignment.md).
  **D7/D8 is paused mid-flight** and must be finished or reverted before the restructure.

- **2026-08-12 (aggregator wired — damping live end-to-end)** — `realtime_aggregator_node.py` now passes
  `timestamp_seconds=frame_time`, the monotonic per-frame clock it already threads to the rigidifier and
  CoM, so damping shares one time base with the rest of the pipeline. `_prev_orientation_result` deleted
  from module scope; the orientation history is a `_run`-scoped local, matching the existing idiom for
  per-run state (`prev_com`, `streaming_kinematics`) — **D16** closed. `_standard_human_cache` stays: it
  holds an immutable model, and D11 supersedes it. Verified end-to-end on the realtime bootstrap model —
  5 frames solved, 16 world + 16 local quaternions, **12 of 21 segments damped** (every segment that falls
  back to the minimal-twist tier). freemocap contract tests **23/23**, skellyforge **51/51**.
  **Next: D7/D8 sternoclavicular**, or the remaining FMC-SR doc items (§4 sequencing record, §8 stale sweep,
  §9 FMC-RB defects). *Uncommitted in freemocap.*
- **2026-08-12 (D3/D4 — real critical damping)** — `skellyforge/kinematics/critically_damped_orientation.py`
  implements the filter [12 § Critical damping](archive/streaming-compatibility-specs/12-standard-human-model.md) specifies: second-order,
  damping ratio 1, per-segment angular-velocity state, **solved analytically** rather than with the
  polynomial `exp` approximation game engines use. Runs in the tangent space (log/exp map) because SO(3)
  is not a vector space — `RotationQuaternion.from_rotation_vector` / `.to_rotation_vector` added, with
  shortest-arc resolution so the filter cannot smooth the long way round.
  `TwistPolicy.damping_factor` → **`twist_time_constant_seconds`**, so behaviour is framerate independent.
  Both `_solve_chain_resolved` fallbacks now damp (**D3**). Damping state moved onto `FrameOrientationResult`
  rather than module scope (**D16**, skellyforge side), and `solve_frame_orientations` now requires
  `timestamp_seconds` with **no default** — a default would let a caller silently disable damping (**D38**).
  Long gaps need no special case: the exponential decay lands them on target with zero velocity.
  **51/51 green**, including a framerate-independence test at 30/60/120/240 fps and residuals asserted
  against the closed-form envelope `(1 + t/tau)·exp(-t/tau)` rather than hand-picked thresholds.
  Also cleared **D18** (local import) and **D19** (dead `_check_strictly_increasing` import).
  **Next: wire the freemocap aggregator** — pass a real frame timestamp, hold `previous_result` on the
  pipeline instance instead of a module global (**D16**, freemocap side).
  *Uncommitted in skellyforge.*
- **2026-08-12 (D1 fixed — `ROTATIONS_LOCAL` is now correct)** — `orientation_solver.py` now composes
  parent-relative rotation as `conj(q_parent_world) * q_child_world`, per
  [07 § Segment rotation conventions](archive/streaming-compatibility-specs/07-coordinate-conventions.md#segment-rotation-conventions).
  **22/22 green** in skellyforge (was 18/22). The `FrameOrientationResult` docstring stated the reversed
  form and was corrected with it. Swept the engine for the same pattern: the only other `conj` composition
  is the angular-velocity finite difference in `quaternion_math.py` (`q_next * conj(q_curr)`), which is the
  **spatial** angular velocity of one body between frames — not a hierarchy composition — and is correct.
  This is the bug doc [07 § the local-rotation trap](archive/streaming-compatibility-specs/07-coordinate-conventions.md#the-local-rotation-trap-vmc-and-unreal)
  warned about; it is now closed before any VMC work begins.
  **Next: D3/D4 critical damping** ([12 § Critical damping](archive/streaming-compatibility-specs/12-standard-human-model.md), [14 §5](archive/streaming-compatibility-specs/14-engine-testing-strategy.md#5-critical-damping)).
  *Uncommitted in skellyforge.*
- **2026-08-12 (engine test suite stood up; D1 confirmed)** — First code of the FMC-SR follow-up.
  `skellyforge/tests/` now exists (it did not before — `pytest` collected nothing across ~3,200 lines of
  math) with pytest config in `pyproject.toml`. Two modules per
  [14 §2](archive/streaming-compatibility-specs/14-engine-testing-strategy.md#2-composition-convention--the-decisive-one):
  `test_quaternion_composition.py` pins the convention in isolation (Hamilton semantics,
  non-commutativity, differential bend, round-trip, 3-deep chain) — **12 green**;
  `test_orientation_solver_composition.py` runs a real skeleton through `solve_frame_orientations()` and
  asserts `recompose(parent_world, local) == child_world` — **4 failing**, confirming **D1** (parent-relative
  quaternion composed with reversed operands) empirically rather than by reading docstrings.
  **Also found — D37:** order-blindness has **three** independent causes, not the one known uniform-bend
  case. A segment at its *rest orientation* is identity and blind on either side of a pair; and parent/child
  rotated about the *same axis* commute, so distinct segment directions are not the invariant — distinct
  *rotation axes* are. Three successive fixtures each hit one hole and each passed roughly half their
  assertions for the wrong reason. Both new causes are now guard tests. **Next: fix D1** (one line, with a
  failing test in front of it), then D3/D4 critical damping.
  *Uncommitted in skellyforge — the user must commit before freemocap sees any of it.*
- **2026-08-12 (checkpoint audit)** — Plans read against the code landed on `development-streaming`;
  findings in [`AUDIT_2026-08-12.md`](archive/AUDIT_2026-08-12.md). Headline: the strategy holds and the
  **sequencing reversal was the right call**, but it was recorded only in
  [`phase-1/standard-human-model/README.md`](archive/phase-1-work-plans/standard-human-model/README.md) and never propagated —
  [`phase-1/README.md`](archive/phase-1-work-plans/README.md) still asserts "DECIDED: (A) positions-first (Option B rejected)"
  and FMC-WS-5 still reads "no code until agreed" with 0/6 checked for work that's done. **SF-SH-6 (spec
  updates, marked *continuous*) is the workstream that hasn't run, and it's the root cause of nearly every
  drift item.** Also found: FMC-WS-5 and the `standard-human-model` sub-plan are two live plans for the same
  work (SSOT violation); the **landmark-vs-bone** channel question is unresolved and will be baked in by
  FMC-WS-2; no plan owns testing for the SkellyForge engine; one real bug in committed SF-SH-4 math
  (parent-relative quaternion operand order) whose passing test is structurally unable to catch it. Five new
  entries added to [Dependencies & blockers](#dependencies--blockers). Verified along the way: contract +
  schema tests are **23 green** (not the 12 recorded in `HANDOFF.md`).
- **2026-08-11 (SF-SH-5 integration complete)** — Orientation solver wired into freemocap
  realtime pipeline. ``AggregationNodeOutputMessage`` extended with ``segment_rotations_world``
  + ``segment_rotations_local`` fields. Aggregator calls ``solve_frame_orientations()`` per frame
  after rigidification, bootstraps a ``StandardHuman`` model via ``_get_standard_human()``, maps
  rigidifier landmark names to bone names via ``_BONE_TO_LANDMARK`` bridge. Rotation data flows
  through the canonical frame — ready for the standard stream encoder (FMC-WS-2) to serialize
  into ``ROTATIONS_WORLD`` and ``ROTATIONS_LOCAL`` channel blocks. ``center_of_mass.py`` import
  path fixed (``utils.types`` → ``types``). Freemocap ``core/kinematics/`` folder fully removed;
  math moved to skellyforge, I/O wrappers moved to ``core/tasks/mocap/``.
  **Milestone: all SF-SH and ST-SH workstreams complete. Next: FMC-WS-3 adapter → FMC-WS-2 encoder → FMC-WS-4 UI wedge.**
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
  ([13](archive/streaming-compatibility-specs/13-tracker-to-canonical-mapping.md), [12](archive/streaming-compatibility-specs/12-standard-human-model.md)); **keep the parquet file**,
  migrate its schema to tidy-long ([10](archive/streaming-compatibility-specs/10-serialization-and-tidy-format.md)); **align, don't delete** the
  disabled `core/kinematics` (out of hot loops until validated — [06](archive/streaming-compatibility-specs/06-backend-refactor-and-cleanup.md));
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
  [12 — Standard Human Model](archive/streaming-compatibility-specs/12-standard-human-model.md). **Open:** face blendshapes; offset magnitudes;
  VRM bone subset for v1; scapula modeling.
- **2026-08-10 (investigation)** — Investigated the overlap between SkellyModels' `Human` actor,
  FreeMoCap `core/kinematics`, and `clients/bs/python_code/kinematics_core`. Findings: the canonical
  human *model* is already SkellyModels-SSOT; the biomechanics *math* is duplicated (batch vs realtime)
  with a few misaligned hardcoded segment lists; and **`bs/kinematics_core` is a mature per-segment
  rigid-body engine (quaternion orientation + angular kinematics + tidy serialization) that appears to be
  the "segment-rotation code that lives elsewhere."** Its on-disk serialization (reference-geometry JSON +
  tidy long CSV) is the disk twin of the standard stream's schema+samples, and a cleaner format than the
  SkellyForge parquet. Wrote [09](archive/streaming-compatibility-specs/09-standard-stream-protocol.md) (wire contract), [10](archive/streaming-compatibility-specs/10-serialization-and-tidy-format.md)
  (serialization), [11](archive/streaming-compatibility-specs/11-kinematics-fold-in.md) (kinematics fold-in). **Open:** confirm bs/ is the rotation
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
