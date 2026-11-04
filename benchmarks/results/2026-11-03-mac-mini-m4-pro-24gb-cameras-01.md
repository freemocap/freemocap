# Machine benchmark: mac-mini-m4-pro-24gb

Run: 2026-11-03T12:19:31.106477+00:00 | failed
CPU: Apple M4 Pro | RAM: 24 GiB

Shared desktop with other agents and apps active; AC power; no controlled thermal or cache warmup; one A68-1600W attached.

| Workload | Status | Measurement | Value |
|---|---|---|---|
| python / record | failed | recordings[0].cameras.3ece.measured_fps | 19.9298 |
| python / record | failed | recordings[0].cameras.3ece.p99_interval_ms | 66.3743 |
| python / record | failed | recordings[0].cameras.3ece.missing_frame_numbers | 0 |
| python / record | failed | stream.delivery.measured_fps | 19.8941 |
| python / record | failed | stream.delivery.p99_interval_ms | 78.2156 |
| python / record | failed | stream.delivery.missing_frame_numbers | 0 |
| python / record | failed | stream.source_frames_received.measured_fps | 19.963 |
| python / record | failed | stream.source_frames_received.p99_interval_ms | 66.4727 |
| python / record | failed | stream.source_frames_received.missing_frame_numbers | 0 |
| python / record | failed | stream.duplicate_source_frames | 0 |
| python / pause-resume | passed | stream.delivery.measured_fps | 19.9484 |
| python / pause-resume | passed | stream.delivery.p99_interval_ms | 73.5261 |
| python / pause-resume | passed | stream.delivery.missing_frame_numbers | 0 |
| python / pause-resume | passed | stream.source_frames_received.measured_fps | 19.8617 |
| python / pause-resume | passed | stream.source_frames_received.p99_interval_ms | 63.0422 |
| python / pause-resume | passed | stream.source_frames_received.missing_frame_numbers | 0 |
| python / pause-resume | passed | stream.duplicate_source_frames | 0 |
| python / close-during-recording | failed | recording.cameras.3ece.measured_fps | 19.9585 |
| python / close-during-recording | failed | recording.cameras.3ece.p99_interval_ms | 65.7162 |
| python / close-during-recording | failed | recording.cameras.3ece.missing_frame_numbers | 0 |
| python / repeat-apply | passed | stream.delivery.measured_fps | 19.7386 |
| python / repeat-apply | passed | stream.delivery.p99_interval_ms | 76.1192 |
| python / repeat-apply | passed | stream.delivery.missing_frame_numbers | 0 |
| python / repeat-apply | passed | stream.source_frames_received.measured_fps | 19.7965 |
| python / repeat-apply | passed | stream.source_frames_received.p99_interval_ms | 62.9678 |
| python / repeat-apply | passed | stream.source_frames_received.missing_frame_numbers | 0 |
| python / repeat-apply | passed | stream.duplicate_source_frames | 0 |
| python / change-backend | failed | measurements | unavailable |
| python / disconnect-reconnect-stream | passed | stream.delivery.measured_fps | 19.9621 |
| python / disconnect-reconnect-stream | passed | stream.delivery.p99_interval_ms | 77.9132 |
| python / disconnect-reconnect-stream | passed | stream.delivery.missing_frame_numbers | 0 |
| python / disconnect-reconnect-stream | passed | stream.source_frames_received.measured_fps | 19.8839 |
| python / disconnect-reconnect-stream | passed | stream.source_frames_received.p99_interval_ms | 63.663 |
| python / disconnect-reconnect-stream | passed | stream.source_frames_received.missing_frame_numbers | 0 |
| python / disconnect-reconnect-stream | passed | stream.duplicate_source_frames | 0 |
| python / exposure | failed | before.delivery.measured_fps | 19.7593 |
| python / exposure | failed | before.delivery.p99_interval_ms | 76.1239 |
| python / exposure | failed | before.delivery.missing_frame_numbers | 0 |
| python / exposure | failed | before.source_frames_received.measured_fps | 19.8562 |
| python / exposure | failed | before.source_frames_received.p99_interval_ms | 63.7858 |
| python / exposure | failed | before.source_frames_received.missing_frame_numbers | 0 |
| python / exposure | failed | before.duplicate_source_frames | 0 |
| python / rotation | passed | before.delivery.measured_fps | 16.7018 |
| python / rotation | passed | before.delivery.p99_interval_ms | 77.5412 |
| python / rotation | passed | before.delivery.missing_frame_numbers | 0 |
| python / rotation | passed | before.source_frames_received.measured_fps | 16.8357 |
| python / rotation | passed | before.source_frames_received.p99_interval_ms | 67.0667 |
| python / rotation | passed | before.source_frames_received.missing_frame_numbers | 0 |
| python / rotation | passed | before.duplicate_source_frames | 0 |
| python / rotation | passed | after.delivery.measured_fps | 19.0094 |
| python / rotation | passed | after.delivery.p99_interval_ms | 77.7629 |
| python / rotation | passed | after.delivery.missing_frame_numbers | 0 |
| python / rotation | passed | after.source_frames_received.measured_fps | 18.7341 |
| python / rotation | passed | after.source_frames_received.p99_interval_ms | 66.6398 |
| python / rotation | passed | after.source_frames_received.missing_frame_numbers | 0 |
| python / rotation | passed | after.duplicate_source_frames | 0 |
| python / exposure-auto | passed | before.delivery.measured_fps | 20.3962 |
| python / exposure-auto | passed | before.delivery.p99_interval_ms | 77.5025 |
| python / exposure-auto | passed | before.delivery.missing_frame_numbers | 0 |
| python / exposure-auto | passed | before.source_frames_received.measured_fps | 19.8478 |
| python / exposure-auto | passed | before.source_frames_received.p99_interval_ms | 64.063 |
| python / exposure-auto | passed | before.source_frames_received.missing_frame_numbers | 0 |
| python / exposure-auto | passed | before.duplicate_source_frames | 0 |
| python / exposure-auto | passed | after.delivery.measured_fps | 20.4248 |
| python / exposure-auto | passed | after.delivery.p99_interval_ms | 74.4913 |
| python / exposure-auto | passed | after.delivery.missing_frame_numbers | 0 |
| python / exposure-auto | passed | after.source_frames_received.measured_fps | 19.8733 |
| python / exposure-auto | passed | after.source_frames_received.p99_interval_ms | 62.8599 |
| python / exposure-auto | passed | after.source_frames_received.missing_frame_numbers | 0 |
| python / exposure-auto | passed | after.duplicate_source_frames | 0 |
| python / exposure-recommend | passed | before.delivery.measured_fps | 20.4078 |
| python / exposure-recommend | passed | before.delivery.p99_interval_ms | 80.7652 |
| python / exposure-recommend | passed | before.delivery.missing_frame_numbers | 0 |
| python / exposure-recommend | passed | before.source_frames_received.measured_fps | 19.8509 |
| python / exposure-recommend | passed | before.source_frames_received.p99_interval_ms | 63.0064 |
| python / exposure-recommend | passed | before.source_frames_received.missing_frame_numbers | 0 |
| python / exposure-recommend | passed | before.duplicate_source_frames | 0 |
| python / exposure-recommend | passed | after.delivery.measured_fps | 20.2676 |
| python / exposure-recommend | passed | after.delivery.p99_interval_ms | 76.8579 |
| python / exposure-recommend | passed | after.delivery.missing_frame_numbers | 0 |
| python / exposure-recommend | passed | after.source_frames_received.measured_fps | 19.8319 |
| python / exposure-recommend | passed | after.source_frames_received.p99_interval_ms | 63.4155 |
| python / exposure-recommend | passed | after.source_frames_received.missing_frame_numbers | 0 |
| python / exposure-recommend | passed | after.duplicate_source_frames | 0 |
| python / resolution | passed | before.delivery.measured_fps | 20.1354 |
| python / resolution | passed | before.delivery.p99_interval_ms | 72.2132 |
| python / resolution | passed | before.delivery.missing_frame_numbers | 0 |
| python / resolution | passed | before.source_frames_received.measured_fps | 19.8226 |
| python / resolution | passed | before.source_frames_received.p99_interval_ms | 63.5199 |
| python / resolution | passed | before.source_frames_received.missing_frame_numbers | 0 |
| python / resolution | passed | before.duplicate_source_frames | 0 |
| python / resolution | passed | after.delivery.measured_fps | 19.8611 |
| python / resolution | passed | after.delivery.p99_interval_ms | 71.8298 |
| python / resolution | passed | after.delivery.missing_frame_numbers | 0 |
| python / resolution | passed | after.source_frames_received.measured_fps | 19.8481 |
| python / resolution | passed | after.source_frames_received.p99_interval_ms | 62.9653 |
| python / resolution | passed | after.source_frames_received.missing_frame_numbers | 0 |
| python / resolution | passed | after.duplicate_source_frames | 0 |
| python / repeat-record-start | failed | measurements | unavailable |
| python / stop-without-recording | passed | stream.delivery.measured_fps | 19.9908 |
| python / stop-without-recording | passed | stream.delivery.p99_interval_ms | 76.8964 |
| python / stop-without-recording | passed | stream.delivery.missing_frame_numbers | 0 |
| python / stop-without-recording | passed | stream.source_frames_received.measured_fps | 19.873 |
| python / stop-without-recording | passed | stream.source_frames_received.p99_interval_ms | 63.5883 |
| python / stop-without-recording | passed | stream.source_frames_received.missing_frame_numbers | 0 |
| python / stop-without-recording | passed | stream.duplicate_source_frames | 0 |
| python / pause-during-recording | passed | stream.delivery.measured_fps | 19.7127 |
| python / pause-during-recording | passed | stream.delivery.p99_interval_ms | 71.4686 |
| python / pause-during-recording | passed | stream.delivery.missing_frame_numbers | 0 |
| python / pause-during-recording | passed | stream.source_frames_received.measured_fps | 19.834 |
| python / pause-during-recording | passed | stream.source_frames_received.p99_interval_ms | 63.4248 |
| python / pause-during-recording | passed | stream.source_frames_received.missing_frame_numbers | 0 |
| python / pause-during-recording | passed | stream.duplicate_source_frames | 0 |
| rust / record | failed | measurements | unavailable |
| rust / pause-resume | failed | measurements | unavailable |
| rust / close-during-recording | failed | measurements | unavailable |
| rust / repeat-apply | failed | measurements | unavailable |
| rust / change-backend | failed | measurements | unavailable |
| rust / disconnect-reconnect-stream | failed | measurements | unavailable |
| rust / exposure | failed | measurements | unavailable |
| rust / rotation | failed | measurements | unavailable |
| rust / exposure-auto | failed | measurements | unavailable |
| rust / exposure-recommend | failed | measurements | unavailable |
| rust / resolution | failed | measurements | unavailable |
| rust / repeat-record-start | failed | measurements | unavailable |
| rust / stop-without-recording | failed | measurements | unavailable |
| rust / pause-during-recording | failed | measurements | unavailable |

Recorded failures:

- python / record: AssertionError: Recording failed capture/video checks
- python / close-during-recording: AssertionError: Closing cameras left an incomplete recording
- python / change-backend: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- python / exposure: AssertionError: Requested exposure was not applied to 3ece
- python / repeat-record-start: ApiResponseError: HTTP 500: {"detail":"Timed out waiting for cameras to pause: ['3ece']"}
- rust / record: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- rust / pause-resume: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- rust / close-during-recording: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- rust / repeat-apply: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- rust / change-backend: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- rust / disconnect-reconnect-stream: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- rust / exposure: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- rust / rotation: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- rust / exposure-auto: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- rust / exposure-recommend: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- rust / resolution: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- rust / repeat-record-start: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- rust / stop-without-recording: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- rust / pause-during-recording: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
