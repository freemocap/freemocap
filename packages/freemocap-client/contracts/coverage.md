# HTTP operation coverage

Generated from the reviewed ledger; run `npm run coverage` after building.

Every row has a typed binding and an HTTP method/path conformance case in `http-conformance.mjs`.
This is coverage, not proof that every server-side effect was executed. Shared tests cover serialization,
errors, aborts, cancellation and asset ownership; compatibility records list actual integration workflows.

| Method | Path | Operation ID | Owner |
| --- | --- | --- | --- |
| GET | `/health` | `healthcheck_endpoint_health_get` | Core integration |
| POST | `/shutdown` | `shutdown_server_shutdown_post` | Core integration |
| POST | `/freemocap/capture/mocap/start` | `capture_start_mocap_recording` | Core integration |
| POST | `/freemocap/capture/calibration/start` | `capture_start_calibration_recording` | Core integration |
| POST | `/freemocap/capture/mocap/stop` | `capture_stop_mocap_recording` | Core integration |
| POST | `/freemocap/capture/calibration/stop` | `capture_stop_calibration_recording` | Core integration |
| POST | `/freemocap/recording-import` | `import_recording` | Core integration |
| POST | `/freemocap/recording-import/check-sync` | `check_import_frame_counts` | Core integration |
| POST | `/freemocap/recording-import/synchronize` | `synchronize_freemocap_recording_import_synchronize_post` | Core integration |
| POST | `/freemocap/recordings/{recording_id}/processing` | `process_recording_freemocap_recordings__recording_id__processing_post` | Core integration |
| GET | `/freemocap/recordings/{recording_id}/stages` | `saved_stages_freemocap_recordings__recording_id__stages_get` | Core integration |
| GET | `/freemocap/recordings/{recording_id}/runs/{run_id}/stages` | `run_stages_freemocap_recordings__recording_id__runs__run_id__stages_get` | Core integration |
| GET | `/freemocap/recordings` | `recordings_list_recordings` | Core integration |
| GET | `/freemocap/recordings/{recording_id}/status` | `recordings_get_recording_status` | Core integration |
| GET | `/freemocap/recordings/{recording_id}/media` | `recordings_read_unprocessed_media` | Core integration |
| GET | `/freemocap/recordings/{recording_id}/videos` | `recordings_list_videos` | Core integration |
| GET | `/freemocap/recordings/{recording_id}/videos/{video_id}` | `recordings_stream_video` | Core integration |
| GET | `/freemocap/recordings/{recording_id}/videos/{video_id}/browser` | `recordings_browser_video_stream` | Core integration |
| GET | `/freemocap/recordings/{recording_id}/parquet` | `recordings_get_recording_parquet` | Core integration |
| GET | `/freemocap/recordings/{recording_id}/calibration` | `recordings_get_recording_calibration` | Core integration |
| GET | `/freemocap/recordings/{recording_id}/playback/manifest` | `recordings_get_playback_manifest` | Core integration |
| GET | `/freemocap/recordings/{recording_id}/playback/bundle` | `recordings_get_recording_bundle` | Core integration |
| GET | `/freemocap/recordings/{recording_id}/playback/tracker-schema` | `recordings_get_tracker_schema` | Core integration |
| GET | `/freemocap/recordings/{recording_id}` | `describe_recording_freemocap_recordings__recording_id__get` | Core integration |
| GET | `/freemocap/recordings/{recording_id}/runs` | `list_recording_runs_freemocap_recordings__recording_id__runs_get` | Core integration |
| GET | `/freemocap/recordings/{recording_id}/runs/{run_id}/channels` | `list_run_channels_freemocap_recordings__recording_id__runs__run_id__channels_get` | Core integration |
| GET | `/freemocap/recordings/{recording_id}/export-options` | `get_export_options_freemocap_recordings__recording_id__export_options_get` | Core integration |
| GET | `/freemocap/recordings/{recording_id}/exports` | `list_exports_freemocap_recordings__recording_id__exports_get` | Core integration |
| POST | `/freemocap/recordings/{recording_id}/exports` | `create_export_freemocap_recordings__recording_id__exports_post` | Core integration |
| GET | `/freemocap/tasks` | `all_tasks_freemocap_tasks_get` | Core integration |
| GET | `/freemocap/tasks/{task_id}` | `get_task_freemocap_tasks__task_id__get` | Core integration |
| POST | `/freemocap/tasks/{task_id}/cancel` | `cancel_task_freemocap_tasks__task_id__cancel_post` | Core integration |
| POST | `/freemocap/tasks/cancel` | `cancel_tasks_freemocap_tasks_cancel_post` | Core integration |
| GET | `/freemocap/realtime/filter-config` | `temporal_config_status_freemocap_realtime_filter_config_get` | Core integration |
| PUT | `/freemocap/realtime/filter-config` | `update_temporal_config_freemocap_realtime_filter_config_put` | Core integration |
| GET | `/freemocap/realtime/config` | `running_pipeline_config_freemocap_realtime_config_get` | Core integration |
| POST | `/freemocap/realtime/apply` | `pipeline_apply_endpoint_freemocap_realtime_apply_post` | Core integration |
| POST | `/freemocap/realtime/reset-skeleton-fitter` | `reset_skeleton_fitter_endpoint_freemocap_realtime_reset_skeleton_fitter_post` | Core integration |
| DELETE | `/freemocap/realtime/pipelines/{pipeline_id}` | `stop_realtime_pipeline` | Core integration |
| DELETE | `/freemocap/realtime/pipelines` | `stop_realtime_pipelines` | Core integration |
| GET | `/freemocap/calibration/most-recent` | `most_recent_calibration_freemocap_calibration_most_recent_get` | Core integration |
| GET | `/freemocap/calibration/content` | `calibration_content_freemocap_calibration_content_get` | Core integration |
| POST | `/freemocap/calibration/transform` | `transform_calibration_freemocap_calibration_transform_post` | Core integration |
| GET | `/freemocap/calibration/files` | `calibration_file_options_freemocap_calibration_files_get` | Core integration |
| GET | `/freemocap/blender/detect` | `detect_blender_freemocap_blender_detect_get` | Core integration |
| POST | `/freemocap/blender/inspect` | `inspect_blender_endpoint_freemocap_blender_inspect_post` | Core integration |
| POST | `/freemocap/blender/addon/install` | `install_addon_freemocap_blender_addon_install_post` | Core integration |
| POST | `/freemocap/blender/open` | `open_in_blender_endpoint_freemocap_blender_open_post` | Core integration |
| GET | `/freemocap/ffmpeg/detect` | `detect_ffmpeg_freemocap_ffmpeg_detect_get` | Core integration |
| GET | `/freemocap/onnx/execution_providers` | `get_available_execution_providers_freemocap_onnx_execution_providers_get` | Core integration |
| GET | `/freemocap/onnx/session_providers` | `get_session_providers_freemocap_onnx_session_providers_get` | Core integration |
| POST | `/freemocap/telemetry/track` | `track_telemetry_event_freemocap_telemetry_track_post` | Core integration |
| POST | `/skellycam/camera/detect` | `cameras_detect_endpoint_skellycam_camera_detect_post` | SkellyCam |
| GET | `/skellycam/camera/microphone/detect` | `microphone_detect_endpoint_skellycam_camera_microphone_detect_get` | SkellyCam |
| POST | `/skellycam/camera/group/apply` | `camera_group_apply_post_endpoint_skellycam_camera_group_apply_post` | SkellyCam |
| POST | `/skellycam/camera/group/all/record/start` | `start_recording_skellycam_camera_group_all_record_start_post` | SkellyCam |
| POST | `/skellycam/camera/group/all/record/stop` | `stop_recording_skellycam_camera_group_all_record_stop_post` | SkellyCam |
| DELETE | `/skellycam/camera/group/close/all` | `close_all_camera_groups_skellycam_camera_group_close_all_delete` | SkellyCam |
| PUT | `/skellycam/camera/group/all/pause` | `pause_camera_groups_skellycam_camera_group_all_pause_put` | SkellyCam |
| DELETE | `/freemocap/streaming/outputs/{output_id}` | `streaming_stop_output` | Core integration |
| GET | `/freemocap/streaming/outputs` | `streaming_list_outputs` | Core integration |
| GET | `/freemocap/streaming/outputs/{output_id}` | `streaming_get_output` | Core integration |
| GET | `/freemocap/streaming/protocols` | `streaming_list_protocols` | Core integration |
| POST | `/freemocap/streaming/outputs` | `streaming_create_output` | Core integration |
| POST | `/freemocap/streaming/vmc/start` | `streaming_start_vmc` | Core integration |
| GET | `/freemocap/dlc/readiness` | `conversion_readiness_freemocap_dlc_readiness_get` | Core integration |
| POST | `/freemocap/dlc/inspect` | `inspect_model_freemocap_dlc_inspect_post` | Core integration |
| POST | `/freemocap/dlc/import` | `import_model_freemocap_dlc_import_post` | Core integration |
| GET | `/freemocap/dlc/import/{job_id}` | `import_status_freemocap_dlc_import__job_id__get` | Core integration |
| GET | `/freemocap/realtime/startup` | `realtime_startup_status` | Core integration |
| POST | `/freemocap/realtime/startup/stop` | `stop_realtime_startup` | Core integration |
| GET | `/freemocap/onnx/preparation/{pipeline_id}` | `onnx_preparation_status` | Core integration |
| POST | `/freemocap/onnx/preparation/{pipeline_id}` | `prepare_onnx` | Core integration |
| POST | `/freemocap/onnx/preparation/{pipeline_id}/stop` | `stop_onnx_preparation` | Core integration |
