# Client playback design

Status: proposal for review, 2026-09-06. Precedes media identity cleanup and posthoc refactoring.
No decoder replacement or dependency installation is authorized by this document alone.

## Findings

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

Exact frame selection cannot repair cameras that captured at different times, unknown offsets,
dropped frames, or clock drift. Align sources using recording timestamps and a documented selection
policy. The initial policy should preserve the existing latest-sample-at-or-before-time convention,
with explicit no-sample intervals outside coverage; equal frame numbers are not required across rates.

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
5. A single recording clock selects frames from all sources. Present a complete set together;
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

Use videos with encoded visible frame ordinals and known offsets, including B-frames, variable rate,
long GOPs, different camera rates, rotation and trimmed media. Compare sequential playback, forward
seeks, cached reverse seeks and uncached restarts to the reference decoded sequence. Compare frame
identity rather than demanding bit-identical GPU/CPU color conversion. Test rapid scrubbing, stale
callbacks, memory eviction, corrupt media and one deliberately slow decoder. Verify all panes and
numerical overlays refer to the same selected recording time after stalls.

Measure real four-camera sustained playback and memory after repeated seek cycles. A 30/120 FPS
fixture must preserve independent timelines; monitor refresh need not display every 120 FPS sample,
but exact stepping must access every sample. Do not skip compressed dependencies to catch up.

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
