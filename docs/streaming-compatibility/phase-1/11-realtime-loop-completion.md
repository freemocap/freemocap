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

**What already exists (Phase A/D):** the composed 55-segment model, the reference geometry, the
keypoint-declared solver, the one length estimator, the completeness contract (both tracker families),
and a rewired aggregator whose frame carries `segment_rotations_world` / `segment_rotations_local` +
rigidified body/hand keypoints. The wire and the viewport are the old protocol still.

**Tech stack:** unchanged — Python (msgspec + numpy on the wire), TypeScript (React/Vite), Three.js.

---

## 1. The loop, as it stands

```
cameras → skellytracker detections → triangulation → mapping (renamed, contract-green)
       → rigidifier (old tree still — Phase E re-keys it) → orientation solver (NEW ✅)
       → AggregationNodeOutputMessage (rotations wired ✅)
       → websocket_server (OLD binary keypoints protocol ❌) → frontend (OLD decoders ❌)
       → Three.js viewport (OLD keypoint/connection renderers; no rigid-body meshes ❌)
```

The three ❌ are this doc's work, in dependency order: schema (F1) → encoder + WS reshape (F2) →
frontend decoder + wedge (F3) → the renderer (F4) → the full-loop test (F5).

---

## 2. F1 — `StreamSchema.from_standard_human()` against the six-group layout

Realizes [`03-canonical-frame-extensions.md`](03-canonical-frame-extensions.md) against
[`../09-standard-stream-protocol.md`](../09-standard-stream-protocol.md#channels) (the single authority
on channel content — where they disagree, 09 wins). The minimal adaptation from Phase D (old layout,
new model API) is superseded by this full pass.

- [ ] **Step 1:** Rewrite `ChannelKind` to one member per group — `KEYPOINTS_3D`, `SEGMENT_ORIGINS`,
      `ROTATIONS_LOCAL`, `ROTATIONS_WORLD`, `DERIVED_POINTS`, `OVERLAY_2D` — delete the legacy
      `ROTATIONS` member (D10); add `OverlayLayer` (`DETECTIONS` | `REPROJECTIONS`).
- [ ] **Step 2:** `from_standard_human` enumerates the six groups: keypoint names from
      `required_keypoints()` (72, sorted); segment names from `segment_names` (55); `segment_parents`
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

## 3. F2 — the backend encoder + WebSocket send-path reshape

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

## 4. F3 — the frontend: transport service, decoder, rolling-window stores

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

## 5. F4 — the rigid-body segment renderer (the meshes we built)

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

## 6. F5 — the full-loop test, then the manual run

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

## 7. F6 — realtime-loop leftovers (note, do not do now)

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
- The 3JS viewport draws the 55 rigid-body segments from the solver's world quaternions
  (identity == T-pose), with the overlay layers available.
- The manual full-loop run passed (F5 step 3).
- Suites: freemocap (the green subset + the new F tests), skellyforge 94, skellytracker 226.
