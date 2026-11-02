# Server output contract delta

Execution approved 2026-11-01 through the coordinator's verbatim user instruction.
The global and child wording in `streaming-output-dependencies.md` is frozen.
Parent owns shared lifecycle/API/SDK/UI; protocol agents own only their emitter
modules/tests. Renderer and mesh assets belong to the separate native Skelly owner.

## Existing scientific contracts

SkellyCam's `pre_frame_grab_ns` and `post_frame_grab_ns` are immutable acquisition
clock values. Its `calculate_frame_grab_timestamps` accessor gives the integer
midpoint used in recording CSVs. Camera nodes currently carry capture seconds to
the aggregator; the output boundary will additionally preserve original integer
camera midpoints rather than reconstructing nanoseconds from seconds. Neither
source nor adapter may substitute processing, arrival or emission time.

Forge's `definitions/human_skeleton/rest_pose.yaml` explicitly derives the human
rest geometry from colocated `default-vrm.gltf.json5`; joints supply the hierarchy.
Resolved `RestPose.segment_orientations` and wire `rest_orientation` are WORLD rest
rotations, even though YAML orientations are authored parent-relative. Existing
coordinate conversions distinguish VRM asset and Unity receiver conventions.
Only the target profile's rig-frame/name projection belongs in the VMC adapter.

## Added control resource

For the usual local VMC receiver, `POST /freemocap/streaming/vmc/start` needs no
request body. It uses the existing VMC defaults (`127.0.0.1:39539`, automatic sole
pipeline) and returns an existing matching idle/running output on repeated calls.
The SDK exposes `streaming_start_vmc()`; the current inventory has 65 operations.
In the Streaming tab's left sidebar, the visible **Streaming outputs** section
offers **Start VMC** and per-output **Stop VMC**. Custom settings are under
**Advanced output settings**. Starting an output does not start capture.

Use `/freemocap/streaming/protocols` for GET capability/schema discovery and
`/freemocap/streaming/outputs` for POST create and GET list. GET and DELETE
`/freemocap/streaming/outputs/{output_id}` inspect and stop one output.
These are new resources; no existing scientific endpoint or wire shape changes.

Creation accepts protocol, protocol-specific validated config, optional pipeline_id
and bounded queue_capacity. An explicit source can start idle. An omitted source
selects the sole active pipeline; ambiguity is a 409 conflict, never an arbitrary
choice. Unknown IDs/protocols are 404; invalid config is 422; a missing protocol
runtime is 503. Creation does not start capture. Stop is idempotent for an existing
output and releases only that output; stopped/failed state remains inspectable.

Outputs are app-owned and ephemeral. A browser disconnect does not stop them.
They transition idle -> running when samples arrive, return idle when capture
stops, and fail independently on emission/source errors. State reports source
frame-number gaps separately from output queue drops/overflows. A frame-number gap
is not a claim about whether capture, inference selection or output polling caused it.
VMC uses a bounded latest-pose queue with observable drops; LSL fails on overflow
instead of silently applying pose-loss semantics. Capture is never backpressured.

Emitters receive frozen OutputSample(frame, pipeline_id, source_timestamp_ns,
camera_timestamps_ns), own their transport, and expose emit(sample)/close().
They do not call pipeline APIs. The server composes owned numeric channels without
image encoding or a CBOR round trip. Per-source composition/cursors are independent
of WebSocket connections. The acquisition timestamps survive queueing unchanged.

LSL's native runtime is opt-in through the `lsl` package extra. Protocol discovery
reports whether it can load, and creation returns 503 with the specific missing
runtime reason. This keeps an optional native transport from becoming a startup
requirement for ordinary HTTP/WebSocket/VMC use. The validated private environment
uses pylsl 1.18.6 and liblsl 118 (v1.18.0.b6); no canonical environment or lockfile
was changed. VMC uses the standard-library UDP socket implementation.

Source rollover retires the prior LSL outlets and creates new stream identities;
receivers must rediscover the new session. One output follows one selected source
at a time. Historical status retains no queued frame buffers, and unfinished
workers continue to count toward the 16-worker bound even after a failure.

## Local verification, 2026-11-01

The generated SDK now covers 64 operations: the prior 59 plus five additive output
operations. The original compatibility record remains intact. SDK tests: 99 pass;
UI TypeScript check and three StrictMode browser tests pass. Real-manager HTTP
tests cover running/idle/stopped state, independent outputs, exact acquisition
provenance and 404/409/422/503 errors.

Independent real-server checks use the private LSL environment and the isolated
Core source. Both SDK and browser controls discover, start and stop actual VMC/LSL
emitters without a WebSocket or camera. Server shutdown with an idle output also
exits cleanly. Evidence: `.test-artifacts/streaming-outputs/http-01/` and
`http-ui-01/`; each has request/result logs and a clean server-cleanup record.
The browser screenshot is an isolated component harness, not full-app visual
acceptance. Canonical integration and the live/receiving-avatar checks are open.
