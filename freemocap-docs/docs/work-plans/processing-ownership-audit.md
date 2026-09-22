---
title: Processing outputs and object ownership audit
sidebar_position: 1.6
mdx:
  format: md
plan_status: ongoing
plan_generated: "2026-09-10"
plan_audited: "2026-09-10"
---

# Processing outputs and object ownership audit

## Scope and review status

Source inspection of normal posthoc mocap publication and realtime pipeline apply.
This extends the [architecture review](architecture-review.md). No runtime changes
or live camera tests were made. Calibration publication, every export, and low-level
device-setting reconciliation are not covered by this pass.

**Ready for review:** the difference between available planner behavior and what the
normal processing command actually invokes; the meaning of realtime “apply.”

## Processing: command to published result

1. The UI's `processMocapRecording` thunk posts the processing request to HTTP.
2. `process_mocap_recording` asks the application to create a posthoc mocap pipeline.
3. The worker's mocap task builds an `ObservationRecordingRequest` and calls
   `publish_posthoc_observations` with computed observations and reconstructions.
4. Publication creates run 0 when the recording Parquet does not exist. For an
   existing file, it creates a `ProcessingRequest` without overriding its
   `base_run_id=0` or `keep=False` defaults.
5. The planner selects a target run and invalidates dependent outputs in the
   selected sensor groups. The publisher combines valid retained data and new data.
6. Parquet publication validates batches, writes a temporary file, and replaces the
   destination after writing finishes. Health-report generation follows Parquet
   publication; this is not one transaction covering every output file.

## Output policy: implemented capability versus exposed behavior

| Case | Inspected behavior |
| --- | --- |
| Planner with `keep=False` | Targets `request.base_run_id` |
| Planner with `keep=True` | Allocates `max(metadata.runs) + 1` |
| Normal mocap publication | Uses default base run 0 and `keep=False` |
| Data outside the invalidated scope | Retained according to stage and sensor-group rules; other runs are preserved |
| Changed sample grid during observation overwrite | Raises an error rather than replacing incompatible retained data |

**Finding:** the planner has a separate-run capability, but this normal publication
path does not pass a user's append choice into it. Searches of the UI and API for
the planner's `keep` and `base_run_id` fields did not establish an exposed selection
path. Planner support should not be documented as an end-to-end UI feature yet.

“Overwrite” here means replacing results within the selected run and invalidated
scope. It does not mean deleting every run or every file in the recording folder.
The next implementation design should make that scope explicit in the UI/API contract.

This is an output-policy question, not a requirement for durable request IDs,
exactly-once execution, or recovery after a server restart.

## Long-lived objects: realtime apply

`FreemocapApplication` holds the camera-group and realtime-pipeline managers.
The realtime HTTP endpoint resolves supplied camera configs, or uses the existing
group's configs when none are supplied, then calls
`create_or_update_realtime_pipeline`.

| Application state | Actual application-level path |
| --- | --- |
| A realtime pipeline already exists | Updates the first pipeline's processing config and immediately returns it |
| No realtime pipeline exists | Creates/updates the camera group, then asks the realtime manager to create a pipeline with the requested camera subset |

**Finding:** the existing-pipeline branch does not forward camera configs or the
requested camera subset to the camera-group/creation path. This method alone is
therefore not a full reconciliation of all fields accepted by realtime apply.
This matters even with one client and one pipeline; it is not a multi-client edge case.

Separately, `RealtimePipelineManager.create_pipeline` compares camera-ID sets and
reuses a matching pipeline or creates, starts, and stores a new one. That manager
behavior does not override the application's earlier return.

In SkellyCam, `CameraGroupManager.create_or_update_camera_group` either creates a
group or updates a found group. Its grouping helper selects configs for camera IDs
already in each group. This inspection does not establish that arbitrary camera
additions/removals implement the full desired-state contract; that requires following
`update_camera_settings` and the separate camera-control path.

## Connection lifetime versus processing lifetime

The inspected WebSocket context exit closes the socket and cancels connection tasks;
it does not call the camera or pipeline managers' shutdown methods. Processing
shutdown is an application operation through `shutdown_all_processing`. Camera
groups have a separate `close_all_camera_groups` operation in SkellyCam.

This supports the intended server ownership. It is not a complete audit of all
application shutdown hooks or hardware cleanup behavior.

## Source map

Paths are relative to the workspace's `freemocap` repository unless marked SkellyCam.

| File | Evidence |
| --- | --- |
| `freemocap-ui/src/store/slices/mocap/mocap-thunks.ts` | `processMocapRecording` |
| `freemocap/api/http/mocap/mocap_router.py` | `process_mocap_recording` |
| `freemocap/core/tasks/mocap/posthoc_mocap_task.py` | Construction/publication of `ObservationRecordingRequest` |
| `freemocap/core/recording/result_processing/observation_publication.py` | First publication and existing-file path |
| `freemocap/core/pipeline/posthoc/processing_request.py` | `ProcessingRequest` defaults |
| `freemocap/core/pipeline/posthoc/stage_execution_plan.py` | `build_execution_plan`, `retained_run` |
| `freemocap/core/recording/parquet_storage/checkpoint_publication.py` | Retention and target-run publication |
| `freemocap/core/recording/parquet_storage/parquet_writer.py` | `publish_recording`, `publish_parquet` |
| `freemocap/api/http/realtime/realtime_router.py` | `pipeline_apply_endpoint` |
| `freemocap/app/freemocap_application.py` | Manager fields, `create_or_update_realtime_pipeline`, `shutdown_all_processing` |
| `freemocap/core/pipeline/realtime/realtime_pipeline_manager.py` | `create_pipeline` |
| `freemocap/api/websocket/websocket_server.py` | `__aexit__`, `run` |
| SkellyCam: `skellycam/core/camera_group/camera_group_manager.py` | Group creation/update and close operations |

## Next steps

- Define the exposed processing output policy using the existing planner/model,
  including which run and sensor groups overwrite affects.
- Trace camera-setting application before specifying complete realtime apply semantics.
- Keep these findings as a focused implementation backlog; do not claim that the
  intended declarative behavior is already implemented everywhere.
