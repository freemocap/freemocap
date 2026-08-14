# 11 — Realtime Loop Completion (the full loop)

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` (recommended)
> or `superpowers:executing-plans` to implement this task-by-task. Steps use checkbox (`- [ ]`) syntax.
>
> **Status: plan for agreement — no code until agreed.**
>
> **This is Phase F of [`10-whole-project-alignment.md`](10-whole-project-alignment.md), promoted to the
> current workstream 2026-08-13 (the user's decision: the realtime route completes BEFORE the posthoc
> rebuild).** Realizes the detailed FMC-WS-3 / FMC-WS-2 / FMC-WS-4 / FMC-RB workstream plans
> ([`02`](02-backend-encoder-and-ws-reshape.md), [`03`](03-canonical-frame-extensions.md),
> [`04`](04-ui-wedge.md), [`06`](06-rigid-body-bone-renderer.md)) against the segment model that now
> exists, plus the convention defects. The posthoc rebuild (Phase E) is planned separately in
> [`12-posthoc-rebuild.md`](12-posthoc-rebuild.md) and revisits the outcomes of this doc.

**Goal:** Close the realtime loop end-to-end: cameras → skellytracker → mapping → rigidifier →
orientation solver → **the standard stream over WebSocket** → **the TypeScript decoder** → **the
Three.js rigid-body segment renderer** — with every step proven by tests and one manual full-loop run.

**What already exists (Phase A/D):** the composed 60-segment model (55 VRM 1.0 bones + 5 face-detail), the reference geometry, the
keypoint-declared solver, the one length estimator, the completeness contract (both tracker families),
and a rewired aggregator whose frame carries `segment_rotations_world` / `segment_rotations_local` +
rigidified body/hand keypoints. The wire and the viewport are the old protocol still.

**Tech stack:** unchanged — Python (msgspec + numpy on the wire), TypeScript (React/Vite), Three.js.

---

## 1. The loop, as it stands

```
cameras → skellytracker detections → triangulation → mapping (renamed, contract-green)
       → rigidifier (re-keyed onto the segment model — F0, the user's call: the fix belongs HERE, not Phase E) → orientation solver (NEW ✅) 
       → AggregationNodeOutputMessage (rotations wired ✅)
       → websocket_server (OLD binary keypoints protocol ❌) → frontend (OLD decoders ❌)
       → Three.js viewport (OLD keypoint/connection renderers; no rigid-body meshes ❌)
```

The ❌ pieces are this doc's work, in dependency order: the rigidifier re-key (F0) → schema (F1) →
encoder + WS reshape (F2) → frontend decoder + wedge (F3) → the renderer (F4) → the full-loop
test (F5).

---

## 2. F0 — re-key the realtime rigidifier onto the segment model

**Why here and not Phase E (2026-08-13, the user's call):** the rigidifier is the loop's quality
layer — it must enforce lengths on the actual VRM segments, not on the old 26-edge landmark-pair
graph — and it is the last live consumer of the old `AnatomicalStructure` / `canonical_body.yaml`.
Re-keying it in the loop (a) closes the nominal-seeds gap (measured segment lengths feed the
reference geometry per frame), and (b) lets Phase E delete the old layer without touching the live
path. How it works today: the rigidifier's INPUTS/OUTPUTS are already standard-human keypoint names;
only its internal tree + length keys are the old arrow labels, and they are internally consistent —
that's why nothing broke. This pass ends the parallel-skeleton duplication.

**Two user corrections (2026-08-13, binding):**

1. **NO arrow-string keys, anywhere in this path.** The `"parent->child"` string convention (F2's
   original sin) is removed from the rigidifier entirely: the hierarchy (parent → children) IS the
   topology, and `TreeRigidifier`'s `bone_lengths` / carried directions are keyed by the **child
   node's name** (a tree has one parent per node — unambiguous, zero string parsing). Length is a
   property of a segment, not of a packed string.
2. **F0 splits at a commit round** (the cross-repo rule): **F0a** — skellyforge only: `TreeRigidifier`
   re-keyed (child-name keys + `return_directions=True` option), verified in skellyforge's own env →
   **the user commits + pushes skellyforge, then freemocap `uv lock --upgrade-package skellyforge` +
   `uv sync`** → **F0b** — freemocap only: the wrapper re-key + aggregator per-frame reference
   geometry + tests, against the pushed API. freemocap's env runs the pinned commit, never the local
   checkout — cross-repo work ends at the round.

- [x] **Step 1 (DONE 2026-08-13):** The freemocap wrapper (`skeleton_rigidifier.py`) builds its three
      `SegmentLengthEstimator`s from the **model**: seeds `{segment.name: segment.length_ratio ×
      height}`; endpoints `{segment.name: (segment.axes[0].from_keypoint, segment.axes[0].to_keypoint)}` —
      the arrow-key labels die. The `AnatomicalStructure` / `canonical_body.yaml` dependency in the
      live path dies with them.
- [x] **Step 2 (DONE 2026-08-13):** The `TreeRigidifier` (skellyforge `kinematics/skeleton_rigidifier.py`) consumes
      the **segment tree** (`segment_parents`) + segment-keyed lengths — read it, re-key its
      hierarchy input, keep its enforcement algorithm. The hand trees re-key onto the hand segment
      names the same way.
- [x] **Step 2b (DONE 2026-08-13 — the skull rigidifier — supersedes all earlier face handling, decided 2026-08-13):**
      no face pass-through, no carve-outs. The ontology is generalized instead: every segment
      declares its rigid point set EXPLICITLY (`rigid_points` + exact/approximate axis pairs — the
      reshape in the skellyforge round below), and the rigidifier grades by what is declared:
      **2 rigid points → the span/edge path (today's behavior); 3+ rigid points → the full
      rigid-body fit** (median pairwise distances → MDS template → per-frame rotation-only
      Procrustes anchored at the segment's tree-corrected origin). The two paths are one
      mathematical family — the 2-point span enforcement IS the degenerate Procrustes. The skull is
      the head segment's 7-point rigid set (`head_center`, `head_vertex`, `nose`, `left_eye`,
      `right_eye`, `left_ear`, `right_ear`); `head_vertex` is a legitimate rigid point (derived by
      today's mapping, possibly tracked directly by a future tracker — the model does not care).
      The jaw + mouth corners articulate (they are NOT rigid points) and anchor at observed. The
      52 blendshape channels stay declared-but-null and never touch the rigidifier.

**The skellyforge reshape round (before F0b's wrapper wiring):**

- [x] **R1 — the `SegmentDefinition` reshape (DONE 2026-08-13, pushed):** `rigid_points: tuple[str, ...]` (all keypoints
      rigid on the segment, ≥2, distinct) + `origin_keypoint` + TAGGED `axes: tuple[AxisDefinition,
      ...]` (1–3; `AxisDefinition` = axis ∈ {x,y,z} × kind ∈ {EXACT, APPROXIMATE} × from→to — the
      tags carry the roles, no preset x-exact/y-approximate; the first axis must be EXACT) + the
      T-pose rest fields unchanged. Load-time validation: origin ∈ `rigid_points`; EXACT axes'
      keypoints ∈ `rigid_points`; APPROXIMATE axes are direction references and may be external
      (the upper arm's `wrist`). All authored parts migrate mechanically: exact `(origin,
      long_axis)`, approximate `(origin, twist)` or none — today's semantics exactly (the modules
      compute twist as origin→twist; verified), no transitional vocabulary. The head gains its
      7-point skull set. Model/part tests stay green through the whole reshape.
- [x] **R2 — solver + reference geometry re-read (DONE 2026-08-13, on disk)** the same declarations through the new names
      (Gram-Schmidt exact/approximate basis — already `coordinate_frame_ops.build_orthonormal_basis`;
      the two-tier twist is unchanged). The rest pose stays the authored T-pose definitions.
- [x] **R3 — the multi-point rigid fit module (DONE 2026-08-13, on disk)** (adapted from the bs repo's ferret skull solver —
      `clients/bs/python_code/rigid_body_solver/`, minus the pyceres batch optimization): pairwise
      rolling-median distances (the existing `SegmentLengthEstimator`, pair-keyed) → classical MDS
      template (`reconstruct_from_distances`, sign-stabilized against the reference geometry) →
      per-frame rotation-only Procrustes (the existing `align_point_sets_kabsch`), anchored at the
      segment's tree-corrected origin. Template rebuilds when the medians change materially; per-frame
      subset alignment for occlusion (≥3 common points; fewer → observed anchors). Tests: all
      pairwise distances exact post-fit, rigid input → identity, subset fallbacks.
      *(The temporal-smoothing factors the bs solver used are unnecessary here — the Euro filter
      smooths keypoints upstream and the D3/D4 filter smooths orientations downstream.)*
- [x] **Step 3 (DONE 2026-08-13):** The aggregator passes the model to the rigidifier construction (it already has it
      per-run), and the rigidifier's per-frame measured lengths feed `build_reference_geometry`
      **per frame** (replacing the once-per-run nominal seeds from Task 9 Step 1 — lengths now live,
      the solver's reference directions are unchanged, the schema's rest pose follows).
- [x] **Step 4 (DONE 2026-08-13):** Tests — the rigidifier's enforced lengths equal the measured segment medians;
      rigidification preserves the tree's root and segment endpoints; the old-name grep across the
      freemocap live path is clean (`joint_hierarchy`, `bone_length_ratios`,
      `AnatomicalStructure` — zero hits in the realtime path). **F0 is COMPLETE**: the graded
      dispatch (2 rigid points → the span path; 3+ → the skull fit, 21 pairwise distances exact),
      the orphan-anchor rule covering every axis-referenced keypoint, and the wall-clock window fix
      all landed — 62 green in the freemocap subset.

## 3. F1 — `StreamSchema.from_standard_human()` against the six-group layout
## 2. F1 — `StreamSchema.from_standard_human()` against the six-group layout

Realizes [`03-canonical-frame-extensions.md`](03-canonical-frame-extensions.md) against
[`../09-standard-stream-protocol.md`](../09-standard-stream-protocol.md#channels) (the single authority
on channel content — where they disagree, 09 wins). The minimal adaptation from Phase D (old layout,
new model API) is superseded by this full pass.

- [ ] **Step 1:** Rewrite `ChannelKind` to one member per group — `KEYPOINTS_3D`, `SEGMENT_ORIGINS`,
      `ROTATIONS_LOCAL`, `ROTATIONS_WORLD`, `DERIVED_POINTS`, `OVERLAY_2D` — delete the legacy
      `ROTATIONS` member (D10); add `OverlayLayer` (`DETECTIONS` | `REPROJECTIONS`).
- [ ] **Step 2:** `from_standard_human` enumerates the six groups: keypoint names from
      `required_keypoints()` (76, sorted); segment names from `segment_names` (60); `segment_parents`
      added (D29's `SegmentNameString` alias lands here); `rest_pose` from
      `build_reference_geometry(...).keypoints` (already the Phase-D shape). **The schema↔model
      coupling (D30) is decided: intended** — `from_standard_human` IS the boundary; note it in the
      docstring and in [`01-standard-stream-contract.md`](01-standard-stream-contract.md).
- [ ] **Step 3:** Make `StreamSchema` frozen (D22 — the spec says frozen; make the code match).
- [ ] **Step 4:** Convention fixes in `coordinate_convention.py`: `forward_axis=Axis.PLUS_X` (D34 —
      the canonical standard is `mm · right-handed · +Z up · +X forward`); delete the `TODO(convention)`.
      Verify the camera-0-pinned calibration path meets the +Z/+X invariant (D35 — either it
      re-orients into canonical before data flows, or the gap is closed; the standard is not weakened).
- [ ] **Step 5:** Tests — `from_standard_human` yields the six groups with correct names/columns;
      both rotation kinds distinct; keypoints vs segments split; overlay layers; `segment_parents`
      agrees with the model; `RestPose` positions == reference keypoints; frozen schema rejects mutation.

## 4. F2 — the backend encoder + WebSocket send-path reshape

Realizes [`02-backend-encoder-and-ws-reshape.md`](02-backend-encoder-and-ws-reshape.md). The frame
source is the aggregator's output message (rotations already on it ✅); this pass serializes it.

- [ ] **Step 1:** `StreamSample.from_aggregator_output()` + `.to_bytes()` / `.from_bytes()` —
      blocks: `KEYPOINTS_3D` (tracker-named detections + reprojection error), `SEGMENT_ORIGINS`
      (per-segment transform origins — computed from the merged keypoints via each segment's
      `origin_keypoint`; NaN for missing), `ROTATIONS_LOCAL` / `ROTATIONS_WORLD` (wxyz, NaN for
      unsolved), `DERIVED_POINTS` (CoM + xcom from the de Leva rewrite), `OVERLAY_2D` (per camera ×
      layer — detections now; REPROJECTIONS wire the segment reprojection via the existing
      calibration, FMC-SR §3).
- [ ] **Step 2:** Decompose `websocket_server.py`'s send path: `SendSerializer` (the one-writer
      invariant), `BackpressureController` (windowed acks, pure policy), `FrameRelay`;
      `WebsocketServer` becomes the thin supervisor. Schema sent once on connect (+ on change).
- [ ] **Step 3:** **Delete the legacy path and the `FREEMOCAP_STANDARD_STREAM` flag in one change**
      (D36 — no coexistence; the first-byte tags already prevent collision, and the frontend decoder
      lands in the same cycle as F3).
- [ ] **Step 4:** Tests — backpressure SEND/WAIT/RESET; `from_aggregator_output` block kinds + wxyz
      values; sample round-trip; missing → NaN row; overlay blocks per camera; golden bytes for the
      schema and one sample (the F3 parity fixtures).

## 5. F3 — the frontend: transport service, decoder, rolling-window stores

Realizes [`04-ui-wedge.md`](04-ui-wedge.md) — with the legacy-compat items **deleted** (D36: there is
no legacy to coexist with; the decoder lands in the same cycle as F2).

- [ ] **Step 1:** `TransportService` + `RoutingTable` + `StandardStreamDecoder` +
      `SchemaRegistry` + `RollingWindowStore` (per [`04`](04-ui-wedge.md)'s file list and sketches);
      `ServerContextProvider` shrinks to a thin consumer.
- [ ] **Step 2:** Golden-byte parity: the Python schema/sample fixtures from F2 decode in TS to the
      same values (the cross-language contract test).
- [ ] **Step 3:** `subscribeToRotations` / `getRollingWindow` hooks land; the rolling windows are
      memory-bounded (~100 frames, settable).
- [ ] **Step 4:** Tests — schema round-trip, sample golden decode, rolling-window eviction,
      subscriber fire, overlay blocks per camera.

## 6. F4 — the rigid-body segment renderer (the meshes we built)

Realizes [`06-rigid-body-bone-renderer.md`](06-rigid-body-bone-renderer.md) with its four defects
fixed up front (FMC-SR §9): index segments by their schema-declared names, never by hierarchy edges
(D5); cross-section from a radius parameter, independent of long-axis length (D6); schema-time
name→index resolution (D14); `setColorAt` once at schema time (D15). Plus the honest note: **this
renderer cannot validate `ROTATIONS_LOCAL`** (it renders world quaternions; the local-rotation trap is
what the solver tests catch — cross-link to [`../14`](../14-engine-testing-strategy.md)).

- [ ] **Step 1:** `RigidBodyBoneGeometry` — the elliptical cone+sphere mesh (roll visibility).
- [ ] **Step 2:** `buildBoneInstances` from `StreamSchema.segment_names` + `joint_hierarchy`,
      fixed per D5/D6/D14/D15.
- [ ] **Step 3:** `RigidBodyBoneRenderer` — single `InstancedMesh`, scratch-reuse hot path, driven
      by `subscribeToSkeleton` (SEGMENT_ORIGINS) + `subscribeToRotations` (ROTATIONS_WORLD).
- [ ] **Step 4:** Visibility toggle `rigidBodyBones` (default on) + the overlay-layer toggles
      (FMC-SR §3); the existing keypoint/connection layers stay unchanged.

## 7. F5 — the full-loop test, then the manual run

- [ ] **Step 1:** The backend E2E slice that runs today (`test_e2e_pipeline` + the realtime pipeline
      test) extended to assert: aggregator output → `StreamSample.from_aggregator_output` → bytes →
      `StreamSample.from_bytes` → identical rotations/keypoints; a full realtime run (mock camera
      group, as the existing test drives it) producing a non-NaN `ROTATIONS_WORLD` block.
- [ ] **Step 2:** The frontend integration test: connect → schema → samples → `subscribeToRotations`
      fires → rolling window bounded → `RigidBodyBoneRenderer` instances placed (jsdom/three test).
- [ ] **Step 3:** **The manual full-loop run (the user, real cameras):** the realtime pipeline live,
      the 3JS viewport drawing the rigid-body segments from the solver's world quaternions. The
      checklist: identity pose at capture start looks like the T-pose; bending an arm rotates the
      humerus mesh without pop; a hidden hand degrades gracefully; the WS frames decode without
      schema drift. **This run is the gate before Phase E opens.**

## 8. F6 — realtime-loop leftovers (note, do not do now)

- `streaming_status` in `app_state` (audit when the wedge lands — `05-ui-integration-and-refactor.md`
  has the known-concern note); `body_kinematics` stays dropped (live-substrate-only);
  `nominal_srate` for the future LSL route (measure jitter when the loop runs); the
  `websocket_server` inbound-settings question (05's known issue — resolve during the wedge).
- Anything F shakes out about the model/solver/stream becomes **input notes for doc 12's revisit**.

---

## Definition of done (the realtime loop)

- The six-group schema derives from the composed model; the convention says `+X` forward; the legacy
  wire path and its flag are deleted.
- The aggregator's frame reaches the frontend as schema+samples; the TS decoder is golden-byte
  parity with the Python encoder.
- The 3JS viewport draws the 60 rigid-body segments from the solver's world quaternions
  (identity == T-pose), with the overlay layers available.
- The manual full-loop run passed (F5 step 3).
- Suites: freemocap (the green subset + the new F tests), skellyforge 133, skellytracker 234.
