# Playback streaming adaptation

Status: source audit and proposed implementation plan; awaiting design agreement.
Scope: recorded video playback within the Mocap posthoc/data-model initiative.
No production implementation or dependency changes in this audit.

## Existing machinery

- SkellyCam `core/recorders/videos/sequential_video_reader.py` owns PyAV sequential
  decoding, rotation and restart-from-start reads. Reuse it. Do not create video copies.
- SkellyCam `core/types/frontend_payload_bytearray.py:create_frontend_payload`
  owns multiframe image encoding/packing and enforces equal frame ordinals. Its
  input currently requires live-camera recarrays. Extract an image-oriented typed
  input boundary in SkellyCam; retain the live-camera adapter there. Do not fabricate
  capture timestamps or camera configuration to package a video frame.
- That packer currently caps resolution at half size, defaults JPEG quality to 60,
  and truncates camera IDs to 16 bytes. These are explicit adaptation points:
  playback encoding quality/resolution must be specified, rotation applied once,
  and transport identity must not truncate arbitrary media IDs. A session-local
  numeric index mapped to full media identity is a candidate for the existing
  payload camera slots; it is not a calibration-camera identity.
- FreeMoCap `api/websocket/frame_relay.py` composes CBOR frame messages and uses
  `send_serializer.py` for one-writer ordering. Actual live source selection in
  `websocket_server.py` is newest-wins. The relay itself need not introduce dropping.
- `TransportService.ts` dispatches CBOR. Its live model/image state is global to
  that transport instance, so playback frames must not overwrite live state.
- `ServerContextProvider.tsx` overwrites `pendingPayloadRef` on image receipt and
  acknowledges before image decoding. Neither operation provides playback credit.
- `FrameProcessor` and `frame-decode.worker.ts` already transfer buffers and decode
  images off-thread. `binary-frame-parser.ts` uses jpeg-js and returns RGBA buffers
  (some worker comments inaccurately describe ImageBitmaps). Reuse the actual code,
  adapting its input identity boundary jointly with the Python packer.
- `FrameLookahead`, the decoded-frame LRU, and playback's ordinal presentation
  controller own useful behavior. Replace the compressed-video decoder dependency
  underneath them, not the timeline or cache with another independent player.

## Proposed ownership and transport

SkellyCam owns video reading, synchronized image-group construction, and reusable
image packing/encoding. FreeMoCap owns recording-resource selection, the playback
session endpoint/lifecycle, and association with saved kinematics. The frontend
owns presentation time, group assembly, bounded caches and flow-control requests.
A playback session is not an inference pipeline; no inference service or fake
camera capture group should be created to play videos.

Prefer a dedicated playback WebSocket connection using the existing serializer,
CBOR infrastructure and image decode components. This isolates a large buffered
playback stream from live image/log/control traffic and avoids new stream routing
through singleton live state. A second connection is not a second transport stack.
Do not instantiate the live WebsocketRunner with its camera/application lifecycle.
Extract only reusable pieces proven necessary by the playback session.

Session control models: open selected recording/source; grant capacity; seek;
close. Server outcomes: ready, frame group, end, failed. Use enums and typed
Python/TypeScript contracts. Carry session identity, generation, source revision,
and multiframe ordinal. Distinguish stream delivery metadata from recording data
provenance; no new run IDs or output metadata are needed for this transport.

## Buffer and lifetime contract

Client grants a cumulative send limit per generation in a bounded window of
multiframe ordinals. Capacity is derived from reserved decoded bytes for all
images in a group, plus bounded encoded/in-flight buffers. Grants replenish in
batches as capacity becomes available; they are not one request per frame.
Repeated control messages cannot mint extra capacity. No unbounded worker queue.
Server checks credit before decoding; blocking decode/encode stays in managed
threads outside the event loop. Initial implementation bounds concurrent groups
and measures throughput before adding deeper parallelism.

Every transmitted ordinal contains all selected views. Presentation advances only
when the whole group is available. Encoded byte limits and decoded byte limits
must both be enforced. A single group too large for the budget is an explicit
configuration error, not unlimited allocation. Cache entries own their image
buffers; transferring a buffer into a canvas must not detach a retained cache entry.

Cached seeks display locally. Uncached forward seeks advance readers sequentially;
uncached backward seeks reopen at zero and decode forward. Seek increments the
session generation; revoke old credit and discard stale results even if native
work finishes late. Cache keys include source revision, media identity, frame
ordinal and encoding/resolution policy. Raw and annotated groups share the same
mechanism and preserve the selected ordinal when switching.

EOF must agree across the selected synchronized group. Report errors from any
reader/encoder to the session and stop sibling work. Closing the view, changing
recording, cancellation or disconnect releases readers, workers and buffers.
Playback failure must not stop realtime, Mocap processing, calibration, or the app.

## Image quality and reconstruction

Reuse JPEG transport as an explicit display encoding, not a change to originals
or saved measurements. Do not silently inherit the live half-size/quality-60
policy. Start prototype with explicit quality and resolution; measure CPU cost,
bytes/sec and decode time before selecting production defaults.
Keep saved 3D window queries independent initially. Present their samples from
the same displayed ordinal/time; do not couple Parquet validity to video playback.
Unifying saved numeric delivery into FrameMessage can follow after image playback
is proven, rather than expanding this task into the entire data-model refactor.

## Implementation checkpoints

1. Agree this boundary plan, especially dedicated connection, media identity and
   explicit display-encoding policy.
2. Adapt SkellyCam image input/packing without duplicating encoder code. Test
   live payload compatibility, arbitrary identities, rotation and exact ordinals.
   User commits/pushes; FreeMoCap consumes the Git dependency as usual.
3. Build a headless playback session using a fake consumer. Verify credit bounds,
   pause, seek generations, source changes, EOF mismatch, failure and disconnect.
4. Integrate the shared frontend decoder with existing cache/lookahead. Remove
   the production Mediabunny video-decoding path once replaced; no per-frame HTTP
   route or disk transcode fallback. Keep raw and annotated on one source adapter.
5. Real-app Windows checkpoint: MPEG-4 test data and H.264 recordings; arbitrary
   video counts; rapid seeks/source switches; long playback; simultaneous realtime
   and posthoc; cancellation. Measure memory, throughput and stalls. Then packaged
   Linux/macOS verification. No claim of smooth performance before those checks.

Deferred: sidebar status redesign, calibration reprojection-based matching,
remaining Mocap posthoc/API and recording data-model work.

## Checkpoint 1: shared image packing implemented

SkellyCam now exposes ImagePayloadFrame, ImagePayloadRequest and
encode_image_payload in frontend_payload_bytearray.py. Live camera records adapt
to this encoder; image-only callers supply oriented BGR arrays, explicit transport
slots, output dimensions and JPEG parameters. The existing binary layout is
unchanged. Transport IDs exceeding its ASCII slot fail instead of truncating;
full playback media identities still require the planned session mapping.

12 focused image/payload tests passed, covering wire layout, full-resolution
images, equal ordinals, unique slots, invalid IDs, rotation through live tests,
and independent payload lifetime. The broader 23-test module had one unrelated
filename assertion failure (expects idx0, builder emits idx-0); 22 passed.

This is the SkellyCam dependency handoff point. User commit/push and FreeMoCap
Git-dependency update precede integration. No installed packages or dependency
sources changed. Playback remains on its current implementation until session
and frontend work are completed; this checkpoint alone does not fix MPEG-4 playback.
