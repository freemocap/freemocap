# Browser video playback

## Decision and scope

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

1. Preserve this prototype as a decision checkpoint before changing the app. User commits/pushes
   SkellyCam and updates FreeMoCap's Git dependency before integration imports its new module.
2. Implement explicit media capability selection: original file when supported, remux where sufficient,
   transcode otherwise. Keep codec/media operations in SkellyCam and HTTP orchestration in FreeMoCap.
3. Add production cancellation, request admission/resource limits, pre-header validation, mid-stream
   failure reporting, and bounded client ahead/behind buffers. Long-recording backpressure and repeated
   cancellation need integration tests; the short harness is not evidence for these properties.
4. Wire one client playback controller for raw and annotated, preserving recording time on switch,
   annotated-first selection, zoom, and 3D timeline. Translate source time to rebased media time when
   restarting outside buffered content. Keep per-frame presentation out of React state updates.
5. Validate sustained playback and seeking in the real Windows app, including realtime running
   simultaneously, then Linux/macOS and packaged builds. Verify codec availability and bundled libraries.
6. Remove superseded JPEG playback transport/cache/render paths once the replacement passes that
   checkpoint. Realtime streaming is independent. Return to the media identity audit and Mocap posthoc
   architecture/data model work; camera geometry matching remains a separate deferred step.
