---
mdx:
  format: md
plan_status: archived
plan_migrated: "2026-09-10"
---

# Historical client playback design notes

These checkpoint notes describe earlier experiments and are not the current playback specification.
The authoritative implementation summary is [browser video playback](../03-transport/browser-video-playback.md).
Current playback uses HTTP endpoints, native video elements and an HTTP codec-compatibility stream.
There is no playback WebSocket, JPEG range scheduler, or client bitmap lookahead cache.

## Current mocap contract — synchronized video groups

A group contains any positive number of videos with exactly equal decoded frame counts.
Synchronization is an upstream prerequisite. Frame N in every video is assumed to describe
the same instant. Unequal frame counts fail group loading; per-file FPS estimates are never compared.
No trimming, nearest-time selection,
independent camera playback, or per-video drift correction is permitted. One requested ordinal is
presented only after every video supplies that ordinal. Mixed-rate sensor work is outside this pass.

Checkpoint 4 implements this contract in the standalone prototype. Opening scans decoded outputs
to validate frame counts and derives FPS from their presentation span. This is deliberately costly
prototype validation, not the final fast metadata path. One/two/five input regression tests exercise
all panes; group validation tests require nonempty input and equal frame counts.
The validator takes frame counts only. One selected rate estimate paces the
entire group; it does not determine frame correspondence. The image-cache estimate is shared
across the group. Native decoder and compositor overhead are additional resource costs.

## Checkpoint 1 — discovery and visual stability

Implemented: remove per-frame decoding text; detach recording-list refresh from translation function
identity; guard concurrent FFmpeg detection at dispatch and stop automatic retries after failure.
TypeScript checking passes. Client decoding and request batching beyond these guards are not yet
implemented; per-frame JPEG requests still exist until the decoder checkpoint.

App test: reopen Playback, play and scrub raw/annotated media, and confirm the decoding text and its
layout jump are gone. Filter/sort the recording list and verify these actions do not reload the list.
Navigate away and back: a fresh list request is expected. Explicit refresh must still work. Inspect
the Network panel for concurrent FFmpeg detection duplicates. Report any sustained list-request loop.
After this check-in, proceed to a client decoder prototype with frame-identity tests and runtime codec
validation before integrating it into normal playback.

## Findings

### Checkpoint 6 — normal Playback integration

Normal Playback uses URL-backed decode workers, sequential ordinal reads, client image caching,
and a bounded half-second lookahead target. Every pane presents the same ordinal together. A
starved group holds its current images. Ordinary playback makes no per-frame JPEG requests;
HTTP byte-range reads supply compressed media to bounded client caches. The API exposes range
response headers for the browser reader. The blanket timing-drift warning is removed.

Validation: the actual React controller passes an Electron integration test covering HTTP media,
forward/backward reads, playback completion, and source replacement. It checks shared ordinals,
absence of frame HTTP requests, and reuse of downloaded fixture bytes. Application and harness
TypeScript checks pass; the isolated production renderer and worker build passes. The frame-count
validator test passes. Real-recording sustained performance still requires app acceptance.

User test: restart backend and frontend normally, open Playback, select a synchronized recording,
play/pause, seek forward and backward, resume, and switch raw/annotated sources where available.
Check that panes stay together and the layout remains stable. Opening currently scans all decoded
frames to validate exact counts, so startup can be slow. Buffer capacity depends on image size and
video count; this checkpoint does not guarantee real-time throughput. Unsupported codecs fail
explicitly. Audio synchronization and broader stress/codec/platform tests remain follow-up work.

After this acceptance checkpoint, return to media identity/camera matching. Sidebar status and
contents redesign remains deferred; broader request coalescing remains a separate follow-up.

### Checkpoint 5 — buffered group presentation

Validation: all six tests pass in Windows Electron: 1/2/5-video exact access and buffered
pause/resume/completion, mismatched group rejection, bounded refill, and closing during an in-flight
decode. Both application and prototype TypeScript checks pass. Real-recording smoothness and
sustained decode throughput still require the user's prototype run; no performance claim is implied
by the small synthetic fixture.

The standalone prototype includes Play buffered and Pause. It preloads roughly half a second,
replenishes a bounded queue while presenting, and advances one shared ordinal at the common FPS.
The presentation queue has a 256 MiB RGBA estimate cap, reserving space for a displayed group and
one load in flight; the existing worker caches retain a separate shared 32 MiB estimate. Decoder,
canvas, compositor and compressed-data overhead are additional. Large groups receive a shorter
lookahead; groups unable to fit the minimum buffer fail explicitly instead of dropping videos.

Only complete frame groups are displayed. A shortage holds the current group and rebases the
clock on recovery. Pause stops presentation and drains outstanding work before enabling manual
reads. File replacement invalidates outstanding work and releases transferred images. The shared
timer is independent of animation-frame delivery, including in the hidden Electron test window.
Canvas dimensions are retained during playback instead of resetting the drawing surface each frame.

Test with `npm run prototype:media`: select synchronized files, click Play buffered, pause, read a
different ordinal and play again. Expect one preload interval, stable layout, and synchronized panes.
Report sustained buffering separately from brief startup delay. This remains a prototype; main
Playback and its HTTP transport are not changed by this checkpoint.

### Checkpoint 3 — MP4 worker in Electron

Mediabunny is pinned to 1.55.7 in package.json/package-lock.json through npm. Its installed package
adds two type packages; no native codec addon or Python dependency/source was changed.

`media-decoder.worker.ts` opens File/Blob media using Mediabunny, iterates samples from the start,
and keeps a per-file 32 MiB estimated image cache. Cache hits preserve decoder position; uncached
backward reads restart the sequential iterator. Responses transfer a separate ImageBitmap, and
consumers close it after drawing. Errors release decoder resources and require reopening the file.
The standalone prototype permits one outstanding frame request; production cancellation, shared
clock, decode-ahead and multi-camera memory budgeting remain to be implemented.

Windows validation: installed Electron passed the portable H.264 fixture with 48 frames, including
28 B-frames, using ordinal-encoded image content and a sequential PyAV reference. Tested reads:
0, 30, 29, 30, 0, 47, including cache hits and eviction/restart. The same checks passed against
camera 2ea4 in the reported calibration recording using temporary PyAV pixel references. This checks
selected ordinals, not every frame or every possible container edit. App and prototype TypeScript
checks pass. Packaged installer and multi-camera performance testing are still pending.

From `freemocap-ui`:

```sh
npm run test:media
npm run prototype:media
```

The second command opens a separate Electron window, with no backend required. Choose a raw or
annotated video, then read frames 0, 30, 29, 30, 0, 47 (for videos with at least 48 frames).
Check that repeated frame numbers show the same image; `cacheHit` should be true for recent frames.
For larger frames, reading frame 0 after frame 30 should increment `restarts` if it was evicted.
The statistics and explicit read-status text are prototype diagnostics, not the production playback
UX. Close the window to stop the isolated server. Original videos are read-only.

The same npm test/launch commands are intended for Linux/macOS after normal npm installation.
Report codec errors and test output; do not treat Windows or Edge success as cross-platform proof.
The included fixture has its typed Python generator and sequential reference beside it, so running
the tests does not require Python or fixture regeneration. Unsupported codecs produce an explicit
error; this checkpoint does not introduce proxies or per-frame HTTP fallbacks.

Next: validate this checkpoint with the user, then add worker cancellation/backpressure, bounded
decode-ahead, a shared recording clock and four-camera tests before replacing app playback.

### Checkpoint 2 — isolated browser experiment

Implemented `decoder-prototype.ts` and a per-media `decoded-frame-cache.ts` in UI recording services.
The experiment encodes 24 synthetic VP8 frames, decodes sequentially, checks image content and output
timestamps, exercises reverse cache hits and eviction, then repeats decoding from the beginning.
The cache owns ImageBitmap resources and closes evicted images; its RGBA estimate excludes runtime
overhead. This small experiment is deliberately not a production streaming decoder.

Validation: TypeScript passes; `e2e/decoder-prototype.spec.ts` passes in installed headless Edge.
Reproduce from `freemocap-ui` with `node node_modules/@playwright/test/cli.js test
e2e/decoder-prototype.spec.ts --reporter=line` (one command). No app interaction or recording is needed.
No dependencies were installed. This does not establish packaged Electron codec support, MP4/B-frame
correctness, worker backpressure, sustained multi-camera performance or global cache fairness.

Next gate: select and integrate a demuxer through the agreed dependency workflow, test actual captured
codecs and B-frame fixtures against sequential reference decoding, and move the decoder into a worker.
Mediabunny and MP4Box.js were reviewed as candidates at checkpoint 2. Prefer evaluating
Mediabunny's sequential sample iterator for broader container coverage; do not use timestamp-seeking
sample APIs as a substitute for exact ordinal traversal. Cache hits must not advance or reset the
decoder. Player integration and removal of per-frame HTTP remain pending those tests.

Sources: [Mediabunny media sinks](https://mediabunny.dev/guide/media-sinks),
[MP4Box.js](https://github.com/gpac/mp4box.js/blob/main/README.md).

- `usePlaybackController.ts` fetches one JPEG per camera per presented frame. SkellyCam's
  `SequentialVideoReaders` caches JPEGs on the server; a cache hit still requires HTTP and browser
  image decoding. Its shared lock also serializes those reads. Preserve sequential decoding for
  processing, but remove this transport from normal client playback.
- `PlaybackPage.tsx` renders “Decoding requested frames…” on `isSeeking`, introducing per-frame
  status/layout changes. Remove this presentation mechanism in the replacement.
- Directory loading already uses one `/playback/recordings` list response containing statuses.
  Expanding a row invokes `useRecordingStatus` separately. Reuse supplied detail rather than
  assuming every row needs another request; fetch only genuinely absent or invalidated detail.
- Status lookup currently uses recording name without its parent directory. Cache keys must include
  recording location to prevent two equally named recordings sharing status.
- The list refresh effect depends on a callback containing the translation function. The log shows
  repeated list requests; instrument mount/effect/invalidation causes before assigning a cause.
  Redux thunks need request coalescing, not just component-level checks.
- The log also shows repeated FFmpeg capability requests. Audit the shared capability hook/thunk
  and all mounted consumers; capability discovery should be shared per backend session.
- Selecting a recording has separate videos, manifest/media and bundle consumers. Replace redundant
  metadata fetches with one shared playback description; numerical windows remain separately buffered.
- Current UI dependencies declare Electron 35 and no obvious demuxing library. Runtime codec support
  and a demuxer are implementation prerequisites, not capabilities established by this audit.

## Correctness contract

An exact video-frame ordinal, a media presentation timestamp, and a recording capture timestamp
are different values. Preserve their explicit mapping. Never compute exact frame identity by
rounding timestamp times nominal FPS. Inferred capture timing remains a supported, labeled option.

Sequential decoding from the beginning establishes the baseline sequence of displayable frames.
Advance by decoded output frames, not compressed packets: reordering codecs have different decode
and presentation order. Variable frame rates, container edits, preroll and timestamp rounding must
not silently shift the ordinal-to-recording mapping. Validate imported formats against this baseline.

Backward access is not inherently nondeterministic. A cached exact frame is exact; a verified codec
random-access point followed by sequential decoding can also be exact. Initial implementation uses
start-of-stream decoding for uncached backward access. Indexed restart is a later optimization,
accepted only when it reproduces the baseline sequence, including B-frame/open-GOP cases. A generic
timestamp seek or an arbitrary I-frame is not sufficient proof. Do not flush/reset on every frame.

Exact frame selection cannot repair incorrect acquisition synchronization. Mocap input synchronization
is assumed; select the same ordinal in every source. Do not infer a different per-camera frame from
capture timestamps. Retain timestamps as metadata and for association with recorded numerical data.

## Proposed client architecture

1. A shared recording-description query resolves media, source bindings, timelines, available results
   and revision. Absence of reconstruction is a normal capability, not a failed discovery request.
2. A compressed-byte reader buffers progressive/range reads from the backend. Reuse byte ranges;
   coalesce requests and cancel stale work. Do not download every recording in full by default.
3. Worker-based demuxing supplies codec configuration, encoded samples in decode order and their
   presentation information. WebCodecs is the preferred decoder candidate, subject to a runtime
   compatibility spike; codec/container support must be explicit.
4. A sequential decoder records exact output ordinals and maintains bounded lookahead. A global
   client memory budget covers all cameras, both compressed buffers and decoded caches. Retain a
   protected playhead window plus an LRU region for recently visited frames. Cache identity includes
   media revision, track, ordinal and relevant transform. Never hold decoder resources indefinitely;
   benchmark direct VideoFrame retention versus independently owned image resources for the cache.
5. A single group clock advances the shared ordinal at the common FPS. Present a complete set together;
   if required frames are missing, hold the last complete set and pause/rebase the playback clock.
   Decode workers may run independently; presentation must not drift independently per camera.
6. Scrubbing returns cached frames immediately, otherwise queues a cancellable sequential decode.
   Generation tokens prevent obsolete jobs from repainting the new recording or seek target.
7. React handles controls and coarse state. Frame presentation runs outside per-frame React state
   updates. A sustained buffering indicator uses reserved overlay space; ordinary playback has no
   decoding text, status flicker, or layout movement. Audio, when present, follows the same clock and
   pauses during a coordinated stall; audio scheduling must be included in the prototype scope.

Unsupported native decoding requires a reviewed compatibility path, such as a one-time playback
proxy with a verified frame map. Do not silently resample, drop frames, or fall back to per-frame
server JPEG requests. Retain original media and communicate actual unsupported/corrupt-input errors.
Choose the compatibility approach after inspecting real capture codecs and packaged runtime support.

## Sidebar and request budget

The sidebar status/content dropdown redesign is deferred until the posthoc pipeline and recording
data model are settled. Limit current changes to request behavior and playback stability; do not
redesign the status taxonomy, contents tree or their presentation in this pass.

Audit correction: the recording-list reducer already seeds the per-recording status cache, so
expanding a row with batch-provided status does not inherently issue a second request. Preserve
that behavior. Location-aware cache keys remain a separate follow-up.

- One list request per recording root on initial access; deduplicate concurrent consumers. Cache list
  and row details together. For large directories, paginate summaries and batch missing details.
- Invalidate on capture completion, import, processing/export changes, explicit refresh, or a deliberate
  focus freshness check. Coalesce repeated events. Do not refetch due to translation/rerender changes.
- Share one recording-open metadata request between sidebar, player and 3D view. Partition large
  numerical/timing payloads into buffered windows if needed, not individual frame requests.
- Capability checks run once per backend session unless explicitly invalidated/retried.
- Normal play and seeks inside decoded caches: zero frame HTTP requests. Byte-range and numerical
  prefetch requests follow buffered demand, never the display refresh rate.
- Instrument counts, bytes, cache hits, decode latency and stalls. Verify frontend batching also avoids
  repeated backend probing of every file. Do not move an N-request loop into an equally wasteful scan.

## Validation and implementation gates

First capture browser errors and request traces for the reported recording. Then build a small
client decoder prototype before replacing the controller. No unverified smoothness guarantee.

Use videos with encoded visible frame ordinals, including B-frames, long GOPs and rotation.
Reject mismatched counts; synchronization has already occurred. Compare sequential playback, forward
seeks, cached reverse seeks and uncached restarts to the reference decoded sequence. Compare frame
identity rather than demanding bit-identical GPU/CPU color conversion. Test rapid scrubbing, stale
callbacks, memory eviction, corrupt media and one deliberately slow decoder. Verify all panes and
numerical overlays refer to the same selected recording time after stalls.

Measure sustained playback at several group sizes and memory after repeated seek cycles. Monitor
refresh need not display every source sample, but exact stepping must access every shared ordinal.
Do not skip compressed dependencies to catch up. No code path assumes four inputs.

Replace the generic drift warning only after these checks pass. Show specific timing provenance or
unresolved alignment where applicable; exact playback does not certify acquisition synchronization.
Audit the existing `syncInfoBody` translation and its callers rather than just changing its wording.

Implementation order: request inventory/coalescing and stable UI; client decode prototype and codec
decision; integrated frame cache/clock; app acceptance; then media identity and calibration matching.
The playback description must use explicit media references so identity cleanup can reuse it.

## Technical references

[W3C WebCodecs](https://www.w3.org/TR/webcodecs/) specifies presentation-ordered video outputs,
key-chunk requirements after configuration, configuration support checks, and explicit frame-resource
release. It does not guarantee support for every codec. These requirements inform the prototype;
they do not establish that a demuxer, frame index or synchronization mapping is correct.

### App QA follow-up: seeking and label ownership

User confirmed smooth real-recording playback. Timeline controls retain requested position through
pointer release; frame steps accumulate against the requested ordinal. Frame/time labels use
fixed-size canvases with one renderer. The Electron harness exercises the actual timeline control
and checks decoded image ordinals. Media-only recordings return a null manifest normally.

Remaining: startup/reload flashing, request coalescing across sidebar/bundle/media discovery, and
bundle validation invoking VideoGroupHelper's filename camera-ID parser for annotated videos.
Resolve that coupling in media identity cleanup without adding another filename parser. Measure
expected video byte-range requests separately from duplicate metadata requests.

### Playback transport cleanup

The server JPEG frame route and its playback reader cache are removed, along with the unused
client timestamp-to-video-frame lookup. Both video sources use ClientVideoGroup and the same
worker, ordinal cache, lookahead, and presentation loop; source selection changes file URLs only.
Electron verifies play and seek after switching to annotated media. Direct FastAPI checks verify
byte-range serving for both sources and absence of the frame route. TypeScript passes. Pytest is
not installed in the current environment; no dependency changes were made. The reported real
annotated-video problem remains unconfirmed: no frontend server-frame fallback was found.

### Overlay cleanup and deferred work

Combined green frame/time label occupies the upper-right. Static filename stays bottom-left,
constrained with ellipsis and full text on hover. PlaybackLabel retains its drawing context;
formatting occurs once per synchronized frame group. Static filenames remain React-owned.
TypeScript passes. No global overlay manager is introduced.

Deferred: review shared image-annotation drawing for realtime/playback/export independently of
viewport labels. Audit streaming's retained prior observation and latest-frame scheduling before
reusing any lifecycle code for exact-frame playback. Also review paused visibility/format changes,
high-DPI label rendering, and coarse React timeline updates. Resume media identity work now;
startup discovery duplication and real annotated-file failures belong to that investigation.

### Recording-open request consolidation proposal

The 15:16 user log contains one bundle, one manifest, one media request, four recording-list
requests, and repeated 206 video-byte requests. Extend the existing bundle to include playback
manifest/media bindings and share it across consumers. Deduplicate recording-list/open requests
and explicitly invalidate on recording changes. Do not merely hide repeated backend probes behind
one endpoint. Video byte transport is a separate concern: measure ranges, transferred bytes and
cache hits before choosing larger reads or a persistent bounded encoded-media cache. Source
switching currently destroys decoder caches and opening scans all decoded frames; both contribute
to repeated I/O. GraphQL is not needed for this bounded recording-open contract.

Source switching preserves the requested ordinal and pauses presentation while opening the selected
files. Selecting a different recording still resets the timeline. Retaining both source caches
under one shared memory budget remains follow-up work.

### Recording-open metadata integration

RecordingBundle now includes manifest and media bindings. PlaybackPage consumes the location-keyed
Redux bundle shared with PlaybackContext; the controller makes no metadata HTTP requests. Source
switching retains the frame and reuses these bindings. AppContent owns initial recording-list load;
RecordingBrowser does not refetch on mount. Concurrent list dispatches are guarded; explicit refresh
and import refresh remain. Backend validation against the user's calibration recording returns all
eight raw/annotated bindings. Application and harness TypeScript checks pass.

Backend probing is not yet consolidated: the bundle composes existing discovery and media loaders.
The SkellyCam identity-free metadata contract remains the next step for removing repeated probes.
Compressed-video range reads, whole-video validation and source-cache retention remain separate.

### Recording-owned source caches

RecordingVideoCache retains lazily opened source groups across raw/annotated switches. Worker
cache allocations total at most 32 MiB decoded images and 64 MiB compressed bytes across the
recording media inventory; allocations are fixed per video, not a dynamic shared LRU. The active
presentation queue retains its separate 256 MiB estimate cap. Native codec/compositor overhead
is additional. Inactive groups do not prefetch; pending work drains on source change. Recording
replacement, bundle refresh and unmount close all groups. First-time source opening still scans
frames, and eviction may require more video-byte reads. No promise of zero requests for arbitrary
recording sizes or uncached ordinals is implied.

Electron acceptance checks repeated source switching at frame 47 and asserts no added video HTTP
reads after both fixture sources are cached. Application/harness TypeScript checks pass. Next user
check: seek within a real recording, switch to annotated and back repeatedly, confirm the frame
stays fixed and the second switch avoids full reopening. Backend probe migration and recording-list
refresh investigation remain separate work.

### Memory-aware playback budget

Electron exposes total/available memory through a lightweight memoryInfo IPC query. Playback
selects 1 GiB with at least 16 GiB total and 4 GiB available; otherwise 512 MiB. Browser-only
playback uses 512 MiB. Half is allocated to compressed bytes, one quarter to decoded caches,
and one quarter to active lookahead, shared across the recording inventory. Native decoder/GPU
and other application allocations remain outside these cache estimates. Limits do not reserve
memory up front. First loads and evicted data still require I/O.

Future Settings work: expose higher user-configurable budgets and allocation diagnostics; retain
bounded eviction and exact frame semantics for recordings larger than RAM. This supersedes the
fixed 32/64/256 MiB allocations documented in earlier checkpoints. Restart Electron to load the
memoryInfo IPC route before testing this checkpoint.

### Alternate-source byte prefetch checkpoint

Files fitting their per-video compressed allocation use one complete download and retained File
storage. In-flight downloads are shared between prefetch and active loading; workers decode from
BlobSource. Paused, ready playback prefetches alternate files sequentially without decoding images.
Starting playback stops scheduling further prefetch work; an in-flight download may finish.
Recording cache disposal aborts downloads and releases retained files. Content length and actual
size must match the bundle inventory. Larger files retain bounded UrlSource range reading; this
checkpoint does not eliminate their range requests. All frame selection remains sequential.

First switching can still incur the exact-count scan and sequential decode. Real-app acceptance:
allow idle prefetch, switch Raw/Annotated at a fixed frame, confirm repeat switches cause no
redownload for files that fit; verify active playback stays smooth. Large-file range optimization,
background decode scheduling and dynamic allocation remain deferred. After acceptance, return to
SkellyCam probe integration and media/camera identity; do not treat playback polish as prerequisite
for every subsequent architecture cleanup.

### User acceptance and deferred Charuco annotation issue

User accepts playback for this checkpoint; resume media/camera identity work. Annotated videos
show blue "undetected corners" text that appears inconsistent with visible board detections and
the selected 5x3 board (reported list roughly 0–25). This is an unverified observation, not a
confirmed detector failure. Later trace annotation inputs, board definition/ID domain, and
frame association; compare saved detections with the rendered missing-ID list. Do not infer a
correct corner count from "5x3" until its square/corner convention is established. No annotation
or calibration behavior changed in this checkpoint.
