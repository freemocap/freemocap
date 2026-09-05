# Processing and playback integration

Approved direction: 2026-09-05. Implementation is incomplete.

Companion contracts: [recording data model](../03-transport/recording-data-model-proposal.md)
and [posthoc rebuild](posthoc-rebuild.md).

## Shared computation

Keep worker lifecycle management. Share resolved tracker configuration, session construction,
batched inference, per-camera tracker state, triangulation and skeleton reconstruction.
Realtime consumes current camera frames and may drop stale work. Posthoc consumes every selected
video frame in order with bounded backpressure. Neither mode owns another copy of the scientific
algorithms. Posthoc scale estimation consumes the complete recording before reconstruction.

Annotation consumes original images and selected saved observations. It is an export operation,
independent of detector execution. It must never draw over an annotated output from another run.

## Channel and timing contract

SkellyForge definitions remain authoritative for skeleton semantics. Shared channel definitions
declare owner, ordered names, components, units and reference frame. Numeric computation produces
typed arrays; streaming packs them and recording serialization emits tall Arrow batches. Neither
serializer calls the other. Model definitions stored on disk include scientific definitions that
the renderer does not require.

Every sample carries recording-clock time and its sensor-group frame number. A timestamp is a
temporal coordinate, not a unique scalar-row identifier. Camera capture timestamps and fused group
timestamps remain distinct. Persist the clock mapping and media-time mapping explicitly. Nominal
FPS must not silently replace capture timing. Imported media without capture timing needs a declared
media-derived clock. Cross-device synchronization requires a supplied or measured clock mapping.

## Dependencies and execution

Stage dependencies govern reuse and invalidation. Supplied calibration is independent of detection;
solved calibration depends on board observations. Reconstruction reads filtered points and fitted
scale. Biomechanics also reads recording time. Recompute only descendants of changed inputs.

The dependency planner distinguishes supplied/solved calibration and validates reusable ancestors.
It does not yet distinguish board and body observation stages, support initial ingestion into an
empty store, or dispatch workers. Those are required before GUI integration.

The executor opens media and constructs tracker sessions only when observations require computation.
Reconstruction-only execution reads saved prerequisites and starts numerical processing directly.
Cancellation must propagate as cancellation, not successful completion. Errors must reach job status
and fail execution. Temporary outputs do not become the published result after cancellation/failure.

## API contract

Use the existing recording and pipeline services; do not add an independent job framework.

- Inspect recording: committed result IDs, available channels/groups, stage checkpoints, media and
  time ranges. File existence alone does not establish a valid processing checkpoint.
- Preview processing: recording, base result, groups, requested settings and output boundary,
  keep/overwrite choice. Return resolved inputs, reusable stages, stages to execute, invalidated
  outputs and target result ID. Missing prerequisites produce an actionable error.
- Start processing: revalidate the preview against current committed metadata, configuration and
  resolved inputs under the recording write lock. Reject a stale preview before starting workers.
- Observe/cancel: existing transient pipeline ID tracks progress and cancellation; saved run_id
  identifies a result. These identities serve different purposes.
- Read playback: selected result and bounded recording-time interval, with channel/group selection.
  Return packed renderable arrays and descriptors, not JSON for every Parquet scalar row.

## Processing interaction

Select recording/result, change settings, review reuse/recompute consequences, then process.
Default overwrite replaces the selected result only after successful publication. Explicit keep
creates another result and retains the base. Advanced controls expose stage boundaries; ordinary
users should not need to understand worker topology. Changes to inputs determine required stages.

Example preview: Reuse detection and calibration. Recompute triangulation through biomechanics.
Overwrite result 0 when processing succeeds.

Show pending/running/cancelled/failed/completed states and stage progress. Keep playback pinned to
the committed result during processing. Refresh on success; preserve the recording-time cursor when
it remains within the new result. Surface optional export failures separately from processing status.

## Playback interaction

The primary cursor is recording time. Each group resolves its own sample and displays its own frame
number. Stepping advances to the next/previous sample in a selected group. Media selection preserves
recording time using the declared video-time mapping. A missing sample remains missing; interpolation
must be an explicit display policy and must not modify recorded values.

Support playback without video. Do not make a 30 Hz video the data clock for a 120 Hz sensor. Cache
bounded time windows and discard stale seek responses. Refresh cache identity when the selected
committed result changes, including overwriting the same run_id.

## Acceptance sequence

1. Shared domain adapters preserve names, units, quaternion ordering and scientific definitions.
2. A real recording produces canonical timing, observations and reconstructed channels.
3. Reconstruction-only reprocessing succeeds with detector construction and video opening forbidden.
4. Keep/overwrite, failure and cancellation are tested through worker execution and publication.
5. API preview matches actual executed stages and rejects stale inputs.
6. Playback seeks a mixed 30/120 Hz recording, preserves time across media/result changes and reports
   missing samples correctly. Tests must include irregular timestamps and nonzero media offsets.
7. Additional exports consume the canonical reader. The .freemocap.mp4 embeds the selected data and
   metadata without resampling higher-rate sensor data to the grid video's FPS.
