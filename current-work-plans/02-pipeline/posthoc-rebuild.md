# Posthoc pipeline rebuild

Status: implementation in progress, 2026-09-05.
Target contract: [recording data model](../03-transport/recording-data-model-proposal.md).
Integration contract: [processing and playback](processing-and-playback-integration.md).
This plan governs ordering and persistence for this workstream, including where earlier revival
notes deferred the schema or treated a large streaming window as a completed global fit.

## Implementation progress

- The mocap task publishes observations, camera/group timing and raw 3D points into the canonical
  Parquet store. It now also publishes LANDMARKS_3D, SEGMENT_ORIGINS and ROTATIONS_WORLD, with named
  source layouts and explicit spatial references. Single-camera planar coordinates and fits are
  declared in pixels; calibrated outputs use millimetres. Missing frames remain null.
- `RecordingReconstructionInput` carries the numerical request without repeated argument lists.
  Each `ModelRecordingReconstruction` retains frames and the complete SkellyForge `ModelScaleFit`.
  The recording-wide evidence pass freezes either a fit or an explicit absence of evidence.
  `reconstruct_skeletons_with_fits` uses fresh temporal state and does not accumulate scale evidence.
- Per-group/source `scale_fits` stores the complete typed fit once in the run descriptor, including
  per-segment scales/lengths and the measured/voting sets. SkellyForge owns fit invariants. FreeMoCap
  binds the fit to recording source/reference/units. Static channel views of this fit remain to be
  connected; do not create another independent copy of these measurements.
- Scale-fit invalidation follows SCALE_FIT dependencies. Reconstruction-only restarts retain the fit;
  scale restarts remove the selected group's fit. Keep and overwrite preserve other results/groups.
- Point and reconstruction adapters share `ChannelSeries` and `SeriesSampling` for bounded tall Arrow
  serialization. Channel declarations do not allocate recording-sized arrays. Reconstruction still
  holds full-recording results in memory, and each channel adapter builds one numeric trajectory array.
- Calibration solving belongs exclusively to the calibration task, which produces the calibration
  TOML. Mocap has no calibration stage or calibration-completion checkpoint. Its planner requires
  geometry only for executed multi-camera triangulation or reprojection. Downstream processing from
  saved direct inputs does not require historical camera/calibration inputs.
- Resolved camera geometry is persisted per group from the actual cameras used for triangulation.
  Solver statistics and acquisition method are not part of this geometry contract.
- SkellyCam owns timing ingestion: existing sidecars preserve recording-relative timestamps;
  absent sidecars infer `offset_s + frame_number / fps`; malformed present sidecars fail. The mocap
  path uses synchronized video frame zero as inferred time zero. Missing group timing uses the mean
  of camera times. Observation sources declare how their timestamps were obtained.
- Recording metadata, bounded Parquet validation, write locking, atomic publication, JSON mirror
  recovery, checkpoint signature comparison and scoped keep/overwrite have focused tests.
  Observation requests use typed models/factories; streaming and recording share ChannelKind.
- Validation: **63 focused tests pass**, including a real skeleton's generated reconstruction written
  through the canonical writer, fit reload from Parquet metadata and numerical replay with scale
  fitting forbidden. Publication/overwrite tests cover missing frames and world quaternions.
  Lint and mocap/calibration task imports pass. These are synthetic-data tests, not detector/video
  acceptance. The validation environment uses editable local SkellyCam and SkellyForge.

### Next bounded chunks

1. Complete reconstruction persistence: local-rotation reference semantics, joint angles and derived
   channels; expose fitted static channel views from the single stored fit. In particular, review
   `_local_rotations`: a missing parent currently yields a world quaternion, which cannot be labelled
   unconditionally as parent-relative data on disk.
2. Persist full scientific definitions/rest pose/mapping and the actual reconstruction input arrays,
   with explicit filter policy and stage input signatures. Current source layouts describe channel
   names/topology; they are not a scientific definition snapshot. Ingestion emits no reusable stage
   completion checkpoints yet.
3. Connect saved-data worker dispatch with video opening and detector construction forbidden.
   Validate request-driven keep/overwrite, cancellation and failure through real worker execution.
4. Process a real recording end to end. Timestamp-based playback and the default annotated grid
   output follow this acceptance milestone; optional raw grid and other exports follow their plans.

Check in before the next implementation chunk. Keep capture/transport in SkellyCam, detector
functionality in SkellyTracker, skeleton computation in SkellyForge, and orchestration in FreeMoCap.

## Outcome

Process a recording into the agreed self-describing Parquet + recording_info. Reprocess selected
stages without rerunning valid upstream work. Default run_id=0; explicit keep creates another result,
overwrite replaces the chosen result. Optional additional-format exports follow the core rebuild.

Keep the current worker management, cancellation and progress machinery where useful. Reuse the
shared skeleton computation for human and board; do not rebuild deleted SkellyForge APIs.

## Current integration points

- core/pipeline/posthoc/posthoc_pipeline_manager.py: creates calibration/mocap jobs.
- core/pipeline/posthoc/posthoc_pipeline.py: currently creates VideoNodes on the detection path.
- core/pipeline/posthoc/posthoc_aggregation_node.py: collects frame observations and invokes a task.
- core/tasks/mocap/posthoc_mocap_task.py: current observation-to-provisional-output task.
- core/tasks/calibration/posthoc_calibration_task.py: calibration solve and board reconstruction.
- core/reconstruction/posthoc_reconstruction.py: batch triangulation and per-frame reconstruction.
- core/skeletons/reconstruct_skeleton.py and reconstruction_state.py: shared solve and state.
- core/streaming/message_model.py and producers/: existing channel structures.
- system/recording_structure/recording_structure.py: path owner.
- api/http/playback/playback_router.py: reader integration.
- core/tasks/mocap/mocap_task_config.py and pipeline/posthoc/pipeline_phases.py: request/progress contract.

Batch reconstruction uses a complete-recording evidence pass, one global fit, then a
reconstruction pass with frozen scale and fresh roll state.
Current provisional NPY/CSV outputs are not the target store. The stage runner must be reachable
without constructing detector workers when reusing saved detection.

## Stage graph and durable boundaries

```text
input media + timing -> observations -> triangulation -> filtering -> scale_fit
                                              ^              |           |
                                              |              +-----------+
separate calibration task -> TOML -> camera geometry          |
                                              |         reconstruction -> biomechanics
                                              |              |
                                              +--------> reprojection

canonical saved outputs -> optional exports
```

Reconstruction also reads filtered points and model/rest-pose definitions. Biomechanics reads
reconstruction, fitted scale and mass definitions. Reprojection reads reconstruction and calibration.
Calibration solving consumes board observations in its separate task. Mocap consumes resolved camera
geometry only when executing an operation that requires it. Single-camera planar reconstruction
sets Z to zero without calibration. Saved-data downstream processing requires only its direct inputs.
No dependency on whichever global calibration file happens to be newest at a later stage.

| Stage | Reusable input | Saved output |
|---|---|---|
| ingest/timing | recording media/capture metadata | sensor groups, timing rows and input descriptions |
| observations | images + resolved detector config | OVERLAY_2D with names, visibility and camera frames |
| triangulation | 2D observations + camera geometry for multiple cameras | raw 3D keypoints, reprojection quality and camera weights |
| filtering | raw 3D + timestamps/config | filtered 3D keypoints and necessary fitting eligibility |
| scale_fit | eligible filtered observations + mapping/model | frozen instance scale/segment parameters |
| reconstruction | filtered points + frozen fit/model/rest pose | landmarks, origins, local/world rotations, joint angles |
| biomechanics | reconstruction + mass/ground definitions + timestamps | configured derived channels |
| reprojection | reconstruction + resolved camera geometry | camera-image projections |
| exports (later) | canonical reader + selected run + media | chosen additional format |

These are current stage boundary artifacts, not every internal iteration. Persist them in the same
logical store to make stage reuse possible. Do not materialize large Python scalar-row lists.

### Minimal channel additions for restartable stages

Preserve KEYPOINTS_3D as the points supplied to reconstruction (consistent with the current realtime
filtered output). Add RAW_KEYPOINTS_3D for ungated triangulation output. Save reprojection error with
its declared units and camera-specific weights as a TRIANGULATION_WEIGHTS scalar channel.
For weights, reference_frame is null and source is the actual camera; the declared tracker keypoint
association is in the channel descriptor. Disambiguate multiple trackers by their explicit channel
name registry; if overlapping tracker namespaces occur, scope camera diagnostic sources by tracker
in the descriptor and validate uniqueness. This diagnostic binding must not be confused with a
spatial reference frame.

Prefer a narrow internal validity/fit-eligibility component on KEYPOINTS_3D if interpolation is used,
sufficient to prevent gap-filled samples teaching scale after a reload. Define it before serialization
and test it. This is a numerical input to fitting, not a mapping-provenance taxonomy.

Exact component declarations are phase 1 work; no unknown ad hoc channel names are accepted at runtime.
OBSERVATIONS restart means restart a whole detector stage, not resume a detector mid-frame without
its temporal state. Preserve all numeric inputs needed by downstream work; do not claim that the
entire arbitrary TrackerState can be reconstructed from keypoints.

## Execution request and planning

Add one explicit processing request around existing scientific configs:
- base_run_id: selected result for reprocessing; 0 for first processing.
- result_policy: overwrite or keep.
- start_stage and stop_stage: stage boundaries; default whole mocap path.
- sensor_groups: explicit processing scope.
- resolved detector/calibration/filter/model/biomechanics settings.

First build an execution plan: validate prerequisites, decide reuse/recompute, allocate target ID,
list invalid descendants, then run workers. Missing required saved input is an error identifying the
earliest required stage; do not silently launch expensive detection after a late-stage request.

Validate reuse against actual relevant inputs/settings and schema/model compatibility, not file
existence. Store stage-local dependency signatures covering input content or validated input identity,
resolved settings, model/mapping definitions, calibration and algorithm version. This is a small
stage record in recording_info/embedded descriptor, not source archival infrastructure.

If a requested start_stage is later than the earliest invalid dependency, fail with that stage and
reason. UI can present the necessary restart before submission. Honor disabled stages explicitly:
an identity filter is a declared policy; unavailable biomechanics is not fabricated output.

Reuse checks are per selected group/source/stage. Other sensor groups remain untouched unless a
changed clock mapping or explicit cross-group dependency invalidates them.

## Keep versus overwrite: exact behavior

| Request | Behavior |
|---|---|
| First processing | Write run 0 |
| Overwrite run 0 from filtering | Reuse its observations/raw 3D; replace filtering, scale, reconstruction and biomechanics |
| Keep run 0, restart filtering | Allocate next integer run; copy reusable upstream data into it; compute descendants; run 0 stays intact |
| Restart biomechanics only | Load saved reconstruction/static fit; no detector, triangulation or reconstruction workers |
| Stop after filtering | Publish completed checkpoints; mark scale/reconstruction/biomechanics absent for affected scope |
| Retry failed stage | Start at a validated completed boundary; no reuse of partial stage output |

Keep targets are self-contained and include unchanged groups/channels from the selected base run.
Avoid references that would break when the base run is later overwritten. Copying data into the new
run is intentional, user-requested retention. Unrelated existing runs survive every publication.

Change dependency rules:
- Media/detection settings -> observations and all descendants.
- Calibration -> triangulation and descendants; reuse observations.
- Filter settings -> filtering and descendants.
- Mapping/skeleton/rest pose -> scale/reconstruction and descendants; reuse tracker-space points
  when their interpretation is unchanged.
- Mass/derived-quantity settings -> biomechanics.
- Timing/clock mapping -> affected temporal processing and cross-group consumers; assess whether
  synchronization changed camera pairing, in which case triangulation also invalidates.
- Export options -> that export only.

Replacing an upstream output invalidates ALL dependent channels/static values for the affected scope,
even if stop_stage prevents their recomputation. Never leave stale downstream rows in the target run.
Stage status (not_computed/completed/failed) and coverage distinguish an all-missing completed result
from an absent computation. Logs track the attempt; run_id identifies the retained dataset.

## Publication and cancellation

Use one writer lock per recording for allocation and publication; first version may hold it throughout
processing to keep semantics simple. Other recordings can run independently.

Write validated completed stage outputs into a temporary work file/directory inside the recording.
At a stage boundary, publish a coherent Parquet rewrite:
- stream-copy unaffected runs/scopes,
- write target run's retained/new channels,
- exclude invalidated descendants,
- embed the matching run descriptors and stage completion state.

Parquet replacement is a bounded-memory rewrite, not row-level in-place mutation. After closing and
validating the temporary file, atomically replace the data file on the same filesystem. Then update
recording_info's mirrored dataset descriptor. Two files cannot be atomically replaced together:
the Parquet embedded descriptor is authoritative for committed data, and startup repairs a stale
JSON mirror from it under the lock. Reader behavior and Windows open-handle constraints need tests.

A stage failure leaves the last completed checkpoint readable, with its downstream stages absent if
already invalidated. A failure before the first new checkpoint leaves the previous result intact.
Failed/partial temporary output is never reused as completed. Report exceptions and cancellation,
release resources, and retain concise failure information in logs/processing metadata.
No hidden history generations; temporary files are publication scratch only.

Per-run calibration and fits must be preserved in metadata when keep is selected. A top-level
calibration TOML is the selected run's convenience artifact, not the authority for all retained runs.
Annotated media/export files also identify their run/options; overwriting data marks dependent exports
stale. Readers never equate an existing .blend or .mp4 with an up-to-date result.

## Numerical processing

1. Triangulate arrays in batches with validated camera pairing, keypoint order, calibration and timing.
   Preserve raw outputs/quality before filtering. Do not bind cameras by accidental dictionary order.
2. Apply a declared batch filtering/gap policy using actual timestamps, with adequate temporal context.
   Whole-trajectory algorithms may use per-trajectory arrays; bounded serialization does not justify
   incorrect independent filtering of chunk edges.
3. Hydrate eligible observations to accumulate scale evidence without fitting after every frame.
   Reuse fit_model_scale once per instance over the complete recording scope.
4. Reconstruct in chronological group order with FrozenModelScale and fresh roll state.
   Never carry resolver state from the evidence pass into the final pass or across instances/runs.
5. Compute derived trajectories using shared SkellyForge functions and actual timestamps.
   Preserve missing-data boundaries and declared ground/scale requirements.
6. Translate into the shared channel schema before wire packing, retaining numeric precision.

Keep numerical masks needed to exclude predicted/interpolated observations from scale evidence,
without exposing a generic provenance column. Validate local rotations when parents are missing.
Single-camera geometry must be labeled in its real units and cannot silently produce metric results.

## Implementation sequence and file ownership

### 1. Contract and round trip

Create focused modules under freemocap/core/recording/:
- recording_metadata.py: typed recording/run/group/source/channel descriptors.
- recording_data.py: numeric batch contract and validation.
- recording_reader.py: scoped reads and static channel expansion.
- recording_writer.py: stage publication and keep/overwrite semantics.

Names are proposed implementation locations; reuse a matching existing owner rather than duplicate it.
Extend channel/component descriptions alongside core/streaming/message_model.py; extract a shared
description layer if needed so disk does not depend on transport packing. Update RecordingStructure.
Use all Python type hints, module-level imports and keyword arguments where APIs support them.

Deliver a synthetic save/read fixture first: human + board, two same-model instance descriptors,
two cameras, 30/120 Hz groups, named joint angle, quaternion, missing point, static scale, run 0/1.
No live eye-tracker integration required for this schema test.

### 2. Stage planner and persistence semantics

Under core/pipeline/posthoc/, add processing_request.py and stage_execution_plan.py with explicit
stage definitions/dependencies. Keep the registry small; no general workflow framework.
Implement validation/reuse/invalidation plus checkpoint writer tests before expensive workers.

### 3. Observation/timing and worker bypass

Adapt VideoNode/PosthocAggregationNode output into persistent named 2D/timing channels.
Extend PosthocPipelineManager to launch saved-data processing directly when observations are reusable.
Do not create VideoNodes or wait on detector queues for a biomechanics-only request.
Route group-local frame identity through the boundary; avoid a single global FPS/count.

### 4. Shared batch reconstruction and calibration

Adapt core/reconstruction/posthoc_reconstruction.py and the mocap/calibration tasks into the graph.
Implement true two-pass fitting and saved stage inputs/outputs. Remove provisional required CSV/NPY
writing and required Blender completion from the mocap task.
Reuse the generic board bundle; preserve the solved calibration directly rather than reloading a
global "latest" path. Separate calibration success from optional board-derived output failures.

### 5. API, progress and playback

Expose start/stop stage, selected base run and keep/overwrite in the existing posthoc request path.
Update pipeline_phases.py and frontend phase mapping together. Report reused stages and recomputation,
not misleading detection progress for every request.
Playback reads selected_run_id and aligns by timestamps. No rglob-first-Parquet fallback.
Display completed, missing, failed and stale-export states explicitly.

### 6. Optional exports next

Implement a reader-based export interface after core acceptance:
- CSV/NPY adapters with explicit names/units/timing and selected run.
- Blender and other requested animation formats.
- .freemocap.mp4 prototype then exporter: annotated grid default, raw/both options, embedded selected
  JSON/Parquet payload, tile definitions and video-time mapping. Keep 120 Hz data even in 30 fps video.
  Verify extraction, version checks, timestamp alignment and ordinary playback.
Exports run independently, have their own success/failure, and can be regenerated without mocap.
Selecting an unsupported exporter fails explicitly; do not swallow an export exception as success.

## Acceptance gates

- Synthetic schema round trip preserves timestamps, names, units, reference frames, static values,
  multiple instances/groups and nulls; rejects duplicate component keys.
- Real camera recording produces calibrated output using the shared math and finite/plausible checks.
- Global fit is constant over all final frames; noisy early frames do not become permanent early fits.
- Filter-only reprocess demonstrably makes zero detector calls; biomechanics-only skips reconstruction.
- Keep preserves base data/settings/fits and creates an independently readable result.
- Overwrite preserves unrelated runs/groups and removes stale descendants, including stop_stage cases.
- Calibration/filter/model/timing changes trigger the correct earliest invalid stage.
- Interrupted writes/failed stages/JSON mismatch recover without claiming partial data is complete.
- Mixed-rate fixtures retain all samples; playback aligns by timestamp without frame-number joins.
- Stage reload produces the same numerical inputs/results as uninterrupted processing, including
  fitting eligibility and temporal state resets.
- Long-recording writer/rewrite stays bounded in memory; filtering chunk boundaries remain correct.
- Core processing succeeds with no export selected; later exporter failures remain export failures.

First implementation deliverable: phase 1 plus phase 2, proving the disk contract and restart rules
before converting the full processing path.
