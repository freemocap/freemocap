---
mdx:
  format: md
plan_status: ongoing
plan_migrated: "2026-09-10"
---

# Browser video playback

## Decision and scope

### Active routes and callers

All paths below are under `/freemocap/playback`.

| Route | Current caller / purpose |
|---|---|
| `GET /{recording_id}/bundle` | `fetchPlaybackBundle`: recording metadata, video URLs, manifest and media bindings |
| `POST /{recording_id}/window` | `RecordingPlaybackProvider`: bounded 3D/skeleton data windows |
| `GET /{recording_id}/videos/{video_id}` | `BrowserVideo`: original file in a native video element, including HTTP range seeking |
| `GET /{recording_id}/videos/{video_id}/browser` | `BrowserVideo`: fragmented-MP4 HTTP compatibility stream consumed through MediaSource |

Standalone manifest/media routes also exist; the main recording-open flow obtains them through the
bundle. They are HTTP query interfaces, not playback socket remnants.

`app.py` registers only `/websocket/connect`, for application/realtime traffic. Playback components
do not create sockets. The application connection can trigger an HTTP bundle refresh after processing
finishes, but it does not deliver recorded video or recording data windows.

Use browser-native video presentation with approximate visual synchronization. Warn users
that views can differ by a few frames and that embossed frame numbers identify the displayed
frames. This concession applies to viewing only; processing retains its synchronized frame contract.

Original files must not be duplicated or converted to persistent playback files. Reuse PyAV
through SkellyCam for codec compatibility. No new dependency, editable installation, or dependency
source override is needed for the prototype.

## Prototype checkpoint — 2026-09-08

SkellyCam `skellycam/core/recorders/videos/browser_stream.py` supplies a pull-driven generator
of fragmented MP4 bytes using libx264. It reads the original file and encodes video only into a
non-seekable memory sink. Consumers advance encoding by requesting the next chunk; closing the
generator releases its input/output containers. No producer queue or background encoder is created.
The sink fails above 8 MiB; this bounds that sink, not all native codec allocations or network buffers.

The prototype uses at most 1280x720, two encoding threads per stream, quarter-second fragments,
and explicit start/duration requests. These are prototype settings, not a finalized resource policy.
It currently transcodes all inputs; direct file serving and lossless remux selection are not implemented.
Rotation metadata is rejected explicitly pending implementation. Audio is not included.

SkellyCam `skellycam/tests/browser_stream_server.py` is a loopback HTTP test harness, not an
application endpoint. FreeMoCap UI `e2e/browser-stream.spec.ts` launches that harness in SkellyCam's
own environment and plays the stream through Electron MediaSource and native video elements.
It uses the Git-installed application dependencies unchanged.

Validation on Windows:

- Six Python tests cover decodable fragments, frame content after seeking, rebased timestamps,
  early cancellation/restart, no output files, output-sink limit, and invalid start rejection.
- Electron passes on the numbered fixture, all three MPEG-4 Part 2 test-recording videos, and
  all four annotated calibration videos. Tests exercise concurrent playback and restarting streams
  at a different source time and back at the beginning. Playback begins as fragments become available.
- A conversion-only measurement encoded ten seconds from each of four annotated videos concurrently
  in 3.201 seconds, discarding output chunks in memory. This establishes throughput headroom on this
  machine, not sustained app display FPS or packaged-platform performance.
- UI TypeScript check passes.

## Next checkpoints

### App integration — 2026-09-08

FreeMoCap now imports the Git-installed SkellyCam browser stream. The playback controller uses
native video elements for raw and annotated alike. Native source/decode rejection selects the HTTP
compatibility stream. Converted media uses MediaSource with an eight-second ahead target and eviction
of content more than two seconds behind. It is a time-window policy, not a guaranteed process RSS limit.
Restarting outside that window cancels the previous fetch and starts at the requested recording time.
HTTP disconnect closes the encoder iterator. Preparation failures are returned before streaming headers.

The JPEG playback socket, range scheduler, bitmap lookahead and associated obsolete tests are removed.
Realtime sockets and processing readers are unchanged. The green timeline represents browser-buffered
video; there is no separately managed bitmap buffer. An explicit approximate-sync notice is visible.
Direct playback uses the original resolution; conversion currently uses the prototype's 1280x720 bounds.
Audio, rotated-source conversion, lossless remux selection, and platform packaging checks remain pending.

Validation: eleven HTTP/media/bundle tests pass. Electron tests using the actual controller pass for
both original-file playback and forced conversion, including play, seek, raw/annotated switching at the
selected time, and reload. TypeScript passes. Sustained real-app performance is the next user checkpoint.

App test: restart normally, open the MPEG-4 test recording, play and drag/step the timeline in both
directions; switch raw/annotated at a paused frame; switch recordings and refresh; verify zoom and the
3D timeline. Also test a longer recording through a full playback cycle and with realtime active.
Report pauses, incorrect source-switch times, conversion errors, or accumulating resource use.

Mount lifecycle: the controller waits for selected video elements to register before opening media.
Element replacement triggers disposal and reattachment; stable tile ref callbacks avoid reopening media
on ordinary renders. Electron coverage includes metadata available before tile mounting and tile
unmount/remount for both direct and converted playback. This addresses the reported missing-element crash.

1. Run the Windows app checkpoint above before further architecture changes.
2. Exercise long-recording backpressure, repeated cancellation, and concurrent realtime workloads.
   Establish global conversion resource admission without starving additional camera views.
3. Add remux capability selection and resolve rotated-source conversion and desired inspection resolution.
   Keep codec/media operations in SkellyCam and HTTP orchestration in FreeMoCap.
4. Validate Linux/macOS and packaged builds, including codec availability and bundled libraries.
5. Return to the media identity audit and Mocap posthoc architecture/data model work;
   camera geometry matching remains a separate deferred step.
