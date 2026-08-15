# Handoff — 2026-08-15 (one producer-composed stream landed; 2D overlay upgraded; user mid-calibration)

**For a fresh agent (or the same one after compaction).** This file is the entry point. Follow the
orientation protocol below, then **confirm your understanding with the user in chat before touching
anything**. Do not start work on assumptions — the user has repeatedly (and correctly) rejected agents
who read stale docs, patched symptoms instead of structures, or required restarts in the workflow.

## The orientation protocol (exhaustive)

Read, in this order:

1. **This file** — the whole thing. It is the live state.
2. **[`ontology.md`](ontology.md)** — the kinematic ontology (keypoint → mapping → landmark → segment →
   skeleton). The now-DoD: a **VMC-compatible realtime segment stream** to the frontend. The constraint/
   solve layer (linkages, chains/IK) is **future — seams only, do not describe it as current**.
3. **[`00-foundation/conventions.md`](00-foundation/conventions.md)** + [`glossary.md`](00-foundation/glossary.md) —
   mm · right-handed · +Z up · +X forward; quaternions **wxyz**; **identity == T-pose**;
   `q_local = conj(q_parent)·q_child`; 60 segments / 76 landmarks (single-sourced in the glossary).
4. **[`01-data-model/stream-contract.md`](01-data-model/stream-contract.md)** — THE wire contract. The
   producer model, the channel table (kinds 0–9 — note `OVERLAY_REPROJECTIONS = 9` landed 2026-08-15),
   the schema-signature lifecycle, dtype codes (FLOAT32=0, UINT8=1 for `IMAGE_JPEG`). This is the
   single source of truth for shapes.
5. **[`03-transport/backend-encoder-ws.md`](03-transport/backend-encoder-ws.md)** +
   [`standard-stream-protocol.md`](03-transport/standard-stream-protocol.md) — one relay, one consumer,
   newest-wins, no ack window, images in the sample.
6. **[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)'s progress log** — history only. The layer docs
   are the live plans; where docs and code disagree, **the code wins and the doc is a bug** (fix the doc).
7. The code itself, in this order: `core/streaming/standard_stream/producers/` →
   `api/websocket/{frame_relay,websocket_server,send_serializer}.py` →
   `core/pipeline/realtime/realtime_aggregator_node.py` (the reprojection site) →
   `freemocap-ui/src/services/server/` (TransportService → SchemaRegistry → ServerContextProvider →
   `server-helpers/{canvas-manager,offscreen-renderer.worker}.ts` → `image-overlay/skeleton-overlay-renderer.ts`).

`archive/` is history, never guidance. The workspace is a **multi-repo** clone (`project/freemocap/`
contains `freemocap/` + `freemocap-ui/`; `skellyforge`/`skellytracker` are siblings). freemocap installs
the skellies **from git**, so local skelly edits are invisible until the user commits/pushes them and
`uv sync` advances the pin. **The user owns ALL git — never commit, push, or suggest it; report stopping
points instead.**

**Before proceeding, confirm with the user that you understand:** (a) the one-stream model and why the
two-stream model was deleted; (b) the no-restart runtime invariants below; (c) the current queue and
what "the gate" is. Ask if anything is unclear. Then and only then pick up the work.

## Where we are right now (2026-08-15)

The unified streaming layer is **landed and green end-to-end** (all on disk, uncommitted — the user owns
the commit round). What exists:

- **One producer-composed stream.** `standard_stream/producers/` composes the schema and every sample
  from five producers (keypoints / segment / overlay / derived / image). `FrameRelay` is the single
  consumer of the aggregator output; flow control is newest-wins (**no** `BackpressureController` — it's
  deleted). The camera JPEGs ride every sample as an `IMAGE_JPEG` uint8 block; `SEGMENT_LENGTHS` is
  per-frame; the schema re-sends only when a composite producer **signature** changes. The frontend
  consumes one sample per frame: the image and its overlays are delivered to the per-camera canvas
  workers as a matched pair keyed by frame number (the old 500 ms staleness heuristic is deleted).
- **The 2D overlay upgrade.** `OVERLAY_2D` (DETECTIONS) = the tracker's raw 2D keypoints → small dots,
  no connections. `OVERLAY_REPROJECTIONS` (kind 9) = the fitted skeleton's **60 segment-origin
  landmarks** projected into each camera by the aggregator (valid calibration only) → larger dots with
  the schema's segment parent→child `connections` between them, plus an always-on stats HUD
  (`f <frame> · kp <n> · lm <n>`) per camera feed. In 2D-only mode the reprojection rows are NaN →
  nothing drawn.
- **The user is calibrating the cameras right now.** The moment a valid calibration is saved, the
  running server hot-reloads it (see the invariants) and the 3D solve + the landmark skeleton lines
  light up live. No restart, ever.

## Runtime invariants (hard-won — do not break them)

1. **No restarts in the workflow.** The server stays up across configuration changes. Two concrete
   mechanisms, both live:
   - **Calibration hot-reload:** the aggregator polls the calibration TOML every 1 s
     (`CALIBRATION_POLL_INTERVAL_SECONDS` in `realtime_aggregator_node.py`; `check_for_update()` in
     `calibration_state.py` compares mtimes) → reloads → `is_valid` → the next frame carries real
     `OVERLAY_REPROJECTIONS` values. Finishing a calibration turns the 2D skeleton lines on **live**.
   - **Config changes rebuild the schema via the pubsub network.** The supervisor subscribes to
     freemocap's `PipelineConfigUpdateTopic` (per pipeline) and skellycam's
     `UPDATE_CAMERA_SETTINGS` / `EXTRACTED_CONFIG` (per camera group — the camera workers publish the
     extracted config when they apply a settings change, e.g. a rotation). Any message → a FULL schema
     rebuild + resend. The composite **signature** (which includes `camera_image_sizes` — a rotation
     swaps width/height while keeping the same camera ids, and was a real bug until included) remains
     as the backstop for pipeline start/stop and configs mid-application.
   Any future data-model change must ride the same mechanism, not a restart.

2. **The stream is lockstep by construction.** Images, overlays, and pose for frame N travel in ONE
   sample. Do not reintroduce a second send path, a second consumer of `aggregation_output_subscription`,
   or any cross-stream timing heuristic (that was the original blink bug).

3. **Expected cases are not log spam.** Running without a valid calibration is a normal 2D-only mode:
   per-frame triangulation failures are `debug`-level; exactly one summary ERROR at invalidation, no
   traceback. (Same principle for any other "totally OK" state.)

## Where the work stands per repo

| Repo | State | Suite |
|---|---|---|
| skellyforge | committed+pushed through the 2026-08-14 round (landmark sweep, face-provenance reword, tracker-contract test); on-disk round (`tracker_contract.py` reads `landmark_names`, `rest_roll` removed, `observation.py` freeze) still uncommitted | 148 green at push; 141 + 4 tracker-contract tests post-round |
| skellytracker | mapping language sweep (keypoint→landmark naming in the YAMLs + `TrackerMapping`) | 234 green |
| freemocap | committed+pushed through the 2026-08-14 round (docs reorg, F0–F4, Sweep 3). **On disk since, uncommitted: the entire unified-stream cutover + the overlay upgrade** (producers, single relay, signature lifecycle, IMAGE_JPEG, SEGMENT_LENGTHS, OVERLAY_REPROJECTIONS, deleted backpressure/frontend-payload machinery, TS cutover, goldens) | **133 green** backend subset; `tsc` clean; TS harnesses green (decoder 6 / integration 3 / rigid-body 6) |
| freemocap-ui | part of the freemocap repo (same clone root) — TS cutover landed on disk | as above |

**First action on pickup (the user):** the commit round for all of the above — nothing more.

## The queue (in order)

0. **The commit round — [USER].** Review + commit + push everything on disk (skellyforge round;
   freemocap unified-stream + overlay work). Report the stopping point, don't touch git.
1. **Finish the manual calibration → the F5 gate.** The user is calibrating now. Then the gate
   checklist: T-pose at capture start (identity frames), arm bend rotates the humerus mesh without
   pop, hidden-hand degradation (no crash), no schema drift, and now also: **dots + landmark skeleton
   lines + stats HUD in lockstep with the video, no blinking**.
2. **F5+1 — the VMC adapter** (thin VRM 1.0→0.x name map; local frames are already VMC-ready).
3. **The posthoc rebuild** ([`02-pipeline/posthoc-rebuild.md`](02-pipeline/posthoc-rebuild.md)) — gated
   on F5.

## Known gaps (flagged, deliberately not done in the cutover)

- **Dead `tracker_schemas` handshake** — the frontend still handles it (provider handler →
  `canvasManager.setSchema` → worker `schema` message → `OverlayManager.setTrackerSchemas` →
  renderer `setSchema`), but nothing sends it anymore. The renderer no longer uses it for connections
  (landmarks use the schema's `connections` now). Delete the whole chain as one cleanup.
- **Dead charuco renderer files** on the frontend (`charuco-overlay-renderer.ts`, `charuco-types.ts`,
  the OverlayManager charuco half) — no producer feeds charuco overlays anymore.
- **Playback HTTP path** serves images outside the unified stream — untouched, still works, revisit in
  the posthoc rebuild.
- **`IMAGE_JPEG` is one opaque multi-camera blob** — per-camera blocks are the documented future shape
  (needs SkellyCam payload unpacking backend-side).
- **The rigid-body renderer reads schema-default lengths** — live per-frame `SEGMENT_LENGTHS` is
  resolved into `TransportService.segmentLengthsWindow` + exposed via `getLatestSegmentLengths()`, but
  the 3D renderer doesn't merge them yet.
- **Keypoint connections deliberately NOT drawn** — the user wants keypoints as plain small dots; only
  the landmark layer gets connections.
- The stale-calibration camera-set mismatch (`d441` vs TOML `4da6`) is the user's environment state —
  expected to resolve with the current calibration round.

## Locked decisions (do not re-litigate)

- One producer-composed stream, schema as the single source of truth for the data model, newest-wins,
  no ack window, images in the sample — the whole "Current initiative" history is settled; the
  two-stream model was a defect, not an option.
- The overlay split: keypoints = small dots; segment-origin landmarks = larger dots + connections.
- Landmark is REVIVED with the precise two-faced meaning; "canonical" (mapping sense), `long_axis`,
  `twist_keypoint`, `from/to_keypoint` are retired. Code describes the system AS IT IS.
- All axis targets inside the segment's own landmarks; VRM local conventions (+Y toward child, +Z gaze);
  the observed/unobserved-DOF flag is dropped (the graded landmark count is the seam).
- The rest-pose/model side never imports skellytracker at runtime (`tracker_contract.py` only).
- The stabilization stack (Euro filter → tree/fit rigidification → critically-damped solve) is settled.
- `data_models/observation.py` is a frozen legacy copy that dies with the posthoc rebuild.
- **Working rules:** never touch git (the user owns it); plan==code (docs edited in the same pass);
  fail loudly; no duplicated information; no backwards compat; cross-repo work ends at commit rounds;
  check in before changes; **keep answers short**; **no restarts as a workflow requirement**;
  expected cases log quietly.

## Env

- Suites (all green as of this handoff):
  - freemocap backend subset: `uv run --group dev pytest freemocap/tests/rigid_body/
    freemocap/tests/test_standard_stream_contract.py freemocap/tests/test_stream_schema_builder.py
    freemocap/tests/test_center_of_mass.py freemocap/tests/test_stream_sample_encoder.py
    freemocap/tests/test_send_serializer.py freemocap/tests/test_frame_relay.py
    freemocap/tests/test_full_loop.py freemocap/tests/kinematics/ -q` → **133 passed**.
  - TS: `npx tsc --noEmit` (clean) + the three house harnesses (esbuild+node — NO Vitest):
    `standard-stream-decoder.test.ts`, `standard-stream-integration.test.ts`,
    `rigid-body-bone.test.ts` (run pattern is in each file's header).
- Golden fixtures: `uv run python -m freemocap.tests.streaming_fixtures.regenerate_golden` then copy
  `schema_golden.json` + `sample_golden.bin` into
  `freemocap-ui/src/services/server/transport/__fixtures__/`. **Regeneration IS a wire change** — the
  goldens are the Python↔TS parity anchors.
- The user's gate workflow: `python freemocap/__main__.py` + `npm run dev` in `freemocap-ui/`; cameras
  are 4× USB (d441/be07/099c/583d); TensorRT is unavailable on this machine (nvinfer_10.dll missing —
  CUDA fallback is the normal state, not an error).
