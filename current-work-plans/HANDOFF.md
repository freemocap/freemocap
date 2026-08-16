# Handoff — 2026-08-15 (evening): bones fixed + message-model plan locked

**For a fresh agent (or the same one after compaction).** This is the entry point and the live state.
Read the orientation protocol, then confirm your understanding with the user before touching anything.
Docs and code both drift; neither is authoritative — when they disagree, err on the side of building the
best possible system and read whichever artifact was written most recently.

## The orientation protocol (read in this order)

1. **This file.**
2. [ontology.md](ontology.md) — keypoint → mapping → landmark → segment → skeleton. Now-DoD: a
   **VMC-compatible realtime segment stream**. The constraint/solve layer (linkages, chains/IK) is
   **future — seams only**.
3. [00-foundation/conventions.md](00-foundation/conventions.md) + [glossary.md](00-foundation/glossary.md) —
   mm · right-handed · +Z up · +X forward; quaternions **wxyz**; **identity == T-pose** (the solver's
   measurement frame — the *rest frame itself* is NOT identity); 60 segments / 76 landmarks.
4. [03-transport/message-protocol.md](03-transport/message-protocol.md) — **THE plan for the wire**: a
   self-describing CBOR **message** model (no schema, no samples). Status: PLANNED — design locked, not
   yet implemented; the committed code still uses schema-then-samples.
5. [01-data-model/message-contract.md](01-data-model/message-contract.md) — the message **types** (Zod
   union, envelope, frame shape, client homes).
6. [03-transport/message-relay.md](03-transport/message-relay.md) (backend send path) +
   [04-ui/ui-integration.md](04-ui/ui-integration.md) (frontend dispatcher + the preservation inventory).
7. [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)'s progress log — history only.

archive/ is history, never guidance. Multi-repo clone: project/freemocap/ holds freemocap/ + freemocap-ui/;
skellyforge / skellytracker are siblings; freemocap installs the skellies **from git** (local skelly edits
are invisible until the user commits/pushes + uv sync). **The user owns ALL git — never commit, push, or
suggest it.**

## THE load-bearing principle (message form; survives the swap)

Consumers tolerate whatever they receive: **any valid message set**, including one that omits a kind the
consumer cares about. A consumer that assumes a kind is always present (and breaks when it is absent) is
**the bug**; a producer emitting a valid partial set is **not**. Resolve-a-kind logic should degrade to
draw/emit nothing, never throw. (This is the message-model form of the old schema-producer↔consumer
contract; first instance: the bone renderer buildBoneInstances returns an empty table on an image-only
frame instead of throwing.)

## Where we are right now

- **3D bones render correctly** (rest-derived orientation, committed). The ~90° error was a rest-frame-
  convention gap, not a solver bug: ROTATIONS_WORLD is measured relative to each segment's rest frame
  (identity == T-pose), and that rest frame is not identity — a body segment +Y points toward its child
  (the spine +Y is world +Z, up). Fix: RestPose now carries orientations (per-segment rest-frame
  orientation, wxyz) and the renderer composes ROTATIONS_WORLD · rest_orientation · Q_permute · S.
- **The message-model plan is locked** (docs written; not yet implemented). The committed code still uses
  schema-then-samples; the swap is queue item 3.

The message-model docs + renames + this handoff are **uncommitted on disk**; the bones-fix code is
committed (HEAD 6a24337c).

## Where the work stands per repo

| Repo | State |
|---|---|
| skellyforge | committed+pushed (7863c0d skull stif) — rest basis + axis-agnostic math; nothing pending |
| skellytracker | committed+pushed (4a7b390 re-add lost dots) — 234 green |
| freemocap (+ freemocap-ui) | bones fix committed (6a24337c); message-model plan + doc renames uncommitted |

## The queue (in order)

1. **[USER] commit round** — the message-model docs + renames + this handoff. Never touch git.
2. **F5 gate** — manual full-loop: T-pose, arm bend without pop, hidden-hand degradation, no drift,
   lockstep, correct orientation.
3. **Message-model swap** — implement message-protocol.md (build order is in that doc), completing the
   ServerContextProvider/WebsocketServer decomposition. Preserve every live path (inventory in
   ui-integration.md).
4. **F5+1 — VMC adapter**, then the posthoc rebuild.

## Known gaps (flagged, deliberately not done)

- IMAGE_JPEG is one opaque multi-camera blob — per-camera blocks are the documented future shape.
- The 3D renderer reads schema-default segment_lengths — live per-frame SEGMENT_LENGTHS not merged yet.
- Bone joint sphere + lit shading deferred.
- Playback HTTP image path is outside the unified stream — revisit in the posthoc rebuild.
- Dead tracker_schemas handshake + dead charuco renderer files — flagged, delete during the swap.

## Locked decisions (do not re-litigate)

- **Message model** (message-protocol.md): one WebSocket of typed self-describing CBOR messages; envelope
  (kind, version, timestamp, sequence — full names); flat kinds split by source; no schema/samples;
  replace-kinds idempotent (latest-wins); dispatcher in TransportService; hard cutover.
- **VRM-1.0 rest pose** — the default VMC consumers can handle directly; the world stays +Z-up and
  re-expresses at the adapter edge.
- **3D bones: world-quaternion orientation with a rest-derived frame**.
- Landmark REVIVED; long_axis / twist_keypoint / from-to / "canonical" retired.
- **Working rules:** never touch git; plan==code; fail loudly; no duplicated info; no backwards compat;
  no restarts as a workflow requirement; expected cases log quietly.

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
- The user runs the gate (`python freemocap/__main__.py` + `npm run dev`); 4× USB cameras; TensorRT
  unavailable (nvinfer_10.dll missing → CUDA fallback is normal). The agent CANNOT run the cameras.
