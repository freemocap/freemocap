# Playback streaming adaptation

Status: implemented; ready for Windows app testing with full-resolution recordings.
Scope: recorded video playback within the Mocap posthoc/data-model initiative.

## Ownership and data flow

The playback client owns scheduling and requested image encoding. It requests explicit half-open frame ranges
(start_frame inclusive, end_frame exclusive) through a dedicated WebSocket. The
backend fulfills precisely that range as quickly as native decoding and socket
transport permit, then sends a completion message and waits. Each payload contains
one synchronized multiframe: the same frame ordinal from every selected video.
There is no per-frame acknowledgment or fixed multiframe allowance.

Realtime remains a separate scheduling policy: live images prioritize freshness.
Playback never uses the live newest-frame queue. It receives requested frame ordinals
faithfully, but may skip their decoding/presentation to follow its playback clock.
It shares SkellyCam's sequential reader and image encoder, CBOR/SendSerializer,
and the frontend FrameProcessor worker with the established streaming machinery.

No video copies are written to disk, and playback does not download compressed
videos or make per-frame HTTP requests. Native reads advance sequentially; uncached
backward reads restart from zero. Equal frame counts are required, never equality
of measured floating-point FPS values. Recording timing drives presentation.

## Client workflow

- Opening a recording prefers viable annotated videos, with raw as the fallback.
- During playback, ranges request scale 0.5 and JPEG quality 60 (half width and
  height, matching realtime preview policy). The selected source requests upcoming missing ranges within its
  available decoded-image budget. The presentation clock remains independent of
  range delivery. The controller retains its canvas presentation/look-ahead layer.
- When paused, only the paused ordinal is requested from each available source,
  with scale 1.0 and JPEG quality 90. A cached preview is shown while the detail
  image loads; the canvas is not cleared. Resume selects preview encoding again.
  Both sources retain their compressed images and native decoder positions.
- Switching sources pauses playback and preserves the displayed ordinal. Cached
  multiframes can be reused without another range request.
- Seeking changes the client's priority interval and cancels irrelevant range work.
  The client waits for completion of cancellation before issuing the next range,
  so outstanding reservations cannot accumulate across rapid seeks.
- Closing a recording closes its sockets, decoder workers and image caches.

## Memory and observability

The persistent recording cache retains the compressed multiframe byte payload
(camera headers and JPEG images), indexed by source, encoding profile and frame ordinal. Preview and detail profiles
map to fixed, distinct scale/quality settings; they never share cache entries. Receiving
and storing a payload does not decode it. Cache accounting uses actual byte length.
The client reserves the enforced maximum wire payload size for each outstanding
multiframe before requesting a range; actual compressed sizes free space for more
requests when that range completes. Small recordings can remain entirely cached.

RecordingVideoCache allocates three quarters of the selected recording budget to
JPEG payloads across available sources. The presentation look-ahead uses up to a
quarter (capped at 256 MiB), including headroom for the displayed frame and decode work.
The target is one second of prepared images, reduced when the byte limit requires it. Bitmap
ownership belongs to the presentation buffer: frames are decoded on demand,
drawn, and released. The main cache never retains bitmaps or expanded pixel arrays.
The retained payload is copied before transferring to the shared decoder worker,
so decoding does not detach the cached bytes. Paused-source warming fetches JPEGs
without decoding inactive views. Browser/GPU overhead is not a strict memory cap.

Two canvas strips show different residency information on the slider:
- Thin green: ordinals with compressed JPEG payloads retained for the selected source
  (preview or detail).
- Thicker pink: decoded presentation look-ahead plus the currently displayed frame.

They update every 250 ms independently of the presentation loop, use theme colors,
and do not count requested/in-flight frames as resident. Hover text explains both.

## Implementation boundaries

- core/playback/media_selection.py: shared source-folder and full-filename discovery.
- core/playback/video_source.py: managed native reader thread and shared image packing.
- core/playback/stream_session.py: exact range execution, cancellation and completion.
- api/websocket/playback_socket.py: typed wire requests, source opening and scoped cleanup.
- freemocap-ui/src/services/recording/client-video-group.ts: client range scheduling,
  outstanding wire-byte reservations and compressed-multiframe cache ownership.
- freemocap-ui/src/services/recording/recording-video-cache.ts: recording-wide source ownership.
- freemocap-ui/src/components/playback/usePlaybackController.ts: playback state,
  paused-source warming, frame presentation and preserved media timelines when
  selecting a reconstruction run.
- freemocap-ui/src/components/playback/CachedTimeline.tsx: cache residency rendering.

## Camera rendering ownership

Playback and realtime use `offscreen-renderer.worker.ts` for bitmap creation and
`bitmaprenderer` presentation on worker-owned canvases. Realtime uses its latest-image
policy. Playback uses typed prepare/present/release commands through
`scheduled-renderer.ts`; its bounded look-ahead holds image handles, while the bitmaps
remain inside the camera workers. Preparation runs concurrently across cameras.

The controller submits a presentation only after every camera image is prepared,
and waits for every worker to acknowledge presentation before advancing the ordinal.
This is a logical multiframe barrier, not a guarantee of atomic hardware scanout across
separate canvases. Frame labels and timeline overlays remain small canvas operations
on the main thread. JPEG decoding uses Electron's native JPEG decoder inside the shared decoder worker,
with a CPU-readable OffscreenCanvas producing transferable RGBA output. Both realtime
and playback use this path. Buffer refill starts when a presentation slot is consumed,
so decoding overlaps the rendering acknowledgments.

Canvas workers survive React ref detach/reattach within a commit and terminate when
their canvas leaves the view. Closing look-ahead releases unpresented image handles;
renderer errors reject outstanding operations and surface in playback.

## Validation and app check

Seven Python tests pass: exact requested ranges without acknowledgments, cancellation
of an in-flight multiframe, failure cleanup, bounds/payload validation, annotated
preference, full-filename discovery and native socket seeking/disconnect cleanup.

Frontend coverage includes an Electron worker JPEG benchmark and malformed-image rejection. The Electron integration test uses the real controller,
native backend and shared image decoder; it verifies rendered ordinal pixels,
slider clicks/drags, reconstruction-run selection with raw-only saved timing,
annotated switching, paused source warming, reload, recording switches and React
StrictMode cleanup. It verifies image canvases are worker-owned and renderer failures
reject pending presentation without stopping independent canvases. It checks cached switches do not receive additional images,
playback does not request video HTTP resources, and client-selected batches can
span more than four multiframes. JPEG-cache coverage exceeds the small decoded
presentation buffer, and the two indicators use distinct theme colors. Tests cover presentation-buffer ownership, dropping queued images while preserving consecutive decode requests, in-flight completion, wall-clock speed, and actual presentation-rate measurement.

Renderer and harness TypeScript checks pass. The renderer/worker build passes with
existing asset/CSS/chunk warnings. The broader pytest module remains unavailable
because pytest is absent from the installed environment; no environment changes
were made to bypass that dependency boundary.

App test: restart frontend and backend together; open annotated test data, play,
pause and compare Raw/Annotated, drag forward/backward, switch recordings, and
reload. Repeat using full-resolution recordings and concurrent realtime capture.
Watch whether the green cached region stays ahead of the playback marker.

## Remaining work

- Measure arrival waits, JPEG decode, worker bitmap preparation, presentation latency,
  buffer starvation, memory overhead and large-recording seek latency on real footage.
- Playback performance is parked after the buffer-starvation recovery checkpoint.
  Catch-up drops only already-prepared multiframes. Decoding remains sequential;
  recovery rebases presentation time to the next available frame. Sustained input
  shortages may slow playback rather than accumulating catch-up work.
- Native cancellation currently waits for the active sequential read to finish.
  Interruptible long reads belong in SkellyCam and require the normal Git dependency
  handoff. Socket cancellation prevents subsequent payload delivery and range work.
- Linux/macOS validation and user-configurable memory/quality settings follow Windows QA.
- Resume media/camera identity work, including the planned calibration-reprojection
  fitness matching design, within the larger Mocap posthoc/data-model refactor.

Preview/detail validation additionally checks native wire dimensions and Electron
canvas dimensions: preview images halve both dimensions during playback, then full
resolution is restored at pause without changing the displayed frame ordinal.
Scaling uses the existing SkellyCam image encoder; no installed dependency changes
or changes to realtime encoding policy are required.

## Focused throughput checkpoint

The Electron worker benchmark uses deterministic synthetic JPEGs at quality 60,
20 iterations per size after warmup. The production native decoder (including Blob
creation and RGBA readback) measured approximately 2.4 / 5.4 / 8.3 ms at 640x360 /
960x540 / 1280x720. The JavaScript comparison measured 15 / 34 / 60 ms. These isolate
JPEG decoding; they do not establish end-to-end throughput with real footage or a
busy 3D viewport. Run `playwright test e2e/jpeg-throughput.spec.ts --reporter=line`
from freemocap-ui to repeat the comparison. The JavaScript library is only used by
the benchmark, not the application's image path.

App checkpoint: restart the frontend and replay the same recording at 1x, then
check paused detail, source switching, and realtime rendering. If playback remains
unsatisfactory, record that result and park further playback performance work;
resume the media/camera identity and Mocap posthoc architecture/data-model work.
Wall-clock presentation skipping is implemented. After initial buffering, elapsed
wall time and the selected playback speed determine the due frame. The controller
presents the newest ready multiframe at or before that position and releases obsolete
prepared images. Decoding always requests consecutive ordinals. After an empty-buffer
stall, presentation time resumes from the next available image without resetting the
display-FPS measurement. Final-frame presentation remains exact.

The slider displays actual completed multiframe presentations per second over a
rolling one-second window. It starts unspecified, resets when playback starts, and
retains its last measurement when paused. An isolated UI counter samples four times
per second; no per-frame React updates are added for telemetry. This measures worker
presentation acknowledgments, not physical monitor scanout. Skipping preserves
motion speed rather than inflating the measured display FPS.

The Electron playback test also injects 100 ms bitmap preparation and checks that
presentation continues above four FPS after the initial buffer drains, with both
camera canvases reaching the exact final ordinal. The initial unspecified FPS readout and subsequent measured value are checked.

Next work after the brief app check: resume media/camera identity within the Mocap
posthoc architecture and recording-data-model work. Keep calibration reprojection
fitness matching on that roadmap; further playback tuning is deferred.

Starvation regression checkpoint: playback scheduling uses a bounded timer rather
than depending on animation-frame callbacks. The slow-preparation Electron case
presented 48 camera sets and reported 9 FPS with a deliberate 100 ms preparation
cost. This is a controlled regression result, not a real-recording throughput claim.
Sequential decode, prepared-only dropping, and clock rebasing form the functional
fallback; sustained insufficient throughput may slow recording time. Further
performance tuning is deferred after the app smoke check.

## Resource and zoom checkpoint

Electron chooses a recording-cache budget no greater than 2 GiB, one sixteenth of
physical RAM, or one quarter of available RAM at initialization, whichever is smaller.
Insufficient memory and invalid OS readings fail explicitly. Browser-only playback
retains its conservative 512 MiB default. These are allocation budgets with OS
headroom, not guarantees against subsequent memory pressure or GPU/native overhead.

Playback zoom uses the fixed outer viewport for cursor coordinates, with transforms
applied only to its inner image wrapper, matching realtime's shared zoom hook.
Electron checks repeated cursor-anchored zoom in/out, zoom after panning, and reset
on the actual playback tile. Further playback work remains deferred after this check.
