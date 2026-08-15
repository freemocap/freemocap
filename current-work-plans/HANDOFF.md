# Handoff — 2026-08-15 (evening): stream unified + LIVE; 3D bones render but mis-oriented ~90°

**For a fresh agent (or the same one after compaction).** This file is the entry point and the live
state. Follow the orientation protocol, then **confirm your understanding with the user in chat before
touching anything**. Do not start on assumptions — the user has repeatedly (and correctly) rejected agents
who read stale docs, patched symptoms instead of structures, or fixated on the wrong layer.

## The orientation protocol (read in this order)

1. **This file** — the whole thing. It is the live state.
2. **[`ontology.md`](ontology.md)** — keypoint → mapping → landmark → segment → skeleton. Now-DoD: a
   **VMC-compatible realtime segment stream** to the frontend. The constraint/solve layer (linkages,
   chains/IK) is **future — seams only**.
3. **[`00-foundation/conventions.md`](00-foundation/conventions.md)** + [`glossary.md`](00-foundation/glossary.md) —
   mm · right-handed · +Z up · +X forward; quaternions **wxyz**; **identity == T-pose**;
   `q_local = conj(q_parent)·q_child`; 60 segments / 76 landmarks.
4. **[`01-data-model/stream-contract.md`](01-data-model/stream-contract.md)** — THE wire contract: the
   producer model, the channel table (kinds 0–9; `SEGMENT_LENGTHS=7`, `IMAGE_JPEG=8` uint8,
   `OVERLAY_REPROJECTIONS=9`), the schema-signature lifecycle, dtypes (FLOAT32=0, UINT8=1).
5. **[`03-transport/backend-encoder-ws.md`](03-transport/backend-encoder-ws.md)** +
   [`standard-stream-protocol.md`](03-transport/standard-stream-protocol.md) — one relay, one consumer,
   newest-wins, no ack window, images in the sample.
6. **[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)'s progress log** — history only. Where docs and
   code disagree, **the code wins and the doc is a bug** (fix the doc).
7. The code, for THIS task, in order: `01-data-model/segment-model.md` + skellyforge's orientation solver
   + rest-geometry builder + `SegmentDefinition` (establish the ACTUAL rotation convention) →
   `freemocap/core/streaming/standard_stream/producers/segment_producer.py` (what `segment_axes` /
   rotations it emits) → `freemocap-ui/src/components/viewport3d/renderers/RigidBodyBoneInstances.ts`
   (`computeBoneMatrix` / `buildBoneInstances`) + `RigidBodyBoneRenderer.tsx`.

`archive/` is history, never guidance. Multi-repo clone: `project/freemocap/` holds `freemocap/` +
`freemocap-ui/`; `skellyforge`/`skellytracker` are siblings; freemocap installs the skellies **from git**
(local skelly edits are invisible until the user commits/pushes + `uv sync`). **The user owns ALL git —
never commit, push, or suggest it.**

## THE load-bearing principle — the schema producer↔consumer contract

This is an LSL-style stream: **the schema producer may emit ANY valid schema variation** (image-only in
camera-only mode; image + full reconstruction when a pipeline is live; any future producer set), and
**EVERY consumer MUST gracefully handle whatever schema it receives** — including a schema that omits a
channel group the consumer cares about. A consumer that assumes a group is always present (and breaks when
it is absent) is **the bug**; a producer emitting a valid partial schema is **not**. This is a
**system-wide contract**, never a per-consumer patch — treat any violation as a whole-system correctness
issue.
- **First instance found + fixed:** the 3D bone renderer's `buildBoneInstances` **threw** on the
  image-only schema ("no SEGMENT_ORIGINS channel group"); because that throw hit the renderer's
  *synchronous* schema-`useEffect` before `subscribeToSchema` was wired, it aborted the subscription → the
  later full schema never rebuilt the table → **0 bones**. Fixed: `buildBoneInstances` now returns an
  **empty table** (draws nothing) on an image-only schema instead of throwing.
- **NEXT-AGENT ACTION:** audit **every** consumer for the same assumption (`SchemaRegistry.resolve`, the
  2D overlay path, rolling-window stores, all viewport renderers). Make them tolerate any schema; consider
  a single shared "resolve-group-or-skip" helper so the contract lives in one place.

## Where we are right now (2026-08-15 evening)

The unified streaming layer is **landed and running end-to-end** (all uncommitted on disk). One
producer-composed stream, one consumer of the aggregator output, newest-wins, images + overlays + pose in
one sample, per-frame `SEGMENT_LENGTHS`, schema re-sent only on a composite-signature change. The 2D
overlays (detections + reprojections + stats HUD) and the 3D keypoints/landmarks render correctly, in
lockstep with the video. Calibration is valid (the `d441` vs TOML mismatch is gone).

**The live problem: the 3D rigid-body bones now render but are ~90° mis-oriented for most segments**
(some — arms? — look right-ish). This is the segment-rotation / rest-frame convention. Fixing it is the
current task (see below). Getting the 3D bones to line up with the (good-looking) 2D reprojections is the
point.

## Runtime invariants (hard-won — do not break)

1. **No restarts in the workflow.** The server stays up across config changes. Calibration hot-reloads
   (aggregator polls the TOML every 1 s). Config changes rebuild+resend the schema via the pubsub network
   (`PipelineConfigUpdateTopic`, skellycam `UPDATE_CAMERA_SETTINGS`/`EXTRACTED_CONFIG`); the composite
   signature (incl. `camera_image_sizes` — a rotation swaps w/h) is the backstop. Any data-model change
   rides this, never a restart.
2. **The stream is lockstep by construction.** Image, overlays, and pose for frame N travel in ONE sample.
   Never reintroduce a second send path, a second consumer of `aggregation_output_subscription`, or a
   cross-stream timing heuristic (that was the original blink bug).
3. **Expected cases are not log spam.** 2D-only mode (no calibration), image-only schemas, etc. are normal
   — quiet (`debug`), no tracebacks.
4. **The schema contract above** — every consumer tolerates every schema.

## THE LIVE TASK — 3D bone orientation (~90° wrong): a careful math audit (NOT a mad dash)

The user's chosen approach (settled — do not re-litigate): **"world quaternion, rest-derived axis."** Keep
orienting via the streamed `ROTATIONS_WORLD` (the VMC product — the sophisticated path, positions +
quaternions), but derive each segment's geometry→local-frame mapping from the **rest pose**, NOT the
hardcoded `exact_axis` long-axis label.

- **The suspect + the crux.** `computeBoneMatrix` builds `world = R · Q · S`, where `Q` maps the geometry's
  +Z onto the segment's `exact_axis` (schema `segment_axes`: body/hand=`y`, face=`z`). The contradiction to
  resolve: "identity == T-pose" + "`R_world` maps local→world" implies at T-pose a body segment's long
  axis points **world +Y**, yet the spine points **world +Z (up)** at T-pose. So either the model's local
  frames aren't what `exact_axis` claims, or the world-quaternion convention differs. (`computeBoneMatrix`
  correctly composes `R·Q·S`; its comment saying `R·S·Q` is wrong — ignore it.)
- **User steer (why the long-axis label is stale):** the segment is mathematically **axis-agnostic**; VRM
  enters ONLY at the rest pose. So `segment_axes` / `byNameLongAxis` / `Q` must be replaced by a
  rest-derived orientation — likely a per-segment **rest long-axis direction** (3-vector) or full rest
  local frame exposed on the schema (computed from origin_landmark→distal_landmark at rest), which the
  renderer orients geometry +Z onto before applying `ROTATIONS_WORLD`. We MAY edit skellyforge/freemocap.
- **Method.** The reprojected 2D overlays "look pretty good" → origins/fit are likely right, so the
  **rotations / rest-frame convention** are the suspects. **Read skellyforge's solver + rest-geometry +
  segment definition FIRST** and establish the actual convention before changing the renderer. The skull
  (3+ landmark Procrustes fit) was separately flagged "not quite right."

## Bone-viz state (freemocap-ui/.../viewport3d/, uncommitted)

- **Geometry (`RigidBodyBoneGeometry.ts`) — FIXED.** Was a malformed double-ended spike (it remapped a
  Y-cylinder's *radial* Z). Now a clean tapered cone along +Z spanning [0,1] from the joint (wide base at
  the origin) to the distal tip, X-squished for roll. **No joint sphere** — under the non-uniform
  per-instance scale (Z=length ≫ X/Y=cross-section) a merged sphere stretches into a length-long spindle;
  the keypoint/landmark dots already mark joints. A real joint sphere needs a SEPARATE uniformly-scaled
  instanced mesh (follow-up).
- **Material (`RigidBodyBoneRenderer.tsx`) — unlit `MeshBasicMaterial`, side colors dimmed ×0.7.** Was
  full-bright white → bloomed (threshold 0.9). `MeshStandard` (lit) risks black bones because the scene
  lights are gated behind `visibility.environment`; reverted to unlit-dimmed. Proper shading needs an
  ungated ambient light in `ThreeJsScene` (follow-up).
- **LEFTOVER DIAGNOSTIC CODE TO REMOVE (`RigidBodyBoneRenderer.tsx`):** the `_diagFrameRef` ref; the
  frame-90 `[BONE-DIAG]` gate log in `useFrame`; the try/catch + `[BONE-DIAG]` logs in `rebuild`. Once the
  `buildBoneInstances` empty-table fix is confirmed live, revert `rebuild` to the clean 3-line version AND
  reorder the schema `useEffect` to call `subscribeToSchema(rebuild)` BEFORE `rebuild(existing)` (defensive
  — no future throw can abort the subscription).

## Where the work stands per repo

| Repo | State | Suite |
|---|---|---|
| skellyforge | committed+pushed through 2026-08-14; on-disk rounds since (tracker-contract/`rest_roll`/`observation` freeze; **rigid-child** eyes/ears/nose; possible solver changes) still uncommitted | 148→153 green range |
| skellytracker | mapping-language sweep + `rtmpose_body.yaml` foot-names fix (pushed `4a7b390`) | 234 green |
| freemocap (+ freemocap-ui, same clone) | committed+pushed through 2026-08-14; **on disk since, uncommitted: the whole unified-stream cutover + 2D overlay upgrade + the 3D bone geometry/material/empty-table fixes + diagnostics** | backend subset **133 green**; `tsc` clean; TS harnesses green (decoder 6 / integration 3 / rigid-body 6) |

## The queue (in order)

1. **Fix the 3D bone orientation** — the math audit above. Replace the stale `segment_axes`/long-axis `Q`
   with a rest-derived orientation; get the 3D bones to line up with the 2D reprojections. Then clean the
   leftover diagnostics. **This is the live task.**
2. **Audit all consumers for the schema contract** (the principle above) — not just the bone renderer.
3. **[USER] the commit round** — everything on disk (skellyforge rounds; freemocap unified-stream +
   overlay + bone fixes). Report the stopping point; never touch git.
4. **F5 gate** — the manual full-loop checklist: T-pose at capture start, arm bend rotates the humerus
   mesh without pop, hidden-hand degradation, no schema drift, dots + landmark lines + bones in lockstep
   with the video (no blinking, no spikes, correct orientation).
5. **F5+1 — the VMC adapter** (VRM 1.0→0.x name map). Then **the posthoc rebuild**
   ([`02-pipeline/posthoc-rebuild.md`](02-pipeline/posthoc-rebuild.md)).

## Known gaps (flagged, deliberately not done)

- **The `segment_axes` long-axis mechanism is stale/wrong** (the ~90° cause) — being replaced by
  rest-derived orientation (queue #1). Do NOT treat the existing "segment_axes + long-axis orientation" as
  correct; it is the thing under repair.
- **Dead `tracker_schemas` handshake** on the frontend (provider handler → `canvasManager.setSchema` →
  worker → `OverlayManager.setTrackerSchemas`) — nothing sends it; the renderer uses the schema's
  `connections` now. Delete the whole chain.
- **Dead charuco renderer files** (`charuco-overlay-renderer.ts`, `charuco-types.ts`, the OverlayManager
  charuco half) — no producer feeds them.
- **`IMAGE_JPEG` is one opaque multi-camera blob** — per-camera blocks are the documented future shape
  (needs SkellyCam payload unpacking backend-side).
- **The 3D renderer reads schema-default `segment_lengths`** — live per-frame `SEGMENT_LENGTHS` is exposed
  via `TransportService.getLatestSegmentLengths()` but the renderer doesn't merge it yet.
- **Bone joint sphere + lit shading** — deferred (see bone-viz state).
- **Playback HTTP image path** is outside the unified stream — untouched, revisit in the posthoc rebuild.

## Locked decisions (do not re-litigate)

- **The schema producer↔consumer contract** (the principle above) — system-wide.
- One producer-composed stream, schema as the single source of truth, newest-wins, no ack window, images
  in the sample. The two-stream model was a defect, not an option.
- 3D bones: **world-quaternion orientation, rest-derived axis** (not the hardcoded long-axis label). The
  segment is math-agnostic about long↔x/y/z; VRM enters only at the rest pose.
- Overlay split: keypoints = small dots (no connections); segment-origin landmarks = larger dots +
  `connections`.
- Landmark REVIVED (two-faced meaning); `long_axis`/`twist_keypoint`/`from-to_keypoint`/"canonical"
  (mapping sense) retired. Code describes the system AS IT IS.
- VRM local conventions (+Y toward child, +Z gaze) live in the rest pose; observed/unobserved-DOF flag is
  dropped (graded landmark count is the seam). Rest-pose/model side never imports skellytracker at runtime.
- Rigid-child: eyes/ears/nose are rigid children of the head (inherit its world rotation); jaw + mouth
  corners stay articulated. (skellyforge, awaiting the commit round.)
- **Working rules:** never touch git (user owns it); plan==code (docs edited in the same pass); fail
  loudly; no duplicated info; no backwards compat; check in before changes; keep answers short; **no
  restarts as a workflow requirement**; expected cases log quietly.

## Env

- freemocap backend subset (green): `uv run --group dev pytest freemocap/tests/rigid_body/
  freemocap/tests/test_standard_stream_contract.py freemocap/tests/test_stream_schema_builder.py
  freemocap/tests/test_center_of_mass.py freemocap/tests/test_stream_sample_encoder.py
  freemocap/tests/test_send_serializer.py freemocap/tests/test_frame_relay.py
  freemocap/tests/test_full_loop.py freemocap/tests/kinematics/ -q` → 133 passed.
- TS: `cd freemocap/freemocap-ui && npx tsc --noEmit` (clean) + three esbuild+node harnesses (NO Vitest):
  `transport/__tests__/standard-stream-decoder.test.ts`,
  `viewport3d/renderers/__tests__/standard-stream-integration.test.ts`,
  `viewport3d/renderers/__tests__/rigid-body-bone.test.ts` (run cmd in each file header).
- Goldens: `uv run python -m freemocap.tests.streaming_fixtures.regenerate_golden` then copy
  `schema_golden.json` + `sample_golden.bin` into `freemocap-ui/src/services/server/transport/__fixtures__/`.
  **Regeneration IS a wire change** (Python↔TS parity anchors).
- Windows: `python3` is NOT on PATH — use `node -e` for JSON, `python`/the venv for Python.
- The user runs the gate (`python freemocap/__main__.py` + `npm run dev`); 4× USB cameras
  (d441/be07/099c/583d); TensorRT unavailable (nvinfer_10.dll missing → CUDA fallback is normal, not an
  error). The agent CANNOT run the cameras — instrument minimally, read one line, no `[TEMP]`-log spam.
