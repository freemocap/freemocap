# Handoff — 2026-08-16: backend message model DONE + green; frontend (step 3) is the remaining work

**For a fresh agent (or the same one after compaction).** This is the entry point and the live state. Read the orientation protocol, then confirm your understanding with the user before touching anything. Docs and code both drift; neither is authoritative — err on "build the best possible system" and read whichever artifact was written most recently.

## The orientation protocol (read in this order)

1. **This file.**
2. ontology.md — keypoint → mapping → landmark → segment → skeleton. Now-DoD: a VMC-compatible realtime segment stream. The constraint/solve layer (linkages, chains/IK) is **future — seams only**.
3. 00-foundation/conventions.md + glossary.md — mm · right-handed · +Z up · +X forward; quaternions **wxyz**; **identity == T-pose** (the solver measures relative to a NON-identity rest frame); 60 segments / 76 landmarks.
4. 03-transport/message-protocol.md — **THE plan for the wire**: self-describing CBOR **messages** (no schema, no samples). Status: step 2 DONE (backend green); step 3 frontend next.
5. 01-data-model/message-contract.md — the message **types** (Zod union + Python frozen-slots dataclasses; envelope, kinds, frame shape, client homes).
6. 03-transport/message-relay.md (backend, IMPLEMENTED) + 04-ui/ui-integration.md (frontend dispatcher + preservation inventory, step 3).
7. IMPLEMENTATION_PLAN.md progress log — history only.

archive/ is history, never guidance. Multi-repo: project/freemocap/ holds freemocap/ + freemocap-ui/; skellyforge/skellytracker/skellycam/skellylogs are siblings; freemocap installs the skellies **FROM GIT** (local edits invisible until the user commits/pushes + uv sync). **The user owns ALL git — never commit/push/suggest it.**

## THE load-bearing principle (message form)

Consumers tolerate whatever they receive: **any valid message set**, including one that omits a kind the consumer cares about. A consumer that assumes a kind is always present (and breaks when absent) is **the bug**; a producer emitting a valid partial set is **not**. Resolve-a-kind logic degrades to draw/emit nothing, never throw. (First instance: the bone renderer returns an empty table on an image-only frame.)

## Where we are right now (2026-08-16)

- **Backend message model: COMPLETE + green (74 backend tests pass).** The old schema-then-samples wire is GONE from the backend:
  - standard_stream/ (stream_schema.py, stream_sample.py, coordinate_convention.py, lsl_bridge.py, sample_block_helpers.py, the old producers/) is DELETED.
  - Producers rewritten: fill() -> list[ChannelBlock] (kind + names + columns + data inline). No schema_groups/schema_metadata. The image is no longer a channel — it is the frame message's image field (from frame_ctx.image_payload).
  - websocket_server.py emits CBOR messages: frame (every frame) + convention/model/camera_layout (replace-kinds, on connect + change) + log/framerate/app_state/progress (telemetry).
  - send_serializer.py = send_message / send_raw_bytes / send_raw_text only (JSON/schema/sample send paths removed).
  - channel_helpers.py (assemble_channel_bytes, camera_2d_detections, origin_landmark_names) replaces sample_block_helpers.
  - ChannelKind is a StrEnum in message_model.py (single source); the legacy IntEnum is gone.
  - Old wire tests deleted (test_standard_stream_contract, test_stream_schema_builder, test_stream_sample_encoder, regenerate_golden + schema/sample goldens). New test_message_model.py + rewritten test_frame_relay.py / test_full_loop.py / test_send_serializer.py.
- **skellylogs (sibling repo):** SKELLYLOGS_LOG_DIR env var + use_websocket=False flag (committed/pushed).
- **freemocap eager-logging fix:** configure_logging moved from freemocap/__init__.py + core/__init__.py to __main__.py main() (startup, once). import freemocap is now side-effect-free — this is what lets the agent run the backend locally (was blocked before).
- **3D bones:** fixed + committed (rest-derived orientation; renderer composes ROTATIONS_WORLD · rest_orientation · Q_permute · S).
- **Frontend: step 3 NOT started.** It still expects the old schema-then-samples (wire-types.ts, StandardStreamDecoder.ts, SchemaRegistry.ts, the stream_schema/sample goldens + decoder test). **The app is BROKEN until step 3** (backend sends CBOR; frontend cannot decode it).

## The WHY (imprint this — it is the point of the whole refactor)

- **Why the message model:** schema-then-samples made decode correctness depend on a separately-held descriptor. A sample carries no reference to which schema it assumes, so a stale schema (browser + server restart independently) decodes WRONG with NO error. Self-describing messages remove that coupling — every message decodes on its own terms.
- **decode-complete vs render-complete:** CBOR + inline names = decode-complete (bytes → typed values with zero state). Rendering bones still needs the held model slice (rest orientations/axes/connections) — that is render-complete, which we deliberately do NOT claim. Honesty about this boundary keeps the design honest.
- **Plain byte strings, not typed-array tags:** the packed float32 channel data is pre-serialized to little-endian bytes before CBOR. This sidesteps the float16 downcast (silent precision loss) and the cbor2-vs-cbor-x tag-identity risk. Scalar floats stay float64.
- **Naming rules (hard-won, enforce them):** no single-word file names; no single-word public class/function names; NO import aliasing (X as Y) for internal imports; NEVER import old stuff into new files; positive definitions (say what a thing IS, not what it isn't).
- **Clean language:** message / kind / channel / ChannelBlock / FrameMessage. NEVER schema / sample / standard_stream / ChannelGroup / SampleBlock / StreamSchema / StreamSample — all retired. (Legitimate non-streaming "schema" uses remain: tracker schema = TrackedObjectDefinition for playback; OpenAPI schema; "sample data" = test downloads.)
- **Eager-logging init was an import side effect** (I/O + thread spawn at import freemocap) — the root cause of the agent's sandbox blocks. Fixed by moving configure_logging to startup.

## The queue (in order)

1. **[USER] commit round** — verify git: backend message model + cleanup + skellylogs may already be committed; the freemocap eager-logging fix + doc/comment cleanup + the message_model Hashable fix are the newest edits (likely uncommitted).
2. **Step 3 — frontend dispatch** (THE next work; detail below).
3. **Step 4 — delete old frontend schema/sample.**
4. **Step 5 — verify preservation** (F5 gate + tsc + the 3 harnesses).
5. VMC adapter, then posthoc rebuild.

## Step 3 — frontend dispatch (the next work, in detail)

The backend sends CBOR messages (kinds: frame, convention, model, camera_layout, log, framerate, app_state, progress). The frontend still demuxes the OLD schema-then-samples. The demux is currently SPLIT: TransportService owns stream_schema JSON + binary sample (via RoutingTable); ServerContextProvider owns a SEPARATE transport.on('message') JSON if/else (isLogRecord / isFramerateUpdate / isPosthocProgress / isAppState / isTrackerSchemas). Step 3 unifies this into ONE dispatcher keyed on kind.

Files to change:
1. TransportService.ts — the dispatcher. Decode ALL binary frames via cbor-codec.decodeMessage, validate against the Zod union (message-contract.ts), route by kind to its home.
2. RoutingTable.ts — generalize into a kind dispatcher (kind string → handler), or fold into TransportService.
3. ServerContextProvider.tsx — DELETE the JSON if/else; it becomes a thin composition root (~200 lines).
4. New RTK slices: model, convention, camera_layout (the replace-kinds; replace). model carries rest orientations + axes + lengths + connections — what the bone renderer needs.
5. RigidBodyBoneRenderer.tsx + KeypointsSourceContext.tsx — re-point from getStreamSchema()/subscribeToSchema() (StreamSchema) to the model slice.
6. Delete: StandardStreamDecoder.ts, SchemaRegistry.ts, wire-types.ts, the stream_schema/sample goldens + standard-stream-decoder.test.ts.

Client homes (from message-contract.md): frame → frame subscribers (fast); convention/model/camera_layout/app_state/progress → RTK slices (replace); log → LogStore (append); framerate → FramerateStore (fast).

Risks/edge cases (from the pre-swap audit):
- The bone renderer needs the model slice BEFORE frames arrive; route model → RTK slice and have the renderer read the slice (not the deleted getStreamSchema()).
- app_state has cross-slice listeners (cameras + realtime slices reconcile on serverStateReceived); dispatch the SAME action so they keep firing.
- tracker_schemas handshake is DEAD on the wire, but TrackedObjectDefinition + ConnectionRenderer + getActiveSchema are LIVE for PLAYBACK — delete only the handshake.
- The inbound frameAcknowledgment (displayImageSizes) stays (drives SkellyCam JPEG downscaling).
- image is the opaque multi-camera JPEG blob (decoded by FrameProcessor/binary-frame-parser.ts); per-camera image blocks are future work.

## Known gaps (flagged, not done)

- image is one opaque multi-camera JPEG blob (per-camera blocks = future).
- The 3D renderer reads the anthropometric default lengths (model slice); live per-frame SEGMENT_LENGTHS not merged yet.
- Bone joint sphere + lit shading deferred.
- Playback HTTP image path is outside the unified stream (posthoc rebuild).
- The frontend still has the old schema/sample files until step 3/4 deletes them.

## Locked decisions (do not re-litigate)

- Message model: one WebSocket of typed self-describing CBOR messages; envelope (kind, version, timestamp, sequence — full names); flat kinds split by source; no schema/samples; replace-kinds idempotent (latest-wins); dispatcher in TransportService; hard cutover.
- VRM-1.0 rest pose (world stays +Z-up, re-express at the adapter edge).
- 3D bones: world-quaternion orientation with a rest-derived frame.
- Plain byte strings (not typed-array tags) for packed float32 channel data.
- Calibration stays HTTP (kind reserved, not emitted) — the frontend loads calibration over HTTP today.
- Landmark REVIVED; long_axis/twist_keypoint/from-to/"canonical" retired.

## Working rules

never touch git; plan==code; fail loudly; no duplicated info; no backwards compat; no restarts as a workflow requirement; expected cases log quietly; no single-word file names; no single-word public class/function names; no import aliasing for internal imports; no importing old stuff into new files; positive definitions.

## Env

- Backend subset (74 passed): uv run --group dev pytest freemocap/tests/rigid_body/ freemocap/tests/test_center_of_mass.py freemocap/tests/test_message_model.py freemocap/tests/test_send_serializer.py freemocap/tests/test_frame_relay.py freemocap/tests/test_full_loop.py freemocap/tests/kinematics/ -q
- TS: cd freemocap/freemocap-ui && npx tsc --noEmit + esbuild+node harnesses (NO Vitest): transport/__tests__/message-golden.test.ts (the 3 old harnesses remain until step 3/4 removes them). cbor-x is a dep.
- Goldens: uv run python -m freemocap.tests.streaming_fixtures.regenerate_message_golden, copy message_*_golden.bin into freemocap-ui/src/services/server/transport/__fixtures__/.
- The user runs the gate (python freemocap/__main__.py + npm run dev); 4× USB cams; TensorRT unavailable (CUDA fallback normal). The agent CANNOT run cameras. The agent CAN now import freemocap (logging fix), but heavy skellyforge/skellycam imports (mediapipe native) still crash the sandbox — run those via the user.
