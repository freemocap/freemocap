# Mocap posthoc multiprocessing alignment

Status: initial threaded graph and shared inference integration implemented; ready for first real-app functional QA. GPU throughput, batch limits, and deeper overlap remain to be measured.

## Scope and observed architecture

This is the Mocap/posthoc task. Calibration is a separate task and produces camera geometry; Mocap never runs a solver internally. Geometry is required only by stages that use it.

- `freemocap/core/pipeline/realtime/realtime_pipeline.py` builds per-camera CameraNodes, an optional RealtimeSkeletonInferenceNode, and a RealtimeAggregatorNode. SkellyCam owns camera acquisition and shared-memory buffers.
- `realtime/camera_node.py` reads requested images from shared memory and performs CPU board tracking. Centralized mode excludes skeleton inference from these workers.
- `realtime/realtime_skeleton_inference_node.py` owns one tracker/session, reads a multiframe, and calls Tracker.process_batch. RTMPose batches inference; MediaPipe has its own per-camera execution inside that tracker API.
- `realtime/realtime_aggregator_node.py` requests frames, joins board and skeleton observations by frame number, reconstructs, and coordinates websocket-consumer backpressure.
- `posthoc/calibration_pipeline.py` selects a board, then creates PosthocPipeline: per-video VideoNodes and a PosthocAggregationNode. Each VideoNode owns a tracker and annotation writer; there is no central GPU inference node on this path.
- `posthoc/mocap_pipeline.py` currently bypasses that topology with one worker for decoding, detection, encoding, and reconstruction. This is the architecture to replace, not an intended fallback.

## Recommended worker graph

For N input videos, use N video workers, one central skeleton inference worker, and one aggregation/task worker. The API process owns lifecycle and progress only.

1. Each video worker sequentially decodes its own file into bounded shared-memory slots and performs CPU board detection. It publishes lightweight frame-ready and board-observation messages.
2. The inference worker consumes complete synchronized multiframes in ordinal order, reads the shared images, and uses the same tracker/session construction and process_batch implementation as realtime.
3. The aggregator joins exactly the expected cameras and enabled detector results for each frame. It merges the self-describing observations without replacing one detector's stages with another's.
4. Each video worker receives its merged observation, renders all enabled overlays using the shared compositor, and encodes its video. Raw images remain valid until their consumers finish. Encoding can overlap inference on later frames within the bounded window.
5. The aggregator retains the existing task-facing observation contract and invokes the existing posthoc reconstruction/publication stages when detection is complete. Whole-recording measurements remain an acknowledged memory cost; changing the Parquet model or checkpoint layout is outside this correction.

Do not instantiate a second GPU tracker in the video workers. Do not copy the realtime inference loop into a new posthoc implementation. Extract shared processing and frame-reading responsibilities, with separate live and finite-recording scheduling at the boundary. Realtime's websocket output is not a posthoc processing dependency.

## Scheduling and memory contract

Realtime drains requests to the newest frame and intentionally skips stale work. Its frame reader can skip unreadable camera frames. Neither behavior is acceptable for posthoc.

Posthoc consumes every ordinal exactly once. All input videos must have equal actual frame counts; declared counts must be checked against EOF. No FPS float equality check. Same ordinal means synchronized time. Preserve saved timestamps when present; synthesize from ordinal and frame rate otherwise.

Use a bounded window with explicit slot release after inference, board processing, and annotation have finished reading that frame. Transport image bytes through shared memory; queues carry typed descriptors and observations. Never infer slot availability from just one consumer's read cursor. SkellyCam's ring buffer currently exposes one last_read_index and overwrite checking; that alone does not establish multi-consumer lifetime safety. Specify and test acknowledgement/ownership before enabling overlap.

Missing/duplicate/mismatched results and premature EOF are errors. An observation with no detected board is valid and must still satisfy that detector's completion for the frame. Slow work causes backpressure, not frame dropping. All waits must respond to pipeline shutdown.

## Board selection

One recording-wide selection decision uses the existing SkellyTracker selector: test 5x3 then 7x5, lock the first detected preset, preserve the user-entered square size, and apply the agreed increasing skip schedule during unsuccessful search. No board is valid for Mocap. Do not run independently locking AUTO selectors in every video worker.

Recommended integration: a recording-level selection coordinator uses the existing selector on shared frames until lock, then distributes the immutable board definition to video workers. Keep this bounded and ordered; define the handoff so the first successful observation is retained without duplicate processing. This is selection orchestration, not a second tracking implementation. Verify its concurrency contract in the first implementation chunk.

## Ownership across repositories

- SkellyCam: sequential video decoding, image/frame representation, shared-memory storage and slot safety, ManagedWorker/WorkerRegistry process supervision. Extend existing primitives where their contracts are insufficient; no FreeMoCap duplicate ring-buffer implementation.
- SkellyTracker: session creation, batching, detector state, board selection/backoff, annotation primitives. Reuse its configured tracker APIs and move common tracker-only logic there when needed.
- SkellyForge: skeleton/model fitting and numerical reconstruction capabilities already owned there. Do not recreate models in transport or recording code.
- FreeMoCap: compose these components into task graphs, coordinate frame/result joins and board selection, orchestrate annotation/output retention, expose API lifecycle and progress.

Names and request types should identify their actual role. Use typed configuration/request objects and existing factories; avoid broad kwargs bags, string-based role guessing, and abstractions that merely reshape existing models.

## Lifecycle and progress

Every worker in one graph shares one pipeline owner shutdown scope. A crash or unexpected exit fails the graph and stops/reaps all its workers, including those blocked on queues or buffer slots. It must not stop other pipelines or the application.

EOF is an explicit successful producer outcome, not a worker-crash heuristic. A zero exit without the required terminal protocol is failure. Start failure must roll back every worker and resource already created. Publish the originating error before cleanup and retain terminal status for clients. Test hard process death as well as Python exceptions.

Expose real per-video decode/annotation progress, central inference progress, and aggregator/reconstruction stages. Worker identity and processing stage are separate fields; do not parse camera identity from a display label or manufacture workers for presentation. Pipeline completion requires all required outputs to be finalized, not merely 100% inference.

## Implementation checkpoints

1. Review this graph. Trace and test shared-memory acknowledgements, reusable inference construction, and recording-wide board selection handoff. Lock the typed message contracts before wiring workers.
2. Extract shared inference processing from realtime, keeping realtime scheduling and behavior intact. Verify both supported detector families and arbitrary camera counts.
3. Wire sequential video producers, bounded slots, per-camera CPU work, central inference, and exact aggregation. Fault-inject producer, inference, and aggregator death; verify sibling termination and independent pipeline survival.
4. Wire merged annotation results and existing reconstruction/publication. Delete the single-worker Mocap execution path and obsolete callers/tests; no compatibility branch.
5. Wire stage/node progress to the app. Validate on Windows through the real API, then request user testing: person+board, no board, board disabled, cancellation, failure, and repeated runs. Record throughput and peak memory against the current implementation using the same recording and detector settings.

No dependency-source changes, editable installs, or site-packages edits. Cross-repository changes are committed/pushed by the user, then installed through the normal Git dependency update workflow.

## Deferred work remains on the roadmap

Camera/media identity resolution and calibration reprojection-fitness permutation search remain separate planned work (permutation search requires design review before implementation). Recording data-model and staged reprocessing work resumes after this execution correction. Do not couple this transport change to speculative disk schemas or reintroduce disabled numerical exports.

## Shared inference service: approved direction and first dependency checkpoint

Realtime and Mocap/posthoc will submit to an application-owned inference service. All Mocap/posthoc workers use WorkerMode.THREAD. The shared service has its own lifecycle scope; pipeline cancellation releases that client's pending work and session leases. A fatal service failure terminates all dependent pipelines with an explicit error.

Scheduling starts with interleaved whole-multiframe requests, realtime preference with bounded posthoc fairness, and bounded admission/backpressure. No cross-pipeline tensor batching initially. In-flight native inference cannot be forcibly interrupted by thread cancellation; results must be discarded for a canceled client and resource release must wait until inference returns.

SkellyTracker implementation checkpoint:

- Added SharedSessionPool and TrackerLease in `skellytracker/core/sessions/shared_sessions.py`.
- Exact typed session configuration equality determines compatibility, including provider/device/model/batch settings. Configurations are snapshotted to prevent caller mutation changing an existing allocation's identity.
- Every lease creates independent detector instances. TrackerState alone is not sufficient isolation because MediaPipe maintains detector/landmarker state internally.
- Closing a lease closes its detectors and releases its session references. Shared sessions close only when the last client releases them. Idle sessions are not retained indefinitely.
- Session-pool operations are confined to their owning execution thread. This is resource ownership, not the application scheduler.
- Six focused tests cover reuse, distinct detector ownership, configuration changes, failed construction rollback, closed-pool rejection, and thread confinement.

This checkpoint does not wire the shared service into the app and does not replace the single-worker Mocap graph yet. FreeMoCap continues to use its Git-installed SkellyTracker. Before integration tests can exercise the new API, the user must commit/push SkellyTracker and update the dependency through the normal workflow. No editable installs, site-packages changes, or import-path overrides are permitted.

Next: implement the application service's typed registration/request/result and cancellation protocol against these leases, test fairness and failure fanout, migrate the realtime inference adapter, then wire the threaded posthoc worker graph. GPU resource admission and multiple model configurations still need validation; session reuse alone is not a VRAM capacity guarantee. MediaPipe sessions choose device context but their landmarkers remain per-tracker resources, so sharing a MediaPipe session is not equivalent to sharing loaded ONNX model weights.

### Scheduler implementation checkpoint

Verified the Git-installed SkellyTracker exposes SharedSessionPool. Added `freemocap/core/pipeline/inference_service.py` with a managed thread, typed registrations and requests, per-client tracker leases/state, one outstanding multiframe per client, and round-robin scheduling within mode. Ready posthoc work gets a turn after three realtime requests. Image ownership lasts until the result future is terminal; active cancellation discards results after native inference returns. Request failure signals only its pipeline; service teardown fails remaining dependent requests.

Six tests in `freemocap/tests/test_inference_service.py` pass, including an integration test using the installed pool and actual CPU session implementation. Tests exercise distinct client state for identical camera names, request failure isolation, cancellation while work is active, bounded admission, finite-recording frame order, and scheduling fairness. GPU throughput and multiple-model VRAM limits remain unvalidated.

The service is not connected to the live pipeline factories yet. The next implementation step is to unify session-request construction with the existing tracker factory and replace realtime session ownership with a service client adapter; then replace the Mocap single-worker path with the approved threaded graph. Do not describe this checkpoint as app-test-ready.

Audit finding for the adapter: realtime `_read_frames` currently logs a warning and uses an available frame if its ordinal differs from the requested one. The shared adapter must not mislabel that image with the requested ordinal. Handle live stale-frame selection explicitly; posthoc mismatches must fail. This is separate from media filename identity resolution.

### Realtime service adapter checkpoint

Realtime's centralized inference adapter is now a managed thread submitting to the application-owned InferenceService. The application creates and shuts down the service; stopping an individual realtime pipeline closes only its client. Camera and aggregation workers retain their own topology. Session requests and tracker configuration construction are factored from the existing factories so leased and directly owned trackers use the same model definitions.

The adapter retains newest-request scheduling and confidence gating, closes its shared-memory handles, and never substitutes another frame ordinal for the requested one. Backend timeout exceptions are distinguished from polling timeouts. Service failures remain inspectable by idle clients so a stopped service cannot look like successful worker completion.

Validation: seven scheduler/adapter tests pass; the adapter test exercises both RTMPose and MediaPipe configurations with mocked inference. The existing seven Mocap integration tests passed after factory consolidation. Python compilation passed for realtime modules and adjusted pipeline test callers. No live-camera or GPU performance result is claimed.

Remaining: the threaded posthoc worker graph and its service adapter, shape/batch admission limits, end-to-end simultaneous-pipeline failure tests, and real-app validation. Current posthoc execution still uses its single worker and is not the approved final topology.


### Threaded Mocap graph: real-app QA checkpoint

Mocap now creates per-video managed threads for sequential decoding, board detection, and annotation encoding. A separate managed aggregation thread coordinates complete multiframes and invokes reconstruction/publication. Skeleton inference is submitted to the same application-owned service used by realtime. The standalone all-in-one detection loop has been replaced.

Because these workers are threads, bounded queues carry references to decoded NumPy images in shared process memory; no additional image serialization or custom shared-memory ring is introduced. The initial schedule allows one complete multiframe at a time, with per-camera work parallel and board selection overlapping inference. Deeper decode/encode lookahead is a performance follow-up, not claimed implemented here.

Per-video progress uses the existing video-node progress contract. The aggregation bar remains the recording-level collection/staged-processing status. A dedicated inference progress row still requires extending the UI node-role contract; inference must not be presented as a fake camera.

All video EOF checks pass before publication begins. Cleanup joins video threads; failures retain the originating error and stop the owning pipeline. Pipeline liveness includes remaining video threads, so a blocked native thread is not silently evicted as completed. Threads cannot be forcibly killed safely.

Validation: 24 focused tests across threaded detection, recording integration, scheduler, realtime adapter, and retained progress; Python compilation and UI TypeScript checks. Body inference is mocked in recording tests; board detection and video encoding/decoding are real. A decoder fault test verifies sibling threads exit while the inference service and application remain available. No full GPU performance claim.

User QA after normal backend restart:
1. Start realtime tracking, then process a short recording with person and board. Expect one progress row per video plus recording stages; verify both overlays and playback.
2. Stop realtime during posthoc processing. Posthoc must continue. Repeat by canceling posthoc while realtime remains active.
3. Run without a visible board, then with board detection disabled. Both must complete skeleton processing.
4. Trigger an input/decoder failure and confirm the error appears, progress becomes failed, and another pipeline can start.
5. Report any startup errors, missing progress rows, stalls, or GPU memory/performance problems. Keep real recordings intact; test outputs may be regenerated in the designated test recording.


### Processing throughput and playback continuity follow-up

The real-app run produced annotated videos and reconstruction, but exposed slow
processing and periodic 3D playback stalls. Per-video progress measures completed
annotations; reports occur at roughly 2% intervals. The central inference batch
uses one synchronized multiframe, so similar video progress remains expected.

Video workers now decode one multiframe ahead during shared inference, bounded
to two queued commands per worker. Encoding and observation collection still
join per multiframe; deeper stage overlap and real detector throughput measurement
remain outstanding. This is not calibration's independent detector-per-video
scheduling: skeleton inference is intentionally shared at application scope.
Both paths reuse managed workers, scoped IPC, tracker/annotation facilities and
tqdm terminal progress. Mocap terminal bars count actual annotated frames and
exist only in the posthoc video worker.

The 3D provider now requests the next 2.5-second sample window with 1.5 seconds
remaining in the active window, retaining active data while loading. It keeps at
most two completed windows and one request; no per-frame server requests.
Real-app QA: inspect terminal frame rates, compare processing duration, play
through several window boundaries, and seek forward/backward while playing.
The lookahead is latency mitigation, not a guarantee against arbitrarily slow
window responses. GPU/MediaPipe profiling remains required before asserting the
overall throughput problem is resolved.

### Terminal progress display

SkellyLogs console output coordinates with tqdm to print logs above active bars
and redraw them under the shared display lock. Posthoc bars remain enabled in
IDE consoles as well as terminals, refresh at most four times per second during
normal updates, and Mocap labels use camera IDs to reduce wrapping. The SkellyLogs
source/dependency change requires user commit/push and a FreeMoCap dependency
update before full app validation. Test in the normal app launch console. Cursor handling still requires real-app
verification; terminal detection must not silently suppress requested progress.
