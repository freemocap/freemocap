---
mdx:
  format: md
plan_status: ongoing
plan_migrated: "2026-09-10"
---

# Recording access during processing

Status: recording ownership implemented for calibration/mocap and playback. Logical-run annotation naming remains a follow-up; published video filenames have not changed.

## Implementation status

- The application constructs one `RecordingAccess`, shared by playback requests and the posthoc manager.
- The existing collector starts deferred tasks after reader leases close. Ownership survives failed worker teardown.
- `RecordingPlaybackRoute` holds leases through response execution and explicitly closes streaming generators during cancellation.
- Task snapshots include recording owners. `PlaybackPage` mounts/unmounts one `RecordingPlaybackSession`; invalidated bundle requests cannot restore stale cached data.
- Recording-content requests and absolute-path Parquet downloads return HTTP 409 while owned. Listing skips probing busy recording contents.
- Windows tests cover replacement after native-range and streaming-generator cleanup. Client tests cover session teardown/remount and stale bundle rejection.

The broader Electron playback regression reaches ready native and converted video playback, then fails because a tooltip intercepts the prototype seek button. Its remaining assertions are not verified by that run.

Remaining: logical-run naming/media association, persistent availability of partially published failed runs, and integrating other writers such as synchronization. The ownership change does not make publication across multiple camera files transactional.

## Behavior

Processing owns its recording directory exclusively. Playback of that recording stops while processing prepares, runs, and closes its files. Other recordings remain available. The server enforces ownership even when the client is disconnected or stale.

Annotated output identity includes the logical run ID. Repeating that run replaces the same output. Playback does not create copies or retain a separate history of video versions. Temporary files remain a write-and-replace implementation detail.

## Existing machinery to reuse

Paths below are relative to the `freemocap/` repository.

| Existing file | What it owns today |
| --- | --- |
| `freemocap/app/freemocap_application.py` | Application lifetime and construction of processing managers. |
| `freemocap/core/pipeline/posthoc/posthoc_pipeline_manager.py` | Calibration and mocap creation, cancellation, and worker cleanup. Both application entry points converge here. |
| `freemocap/api/http/playback/playback_router.py` | Bundle, metadata, numeric windows, native video ranges, browser codec streams, and Parquet downloads. |
| `freemocap/core/pipeline/posthoc/annotation_output.py` | Shared annotation writer used by calibration video nodes and mocap video nodes; temporary publication and reader cleanup. |
| `freemocap/system/recording_structure/recording_structure.py` | Canonical recording layout using `Path`; read-only conversion from `RecordingInfo`. |
| `freemocap-ui/src/pages/PlaybackPage.tsx` | Common composition point for video playback and the recording's 3D provider. |
| `freemocap-ui/src/services/recording/browser-video.ts` | `close()` aborts fetches, pauses the element, removes its source, and calls `load()`. |
| `freemocap-ui/src/components/viewport3d/RecordingPlaybackProvider.tsx` | Cleanup aborts pending numeric-window requests and stops its animation loop. |

`shared_file.py` already supports replacement-compatible Windows reads for Parquet. It is a file-handle utility, not a recording ownership service. It does not cover native video responses or codec readers; it should not become a second access registry.

## One authority

Add `freemocap/core/recording/recording_access.py`, owned by `FreemocapApplication` and supplied to the posthoc manager and playback HTTP boundary.

The service keys access by the resolved recording directory, using `RecordingStructure` and `Path`, with Windows path normalization. It holds:

- The owning task, if any.
- Whether that task is draining readers, processing, or cleaning up.
- Active read leases and their cancellation requests/completion acknowledgments.

A lease represents actual server resource lifetime. Sending a cancellation request does not release a lease. Only completion of reader cleanup does.

The task registry remains the authority for task progress. Recording access is derived into a self-contained snapshot on the existing transport; clients do not infer availability from task phase or maintain another lock. In particular, `complete` or `failed` does not establish that worker files have closed.

## Ownership sequence

1. Atomically reserve the recording for the task and stop admitting playback readers. A second processing task targeting that recording gets an explicit conflict.
2. Return the accepted task identity promptly. Application-owned preparation requests cancellation of active readers and waits for their cleanup off the HTTP command's critical path.
3. Start processing only when all reader leases have closed. Do not hold the manager's multiprocessing lock while awaiting readers.
4. Keep ownership through annotation publication and worker teardown.
5. Release ownership after confirmed cleanup on success, failure, or cancellation. If teardown fails, report that failure and keep access blocked while handles may remain open.
6. Publish the available state. The client fetches current recording metadata before remounting playback.

Calibration's board-selection preparation opens videos, so ownership must precede preparation, not just the solver. Mocap also reads metadata before starting its worker; that preflight belongs inside ownership.

## Shared HTTP boundary

Add `freemocap/api/http/playback/recording_access.py` as the router's lifecycle adapter. It resolves the recording identity, acquires a lease before endpoint file access, and keeps that lease through the complete ASGI response and cleanup. This must not be an endpoint-local `with` block that ends when `FileResponse` is returned.

Keep Starlette's range-response implementation. The adapter surrounds response execution with cancellation and guaranteed cleanup; it does not implement a new MP4 server or range parser.

For the browser codec stream, wait for threadpool operations to return and for `chunks.close()` to finish. Cancelling an await must not abandon a codec thread and falsely declare its file closed. Short synchronous metadata/window reads can finish; processing waits for them rather than forcibly interrupting file libraries.

New requests during ownership receive a structured recording-busy response (proposed HTTP 409) containing the recording, owning task, and access state. An already-started byte response is terminated through cleanup; its HTTP status cannot be changed after headers have been sent.

Route coverage requires explicit handling of two exceptions within this adapter/router:

- `/playback/parquet?path=...` identifies a file by absolute path. Resolve its recording ownership as well; do not leave a bypass.
- `/playback/recordings` spans directories. Keep listing available, but omit filesystem probing of a busy recording and expose its access state instead.

Descriptor and content routes for one recording share the same guard. Static viewer assets do not require a recording lease. Access-state HTTP recovery must remain available while content is blocked.

## Shared client boundary

Extract the active recording's playback subtree from `PlaybackPage.tsx` into `freemocap-ui/src/components/playback/RecordingPlaybackSession.tsx`. This subtree owns `usePlaybackController` and `RecordingPlaybackProvider` together.

The page mounts that session only when server access state permits it. Blocking unmounts the session, exercising existing video and 3D cleanup. Display one recording-level processing message using existing styles. No checks in individual video tiles or processing buttons.

Use `playback-data-slice.ts` as the bundle request/cache boundary: abort the affected bundle request, invalidate its cached result, and reject late responses from an earlier access revision. On release, fetch a fresh bundle before opening players. A refresh/reconnect obtains authoritative access state; absence of a task message is not permission to open content.

Transport/schema and task-completion integration are necessary plumbing. The current completion handler must defer bundle refresh until access is released, instead of racing worker cleanup.

## Run identity: separate from access ownership

The inspected code has two distinct identities:

- `PosthocPipelineManager` generates a new task UUID per invocation.
- `RecordingMetadata.runs` uses nonnegative integer run IDs. Observation publication currently writes run `0`; checkpoint publication has explicit base and target run IDs.

`AnnotationOutputRequest.pipeline_id` currently identifies only the temporary file. The published filename is fixed per source video. Simply moving the fresh task UUID into that filename would create a new output on every retry, contrary to the requested behavior.

Resolve the logical output run before detection, pass it to the shared annotation writer, and use it in output identity. The same logical run must map to the same destination even across separate task executions. Playback discovery must use that declared association rather than reconstruct filenames independently.

Calibration-only tasks do not currently declare a corresponding saved Parquet run. Its logical run contract must be made explicit before changing names; do not silently equate a calibration task UUID with a saved run ID. This is a bounded naming/metadata follow-up, not a prerequisite for fixing reader ownership.

## Implementation order and acceptance checks

1. Implement and test the access service plus HTTP lifecycle adapter. Prove that processing waits for actual native-range and codec-reader cleanup on Windows, including disconnects and cancellation.
2. Integrate calibration/mocap lifetime, access snapshots, and the single client session boundary. Test open playback followed by processing; late HTTP responses; refresh during processing; failure/cancellation; and two recordings where only one is blocked.
3. Implement logical-run annotation naming and declared media association. Test that rerunning the same run replaces its files without increasing the number of published videos.

Explicitly test failure after only some camera outputs have published. Per-file replacement is not a transaction across all camera videos: access release must not advertise a mixture as a successfully completed run. Record and expose run failure/incomplete output availability without introducing backup video copies.

The first ownership integration covers the two posthoc writers involved here. Synchronization has a separate manager, and live recording is owned by SkellyCam. Extending exclusive recording access to those writers requires their own entry-point integration with the same service; posthoc ownership alone must not be described as universal filesystem locking.

No video copies, persistent video-version history, per-camera ownership rules, or client acknowledgment requirement are part of this design. External applications can still hold files; publication errors from those handles remain explicit errors. In-memory ownership assumes the current single application process; multiple server processes would require interprocess coordination.
