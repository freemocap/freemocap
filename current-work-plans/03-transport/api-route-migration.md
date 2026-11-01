# API route and caller migration inventory

Baseline: core worktree commit `64a068ff`, 2026-10-31. This source inventory
includes routes hidden from Swagger and the mounted SkellyCam router. The running
server in the original checkout is not the acceptance server for this worktree.
The [approved checklist](api-cleanup-checklist.md) governs execution.

## Reading the inventory

Core paths below start with `/freemocap` unless marked root. Router modules live
in `freemocap/api/http/`; functions named below are their existing handlers.
`R` means `/recordings/{recording_id}`. Every `R` route accepts the optional
`recording_parent_directory`. The function and response behavior remain the
baseline unless a change is explicitly described.

Caller groups (paths relative to `freemocap-ui/src`):

- **Playback:** `constants/server-urls.ts`, `store/slices/playback-data/`,
  `store/slices/recording-status/`, `components/playback/`,
  `components/viewport3d/RecordingPlaybackProvider.tsx`, `services/recording/`.
- **Exports:** `components/mocap-setup/mocap-scientific-settings.tsx`,
  `mocap-csv-settings.tsx`, `store/slices/mocap/mocap-thunks.ts`, and backend
  `core/pipeline/dataflow/recording_pipeline.py`, `posthoc/export_completion.py`.
- **Mocap:** `store/slices/mocap/mocap-thunks.ts`,
  `components/mocap-setup/mocap-stage-selection.tsx`, import/sync UI callers of
  those thunks, and `constants/server-urls.ts`.
- **Calibration:** `store/slices/calibration/calibration-thunks.ts`,
  `components/mocap-setup/RecordingCalibrationOptions.tsx`, calibration UI and
  associated URL constants.
- **Tasks:** `store/slices/pipelines/pipelines-thunks.ts`,
  `services/server/task-progress.ts`, export component polling, sync thunks,
  `services/server/transport/` schemas and the WebSocket server progress sender.
- **Application:** connection panel/hooks, server URL constants, Electron
  `main/services/python-server.ts`, transport service, server-client consumers.
- **Blender/tools:** URL constants and all callers of blender detect/export/open,
  explicit inspect/install requests, FFmpeg and telemetry service callers.
- **Cameras:** URL constants, camera-group control thunks and SkellyCam's own UI;
  SkellyCam implementation changes require a separate repository handoff.

Before each migration, search both endpoint literals and the named URL keys;
also update tests, the standalone Parquet HTML viewer, and test-server harnesses.
Callers can be indirect through thunks rather than literal URL users.

## Recording and export routes

| Current method/path | Existing handler and operation | Target | Callers / acceptance |
| --- | --- | --- | --- |
| GET `/playback/recordings` | `playback/playback_router.list_recordings`; directory discovery/status | GET `/recordings` | Playback; same-name recordings in different roots, partial layouts |
| GET `/playback/{recording_id}/media` | `read_unprocessed_media`; video associations/timelines | GET `R/media` | Playback; raw-only and annotated media |
| GET `/playback/{recording_id}/manifest` | `get_playback_manifest`; `playback_manifest` rendering projection | GET `R/playback/manifest` | Playback; independent clocks and saved model definitions |
| GET `/playback/{recording_id}/status` | `get_recording_status`; `compute_recording_status` | GET `R/status` | Playback and Blender; retain readiness fields |
| GET `/playback/{recording_id}/videos` | `list_videos`; source inventory | GET `R/videos` | Playback; source preference and invalid groups |
| GET `/playback/{recording_id}/videos/{video_id}` | `stream_video`; ranged file delivery | GET `R/videos/{video_id}` | Playback; byte ranges, filename encoding, original/annotated source |
| GET `/playback/{recording_id}/videos/{video_id}/browser` | `browser_video_stream`; compatibility encoding | GET `R/videos/{video_id}/browser` | Browser video module; cancellation and response cleanup |
| GET `/playback/{recording_id}/parquet` | `get_recording_parquet`; revision-bound download | GET `R/parquet` | Playback worker; stale revision and file release |
| GET `/playback/{recording_id}/calibration` | `get_recording_calibration`; saved geometry | GET `R/calibration` | Calibration + Playback; absent/invalid calibration |
| GET `/playback/{recording_id}/tracker-schema` | `get_tracker_schema`; tracked-point/render connections | GET `R/playback/tracker-schema` | Playback; this is a viewer projection, not all recording channels |
| GET `/playback/{recording_id}/bundle` | `get_recording_bundle`; independent resource error collection | GET `R/playback/bundle` | Playback; partial failures must not discard usable resources |
| GET `/playback/viewer` (hidden) | `parquet_viewer`; standalone HTML | Retain hidden utility until its consumer moves | HTML viewer smoke test; no new scientific wording |
| GET `/playback/parquet?path=...` (hidden) | `serve_parquet`; explicit file lookup | Retain hidden utility with shared read lease | HTML viewer; busy-owner and extension checks |
| GET `/exports/scientific` | `posthoc/exports_router.scientific_selection`; available channel selections | GET `R/export-options` | Exports; missing saved result and run selection |
| GET `/exports/tall-csv` | `selection`; saved run/revision inventory | Same options response, explicit tall CSV capability | Exports; preserve all-row selection semantics |
| POST `/exports/scientific` | `save_scientific` → `export_jobs.run_job` → `export_scientific` | POST `R/exports`, kind `channels` | Exports; stale revision, unavailable channels, cancellation, retry |
| POST `/exports/tall-csv` | `save_tall_csv` → `export_tall_csv` | POST `R/exports`, kind `tall_csv` | Exports; now asynchronous, preserve exact table contents |
| GET `/exports/jobs/{job_id}` | `get_export_job` → `job_state` | GET `/tasks/{task_id}` | Tasks; retained completion/failure and job eviction |
| POST `/exports/jobs/{job_id}/cancel` | `stop_export_job` → `cancel_job` | POST `/tasks/{task_id}/cancel` | Tasks; cancellation leaves published files intact |
| POST `/blender/export` | `blender/blender_router.export_to_blender_endpoint`; package prep/export/optional open | POST `R/exports`, kind `blender` | Blender/tools; preserve all executable, package, run and configuration choices |
| GET `/mocap/recording/process/stages` | `mocap/mocap_router.saved_mocap_stages`; saved stage inventory | GET `R/stages` (aggregate chooser) and `R/runs/{run_id}/stages` (single run) | Mocap stage chooser; explicit group/source-run prerequisites |

New general reads: GET `R` describes recording identity and resource links;
GET `R/runs` and `R/runs/{run_id}/channels` read saved descriptors without rendering
composition; GET `R/exports` inventories published artifacts after task eviction
or server restart. File links must resolve safely inside the recording/export
layout and retain the parent query. Artifact inventory preserves per-file source
revision/hash and distinguishes stale outputs from current outputs.

## Commands and task routes

| Current method/path | Existing handler/operation | Target | Callers / acceptance |
| --- | --- | --- | --- |
| GET `/posthoc/tasks` | `posthoc/tasks_router.task_snapshot`; posthoc registry | GET `/tasks` | Tasks; same registry state over HTTP and WS |
| POST `/mocap/recording/process` | `process_mocap_recording`; saved-stage validation and create pipeline | POST `R/processing`, kind `mocap` | Mocap; selected run/group, stage bounds, keep/overwrite |
| POST `/calibration/recording/calibrate` | `calibration/calibration_router.calibrate_recording`; create calibration pipeline | POST `R/processing`, kind `calibration` | Calibration; retain its config and task result |
| POST `/mocap/recording/start` | `start_mocap_recording`; start cameras | POST `/capture/mocap/start` | Mocap; retain destination and configuration |
| POST `/mocap/recording/stop` | `stop_mocap_recording`; stop and launch processing | POST `/capture/mocap/stop` | Mocap; typed IDs/paths, preserve stop-then-process behavior |
| POST `/calibration/recording/start` | `start_calibration_recording`; start + publish board-buffer state | POST `/capture/calibration/start` | Calibration; reject occupied destination, retain buffering |
| POST `/calibration/recording/stop` | `stop_calibration_recording`; stop and calibration processing | POST `/capture/calibration/stop` | Calibration; typed task reference and retained destination |
| POST `/mocap/recording/check_sync` | `check_video_sync`; frame-count compatibility inspection | POST `/recording-import/check-sync` | Mocap; do not claim equal counts establish synchronization |
| POST `/mocap/recording/synchronize` | `synchronize_videos`; stage inputs and launch sync job | POST `/recording-import/synchronize` | Mocap + Tasks; files from different directories, job result |
| GET `/mocap/recording/synchronize/{job_id}` | `get_synchronize_result`; completed sync output | GET `/tasks/{task_id}` with typed result | Tasks; queued/running state replaces HTTP 425 polling |
| POST `/mocap/recording/import` | `import_videos`; copy original or validated sync-job output | POST `/recording-import` | Mocap; selected inputs must match sync job, collision handling |
| DELETE `/mocap/posthoc/pipelines/{pipeline_id}` | `cancel_posthoc_pipeline`; type-scoped cancellation | POST `/tasks/{task_id}/cancel` | Tasks; individual ID, preserve terminal status |
| DELETE `/calibration/posthoc/pipelines/{pipeline_id}` | Same handler name, calibration-scoped manager operation | POST `/tasks/{task_id}/cancel` | Tasks; preserve task type |
| DELETE `/mocap/posthoc/pipelines` | `cancel_posthoc_pipelines`; stop all mocap | POST `/tasks/cancel` with explicit kind `mocap` | Tasks; never broaden cancellation scope |
| DELETE `/calibration/posthoc/pipelines` | `cancel_posthoc_pipelines`; stop all calibration | POST `/tasks/cancel` with explicit kind `calibration` | Tasks; never broaden cancellation scope |
| DELETE `/mocap/synchronization/jobs/{job_id}` | `cancel_synchronization_job`; stop sync worker | POST `/tasks/{task_id}/cancel` | Tasks; preserve temp-output cleanup rules |
| GET `/realtime/config` | `realtime/realtime_router.running_pipeline_config` | Retain | Calibration/realtime controls; existing casing and config |
| POST `/realtime/apply` | `pipeline_apply_endpoint`; create/update and attach camera group | Retain | Camera/realtime controls; pipeline and group IDs |
| POST `/realtime/reset-skeleton-fitter` | `reset_skeleton_fitter_endpoint`; refit command | Retain | Realtime; correct docs for actual state delivery |
| DELETE `/mocap/realtime/pipelines/{pipeline_id}` | `cancel_realtime_pipeline` | DELETE `/realtime/pipelines/{pipeline_id}` | Application; retain ID-scoped behavior |
| DELETE `/mocap/realtime/pipelines` | `cancel_realtime_pipelines` | DELETE `/realtime/pipelines` | Application; explicit all-realtime scope |

## Remaining registered capabilities

| Method/path | Handler and disposition | Acceptance |
| --- | --- | --- |
| GET root `/health` | `app/health.healthcheck_endpoint`; retain App | Application health polling remains read-only |
| GET root `/shutdown` | `app/shutdown.shutdown_server`; change to POST, update all callers | Graceful server teardown; no process-ownership requirement |
| GET root `/` and `/favicon.ico` (hidden) | `app/app.py` redirect and icon; retain | Docs redirect and icon |
| WS root `/websocket/connect` | `api/websocket/websocket_connect.websocket_server_connect`; retain | Frames/logs/state/task status, disconnect isolation |
| GET `/calibration/most-recent` | `most_recent_calibration`; retain calibration tools | Current calibration discovery |
| GET `/calibration/content` | `calibration_content`; retain explicit file read | Parsed calibration and missing-file response |
| GET `/calibration/files` | `calibration_file_options`; retain until recording selector caller migrates | Recording-associated file choices and ambiguity errors |
| POST `/calibration/transform` | `transform_calibration`; retain calibration tools | Live and saved transform handling and revision conflicts |
| GET `/blender/detect` | `detect_blender`; retain Blender | Executable detection |
| POST `/blender/inspect` | `inspect_blender_endpoint`; retain Blender | Package/executable inspection |
| POST `/blender/addon/install` | `install_addon`; retain Blender | Explicit package installation request |
| POST `/blender/open` | `open_in_blender_endpoint`; retain Blender | Open existing output with package prep |
| GET `/ffmpeg/detect` | `ffmpeg/ffmpeg_router.detect_ffmpeg`; retain FFmpeg | Executable detection |
| POST `/telemetry/track` | `telemetry/telemetry_router.track_telemetry_event`; retain Telemetry | Existing telemetry payload and opt-in behavior |
| POST `/skellycam/camera/detect` | `cameras_detect_endpoint`; retain Cameras | Backend/filter selection |
| GET `/skellycam/camera/microphone/detect` | `microphone_detect_endpoint`; retain Cameras | Microphone listing |
| POST `/skellycam/camera/group/apply` | `camera_group_apply_post_endpoint`; retain Cameras | Group create/update |
| POST `/skellycam/camera/group/all/record/start` | `start_recording`; retain Cameras | Existing destination/microphone configuration |
| GET `/skellycam/camera/group/all/record/stop` | `stop_recording`; SkellyCam stage changes method to POST | Standalone and core callers, recording statistics |
| DELETE `/skellycam/camera/group/close/all` | `close_all_camera_groups`; retain Cameras | Group cleanup |
| GET `/skellycam/camera/group/all/pause_unpause` | `pause_camera_groups`; replace with explicit desired pause state in SkellyCam stage | Repeat requests must not toggle accidentally |

## Contract decisions

1. Keep old resource/control paths as hidden deprecated adapters during this
   migration where needed for separately running clients. They call the same
   implementation; no POST redirects or parallel business logic. Remove them
   only after caller inventory/tests establish retirement. Unsafe GET mutations
   receive a coordinated caller change rather than indefinite compatibility.
2. Export creation uses a discriminator `kind`: `channels`, `tall_csv`, `blender`.
   Channel formats remain `wide_csv`, `npy`, `npz`, `notebook`; preserve existing
   selection restrictions and the legacy explicit-channel override at input.
   Tall CSV retains whole-run selection. Blender retains its specific options.
3. Processing uses `kind: mocap | calibration` with the corresponding typed
   configuration. Route identity supplies the recording; no conflicting path in
   the new request body. A legacy body adapter resolves the same canonical path.
4. Tasks expose typed state, kind, recording when available, optional source
   run/revision, progress, errors and result. Prefix adapter task IDs by executor
   kind if needed to avoid collisions. Preserve one executor per accepted job.
   Terminal state is retained for a bounded server session; server restart changes
   the instance identity. Export files have a separate durable inventory.
5. Readers acquire recording leases through response completion. Standalone
   export work acquires a cancellable read lease, then the existing export lock;
   processing reservation revokes readers and waits for release. Internal exports
   from the owning processing task must not acquire a conflicting external lease.
   Calibration mutations and Blender reads use the same ownership policy at their
   operation boundary. HTTP acceptance alone never holds a lease for later work.
6. Use ordered Swagger tags: App, Recordings, Recording results, Recording media,
   Recording calibration, Playback, Recording exports, Recording processing,
   Tasks, Capture, Recording import, Realtime processing, Calibration tools,
   Blender, Cameras, FFmpeg, Telemetry. Document WebSocket separately. Define
   typed responses, unique operation IDs, 202 for accepted asynchronous work,
   missing resource and busy/stale errors, and partial-resource error collections.
7. New settings use `export_options` / `exportOptions`, `exportFormats`,
   `exportChannels` and related explicit names. Accept supported historical keys
   only through input migration; conflicting old/new values are rejected.
   NumPy `scientific_provenance` remains an explicit Forge compatibility boundary
   until checklist items 10–11, not an incidental core format rewrite.

## Acceptance test map

Existing test paths below are under `freemocap/tests` unless marked UI. They are
entry points to relevant coverage, not a claim that every new assertion exists.

| Contracts | Existing checks and required additions |
| --- | --- |
| Registration/schema | `test_hardware_server_harness.py`; add source inventory completeness and canonical route/OpenAPI contract assertions |
| Identity/ownership | `test_recording_access.py`; add default/custom roots, same-name recordings, invalid Windows/POSIX IDs, symlinks, cooperative export cancellation |
| Recording resources/playback | `test_playback_data.py`, `test_playback_timelines.py`, `test_browser_video_http.py`, `test_sequential_playback.py`; UI `app-playback.spec.ts`, `parquet-playback.spec.ts` |
| Exports | `test_scientific_export_api.py`, `test_export_preview.py`, `test_tall_csv_export.py`, `test_numpy_dataset_export.py`, `test_export_completion.py`, `test_blender_export.py`; UI `scientific-exports.spec.ts` |
| Task lifecycle | `test_posthoc_terminal_progress.py`, `test_pipeline_cancellation.py`; add executor-adapter state/cancel/reconnect and HTTP/WS equivalence |
| Capture/calibration/import | `http/test_calibration_router_recording_state.py`, `http/test_mocap_router_import.py`, `test_calibration_file_options.py`, calibration metadata tests; add typed stop responses |
| Realtime/shutdown | `http/test_realtime_config.py`, `test_realtime_lifecycle.py`; UI `server-stop.spec.ts`, Electron `python-server.test.cjs` |
| WebSocket | `test_websocket_disconnect.py`, `test_camera_only_websocket.py`; add malformed feedback and independent second-client assertions |
| Naming/persistence | Existing export and tensor round trips plus intentional historical settings/dataset fixtures; reject ambiguous aliases and compare values/metadata |

No production URL changes are part of the inventory item. Each later checklist
item migrates production code, actual callers, and its focused acceptance checks
together. Hardware, Blender, browser, and full recording checks must be reported
as run, failed, or unavailable; mock-only checks do not establish those outcomes.
