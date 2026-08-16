# Handoff — 2026-08-15 (evening): 3D bones render correctly — rest-derived orientation landed

**For a fresh agent (or the same one after compaction).** This is the entry point and the live state.
Read the orientation protocol below, then confirm your understanding with the user before touching
anything. Docs and code both drift; neither is authoritative — when they disagree, err on the side of
building the best possible system and read whichever artifact was written most recently.

## The orientation protocol (read in this order)

1. **This file.**
2. [`ontology.md`](ontology.md) — keypoint → mapping → landmark → segment → skeleton. Now-DoD: a
   **VMC-compatible realtime segment stream**. The constraint/solve layer (linkages, chains/IK) is
   **future — seams only**.
3. [`00-foundation/conventions.md`](00-foundation/conventions.md) + [`glossary.md`](00-foundation/glossary.md) —
   mm · right-handed · +Z up · +X forward; quaternions **wxyz**; **identity == T-pose** (the solver's
   measurement frame — the *rest frame itself* is NOT identity); 60 segments / 76 landmarks.
4. [`01-data-model/stream-contract.md`](01-data-model/stream-contract.md) — THE wire contract: the
   producer model, the channel table (kinds 0–9), **the rest pose** (`positions` + `orientations`),
   and the schema-producer↔consumer contract (below).
5. [`03-transport/backend-encoder-ws.md`](03-transport/backend-encoder-ws.md) +
   [`standard-stream-protocol.md`](03-transport/standard-stream-protocol.md) — one relay, one consumer,
   newest-wins, no ack window, images in the sample.
6. [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)'s progress log — history only.

`archive/` is history, never guidance. Multi-repo clone: `project/freemocap/` holds `freemocap/` +
`freemocap-ui/`; `skellyforge`/`skellytracker` are siblings; freemocap installs the skellies **from
git** (local skelly edits are invisible until the user commits/pushes + `uv sync`). **The user owns
ALL git — never commit, push, or suggest it.**

## THE load-bearing principle — the schema producer↔consumer contract

This is an LSL-style stream: **the schema producer may emit ANY valid schema variation** (image-only in
camera-only mode; image + full reconstruction when a pipeline is live; any future producer set), and
**EVERY consumer MUST gracefully handle whatever schema it receives** — including a schema that omits a
channel group the consumer cares about. A consumer that assumes a group is always present (and breaks
when it is absent) is **the bug**; a producer emitting a valid partial schema is **not**. Resolve-a-group
logic should degrade to "draw/emit nothing," never throw. (First instance: the bone renderer's
`buildBoneInstances` now returns an empty table on an image-only schema instead of throwing.)

## Where we are right now (2026-08-15 evening)

The unified streaming layer is landed, the 2D overlay (detections + reprojections + stats HUD) looks
good, and the **3D rigid-body bones now render with correct orientation**. The ~90° mis-orientation was a
**rest-frame convention** gap, not a solver bug: `ROTATIONS_WORLD` is measured *relative to each
segment's rest frame* (identity == T-pose), but the rest frame is not identity — a body segment's +Y
points toward its child, so the spine's +Y is world +Z (up). The renderer had been applying
`ROTATIONS_WORLD` against a *nominal* +Y, hence the ~90° error.

**The fix:** `RestPose` now carries `orientations` (per-segment rest-frame orientation, wxyz,
local→world T-pose, from `reference_geometry.basis`) in place of the old all-identity
`reference_orientations`; `segment_axes` (the long-axis basis name) stays. The renderer composes
`ROTATIONS_WORLD · rest_orientation · Q_permute · S` in `computeBoneMatrix`. **VRM-1.0-compatible by
construction** — the model already authors VRM 1.0 rest frames (body/hand +Y toward child, face +Z gaze);
the fix only puts them on the wire. The VMC adapter will consume the same VRM-local orientations and
re-express the world (+Z-up → VMC) at the edge.

All of this is **uncommitted on disk** in freemocap (the orientation fix + docs + goldens + tests).

## Where the work stands per repo

| Repo | State | Notes |
|---|---|---|
| skellyforge | committed+pushed (`7863c0d skull stif`) | rest basis + axis-agnostic math already committed; nothing pending |
| skellytracker | committed+pushed (`4a7b390 re-add lost dots`) | 234 green |
| freemocap (+ freemocap-ui) | committed through `d8487378`; **uncommitted since: the rest-orientation fix + docs + goldens + tests** | backend subset + `tsc` + 3 TS harnesses green |

## The queue (in order)

1. **[USER] the commit round** — everything on disk (the rest-orientation fix + docs + goldens + tests).
   Report the stopping point; never touch git.
2. **F5 gate** — the manual full-loop checklist: T-pose at capture start, arm bend rotates the humerus
   mesh without pop, hidden-hand degradation, no schema drift, dots + landmark lines + bones in lockstep
   with the video, **correct bone orientation**.
3. **Message-model swap** — implement the self-describing message protocol
   (03-transport/standard-stream-protocol.md), completing the ServerContextProvider/WebsocketServer
   decomposition. Preserve every live path (inventory in 04-ui/ui-integration.md). Design locked.
4. **F5+1 — the VMC adapter** (VRM 1.0→0.x name map + coordinate re-expression). Then **the posthoc
   rebuild** ([`02-pipeline/posthoc-rebuild.md`](02-pipeline/posthoc-rebuild.md)).

## Known gaps (flagged, deliberately not done)

- **`IMAGE_JPEG` is one opaque multi-camera blob** — per-camera blocks are the documented future shape.
- **The 3D renderer reads schema-default `segment_lengths`** — live per-frame `SEGMENT_LENGTHS` isn't
  merged yet.
- **Bone joint sphere + lit shading** — deferred (unlit `MeshBasicMaterial`; a joint sphere needs a
  separate uniformly-scaled instanced mesh).
- **Playback HTTP image path** is outside the unified stream — revisit in the posthoc rebuild.
- Dead `tracker_schemas` handshake + dead charuco renderer files (frontend) — flagged, not yet deleted.

## Locked decisions (do not re-litigate)

- **The schema producer↔consumer contract** (above) — system-wide.
- One producer-composed stream, schema as the single source of truth, newest-wins, no ack window, images
  in the sample. The two-stream model was a defect, not an option.
- **3D bones: world-quaternion orientation with a rest-derived frame** — the segment is math-agnostic
  about long↔x/y/z; VRM enters only at the rest pose.
- **Rest pose / T-pose is VRM-1.0-aligned** (the default that VMC consumers can handle directly); the
  world stays FreeMoCap's +Z-up and re-expresses at the adapter edge.
- Landmark REVIVED (two-faced meaning); `long_axis`/`twist_keypoint`/from-to/"canonical" (mapping
  sense) retired.
- **Working rules:** never touch git (user owns it); plan==code (docs edited in the same pass); fail
  loudly; no duplicated info; no backwards compat; no restarts as a workflow requirement; expected cases
  log quietly.

## Env

- freemocap backend subset: `uv run --group dev pytest freemocap/tests/rigid_body/
  freemocap/tests/test_standard_stream_contract.py freemocap/tests/test_stream_schema_builder.py
  freemocap/tests/test_center_of_mass.py freemocap/tests/test_stream_sample_encoder.py
  freemocap/tests/test_send_serializer.py freemocap/tests/test_frame_relay.py
  freemocap/tests/test_full_loop.py freemocap/tests/kinematics/ -q`.
- TS: `cd freemocap/freemocap-ui && npx tsc --noEmit` + three esbuild+node harnesses (NO Vitest):
  `transport/__tests__/standard-stream-decoder.test.ts`,
  `viewport3d/renderers/__tests__/standard-stream-integration.test.ts`,
  `viewport3d/renderers/__tests__/rigid-body-bone.test.ts` (run cmd in each file header).
- Goldens: `uv run python -m freemocap.tests.streaming_fixtures.regenerate_golden` then copy
  `schema_golden.json` + `sample_golden.bin` into `freemocap-ui/src/services/server/transport/__fixtures__/`.
  Regeneration IS a wire change (Python↔TS parity anchors).
- The user runs the gate (`python freemocap/__main__.py` + `npm run dev`); 4× USB cameras; TensorRT
  unavailable (nvinfer_10.dll missing → CUDA fallback is normal). The agent CANNOT run the cameras.
