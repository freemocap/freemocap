# Machine benchmark: mac-mini-m4-pro-24gb

Run: 2026-11-06T12:44:27.324765+00:00 | failed
CPU: Apple M4 Pro | RAM: 24 GiB

AC power; shared desktop; A68-1600W and Global Shutter Camera attached; no existing FreeMoCap camera processes found; sequential suites; latest sfn26 Core 3ae9842d and SkellyCam f482a4fc

| Workload | Status | Measurement | Value |
|---|---|---|---|
| python / record | failed | recordings[0].cameras.camera[0].measured_fps | 24.8904 |
| python / record | failed | recordings[0].cameras.camera[0].p99_interval_ms | 50.5183 |
| python / record | failed | recordings[0].cameras.camera[0].missing_frame_numbers | 0 |
| python / record | failed | stream.delivery.measured_fps | 25.0662 |
| python / record | failed | stream.delivery.p99_interval_ms | 73.5645 |
| python / record | failed | stream.delivery.missing_frame_numbers | 0 |
| python / record | failed | stream.source_frames_received.measured_fps | 24.9465 |
| python / record | failed | stream.source_frames_received.p99_interval_ms | 50.4793 |
| python / record | failed | stream.source_frames_received.missing_frame_numbers | 0 |
| python / record | failed | stream.duplicate_source_frames | 0 |
| python / record | passed | recordings[0].cameras.camera[0].measured_fps | 29.9047 |
| python / record | passed | recordings[0].cameras.camera[0].p99_interval_ms | 50.0881 |
| python / record | passed | recordings[0].cameras.camera[0].missing_frame_numbers | 0 |
| python / record | passed | stream.delivery.measured_fps | 29.8848 |
| python / record | passed | stream.delivery.p99_interval_ms | 66.467 |
| python / record | passed | stream.delivery.missing_frame_numbers | 0 |
| python / record | passed | stream.source_frames_received.measured_fps | 29.9671 |
| python / record | passed | stream.source_frames_received.p99_interval_ms | 50.0927 |
| python / record | passed | stream.source_frames_received.missing_frame_numbers | 0 |
| python / record | passed | stream.duplicate_source_frames | 0 |
| python / record | failed | recordings[0].cameras.camera[1].measured_fps | 24.9155 |
| python / record | failed | recordings[0].cameras.camera[1].p99_interval_ms | 67.0705 |
| python / record | failed | recordings[0].cameras.camera[1].missing_frame_numbers | 0 |
| python / record | failed | recordings[0].cameras.camera[0].measured_fps | 24.9155 |
| python / record | failed | recordings[0].cameras.camera[0].p99_interval_ms | 51.087 |
| python / record | failed | recordings[0].cameras.camera[0].missing_frame_numbers | 0 |
| python / record | failed | stream.delivery.measured_fps | 24.8978 |
| python / record | failed | stream.delivery.p99_interval_ms | 72.8586 |
| python / record | failed | stream.delivery.missing_frame_numbers | 0 |
| python / record | failed | stream.source_frames_received.measured_fps | 25.0429 |
| python / record | failed | stream.source_frames_received.p99_interval_ms | 58.4213 |
| python / record | failed | stream.source_frames_received.missing_frame_numbers | 0 |
| python / record | failed | stream.duplicate_source_frames | 0 |
| python / add-camera | passed | stream.delivery.measured_fps | 25.1897 |
| python / add-camera | passed | stream.delivery.p99_interval_ms | 70.4731 |
| python / add-camera | passed | stream.delivery.missing_frame_numbers | 0 |
| python / add-camera | passed | stream.source_frames_received.measured_fps | 25.055 |
| python / add-camera | passed | stream.source_frames_received.p99_interval_ms | 57.8383 |
| python / add-camera | passed | stream.source_frames_received.missing_frame_numbers | 0 |
| python / add-camera | passed | stream.duplicate_source_frames | 0 |
| python / remove-camera | passed | stream.delivery.measured_fps | 24.7905 |
| python / remove-camera | passed | stream.delivery.p99_interval_ms | 72.4011 |
| python / remove-camera | passed | stream.delivery.missing_frame_numbers | 0 |
| python / remove-camera | passed | stream.source_frames_received.measured_fps | 24.8757 |
| python / remove-camera | passed | stream.source_frames_received.p99_interval_ms | 50.1727 |
| python / remove-camera | passed | stream.source_frames_received.missing_frame_numbers | 0 |
| python / remove-camera | passed | stream.duplicate_source_frames | 0 |
| python / pause-resume | passed | stream.delivery.measured_fps | 25.4372 |
| python / pause-resume | passed | stream.delivery.p99_interval_ms | 69.4608 |
| python / pause-resume | passed | stream.delivery.missing_frame_numbers | 0 |
| python / pause-resume | passed | stream.source_frames_received.measured_fps | 25.572 |
| python / pause-resume | passed | stream.source_frames_received.p99_interval_ms | 58.0379 |
| python / pause-resume | passed | stream.source_frames_received.missing_frame_numbers | 0 |
| python / pause-resume | passed | stream.duplicate_source_frames | 0 |
| python / close-during-recording | failed | recording.cameras.camera[1].measured_fps | 24.882 |
| python / close-during-recording | failed | recording.cameras.camera[1].p99_interval_ms | 71.3817 |
| python / close-during-recording | failed | recording.cameras.camera[1].missing_frame_numbers | 0 |
| python / close-during-recording | failed | recording.cameras.camera[0].measured_fps | 24.8834 |
| python / close-during-recording | failed | recording.cameras.camera[0].p99_interval_ms | 50.4272 |
| python / close-during-recording | failed | recording.cameras.camera[0].missing_frame_numbers | 0 |
| python / repeat-apply | passed | stream.delivery.measured_fps | 24.8616 |
| python / repeat-apply | passed | stream.delivery.p99_interval_ms | 70.2042 |
| python / repeat-apply | passed | stream.delivery.missing_frame_numbers | 0 |
| python / repeat-apply | passed | stream.source_frames_received.measured_fps | 24.4027 |
| python / repeat-apply | passed | stream.source_frames_received.p99_interval_ms | 63.8248 |
| python / repeat-apply | passed | stream.source_frames_received.missing_frame_numbers | 0 |
| python / repeat-apply | passed | stream.duplicate_source_frames | 0 |
| python / change-backend | failed | measurements | unavailable |
| python / disconnect-reconnect-stream | passed | stream.delivery.measured_fps | 24.9551 |
| python / disconnect-reconnect-stream | passed | stream.delivery.p99_interval_ms | 70.4384 |
| python / disconnect-reconnect-stream | passed | stream.delivery.missing_frame_numbers | 0 |
| python / disconnect-reconnect-stream | passed | stream.source_frames_received.measured_fps | 25.0655 |
| python / disconnect-reconnect-stream | passed | stream.source_frames_received.p99_interval_ms | 57.6575 |
| python / disconnect-reconnect-stream | passed | stream.source_frames_received.missing_frame_numbers | 0 |
| python / disconnect-reconnect-stream | passed | stream.duplicate_source_frames | 0 |
| python / exposure | failed | before.delivery.measured_fps | 25.0297 |
| python / exposure | failed | before.delivery.p99_interval_ms | 73.2972 |
| python / exposure | failed | before.delivery.missing_frame_numbers | 0 |
| python / exposure | failed | before.source_frames_received.measured_fps | 25.0539 |
| python / exposure | failed | before.source_frames_received.p99_interval_ms | 57.1123 |
| python / exposure | failed | before.source_frames_received.missing_frame_numbers | 0 |
| python / exposure | failed | before.duplicate_source_frames | 0 |
| python / rotation | passed | before.delivery.measured_fps | 25.025 |
| python / rotation | passed | before.delivery.p99_interval_ms | 69.204 |
| python / rotation | passed | before.delivery.missing_frame_numbers | 0 |
| python / rotation | passed | before.source_frames_received.measured_fps | 25.0849 |
| python / rotation | passed | before.source_frames_received.p99_interval_ms | 57.5854 |
| python / rotation | passed | before.source_frames_received.missing_frame_numbers | 0 |
| python / rotation | passed | before.duplicate_source_frames | 0 |
| python / rotation | passed | after.delivery.measured_fps | 24.9419 |
| python / rotation | passed | after.delivery.p99_interval_ms | 70.9233 |
| python / rotation | passed | after.delivery.missing_frame_numbers | 0 |
| python / rotation | passed | after.source_frames_received.measured_fps | 24.9061 |
| python / rotation | passed | after.source_frames_received.p99_interval_ms | 57.9541 |
| python / rotation | passed | after.source_frames_received.missing_frame_numbers | 0 |
| python / rotation | passed | after.duplicate_source_frames | 0 |
| python / exposure-auto | passed | before.delivery.measured_fps | 25.151 |
| python / exposure-auto | passed | before.delivery.p99_interval_ms | 71.2794 |
| python / exposure-auto | passed | before.delivery.missing_frame_numbers | 0 |
| python / exposure-auto | passed | before.source_frames_received.measured_fps | 25.0576 |
| python / exposure-auto | passed | before.source_frames_received.p99_interval_ms | 58.593 |
| python / exposure-auto | passed | before.source_frames_received.missing_frame_numbers | 0 |
| python / exposure-auto | passed | before.duplicate_source_frames | 0 |
| python / exposure-auto | passed | after.delivery.measured_fps | 25.0829 |
| python / exposure-auto | passed | after.delivery.p99_interval_ms | 66.48 |
| python / exposure-auto | passed | after.delivery.missing_frame_numbers | 0 |
| python / exposure-auto | passed | after.source_frames_received.measured_fps | 25.0789 |
| python / exposure-auto | passed | after.source_frames_received.p99_interval_ms | 63.8168 |
| python / exposure-auto | passed | after.source_frames_received.missing_frame_numbers | 0 |
| python / exposure-auto | passed | after.duplicate_source_frames | 0 |
| python / exposure-recommend | passed | before.delivery.measured_fps | 24.7855 |
| python / exposure-recommend | passed | before.delivery.p99_interval_ms | 69.5406 |
| python / exposure-recommend | passed | before.delivery.missing_frame_numbers | 0 |
| python / exposure-recommend | passed | before.source_frames_received.measured_fps | 24.8975 |
| python / exposure-recommend | passed | before.source_frames_received.p99_interval_ms | 58.1486 |
| python / exposure-recommend | passed | before.source_frames_received.missing_frame_numbers | 0 |
| python / exposure-recommend | passed | before.duplicate_source_frames | 0 |
| python / exposure-recommend | passed | after.delivery.measured_fps | 24.9691 |
| python / exposure-recommend | passed | after.delivery.p99_interval_ms | 70.4018 |
| python / exposure-recommend | passed | after.delivery.missing_frame_numbers | 0 |
| python / exposure-recommend | passed | after.source_frames_received.measured_fps | 25.0686 |
| python / exposure-recommend | passed | after.source_frames_received.p99_interval_ms | 63.7148 |
| python / exposure-recommend | passed | after.source_frames_received.missing_frame_numbers | 0 |
| python / exposure-recommend | passed | after.duplicate_source_frames | 0 |
| python / resolution | passed | before.delivery.measured_fps | 25.0293 |
| python / resolution | passed | before.delivery.p99_interval_ms | 70.2971 |
| python / resolution | passed | before.delivery.missing_frame_numbers | 0 |
| python / resolution | passed | before.source_frames_received.measured_fps | 25.0618 |
| python / resolution | passed | before.source_frames_received.p99_interval_ms | 58.2358 |
| python / resolution | passed | before.source_frames_received.missing_frame_numbers | 0 |
| python / resolution | passed | before.duplicate_source_frames | 0 |
| python / resolution | passed | after.delivery.measured_fps | 25.157 |
| python / resolution | passed | after.delivery.p99_interval_ms | 72.1815 |
| python / resolution | passed | after.delivery.missing_frame_numbers | 0 |
| python / resolution | passed | after.source_frames_received.measured_fps | 25.0803 |
| python / resolution | passed | after.source_frames_received.p99_interval_ms | 57.247 |
| python / resolution | passed | after.source_frames_received.missing_frame_numbers | 0 |
| python / resolution | passed | after.duplicate_source_frames | 0 |
| python / exposure | failed | before.delivery.measured_fps | 25.2334 |
| python / exposure | failed | before.delivery.p99_interval_ms | 71.8174 |
| python / exposure | failed | before.delivery.missing_frame_numbers | 0 |
| python / exposure | failed | before.source_frames_received.measured_fps | 25.0614 |
| python / exposure | failed | before.source_frames_received.p99_interval_ms | 57.8137 |
| python / exposure | failed | before.source_frames_received.missing_frame_numbers | 0 |
| python / exposure | failed | before.duplicate_source_frames | 0 |
| python / rotation | passed | before.delivery.measured_fps | 25.933 |
| python / rotation | passed | before.delivery.p99_interval_ms | 69.3475 |
| python / rotation | passed | before.delivery.missing_frame_numbers | 0 |
| python / rotation | passed | before.source_frames_received.measured_fps | 25.0997 |
| python / rotation | passed | before.source_frames_received.p99_interval_ms | 58.3221 |
| python / rotation | passed | before.source_frames_received.missing_frame_numbers | 0 |
| python / rotation | passed | before.duplicate_source_frames | 0 |
| python / rotation | passed | after.delivery.measured_fps | 25.106 |
| python / rotation | passed | after.delivery.p99_interval_ms | 69.4097 |
| python / rotation | passed | after.delivery.missing_frame_numbers | 0 |
| python / rotation | passed | after.source_frames_received.measured_fps | 25.0712 |
| python / rotation | passed | after.source_frames_received.p99_interval_ms | 58.1095 |
| python / rotation | passed | after.source_frames_received.missing_frame_numbers | 0 |
| python / rotation | passed | after.duplicate_source_frames | 0 |
| python / exposure-auto | passed | before.delivery.measured_fps | 25.1081 |
| python / exposure-auto | passed | before.delivery.p99_interval_ms | 66.599 |
| python / exposure-auto | passed | before.delivery.missing_frame_numbers | 0 |
| python / exposure-auto | passed | before.source_frames_received.measured_fps | 25.0906 |
| python / exposure-auto | passed | before.source_frames_received.p99_interval_ms | 58.2925 |
| python / exposure-auto | passed | before.source_frames_received.missing_frame_numbers | 0 |
| python / exposure-auto | passed | before.duplicate_source_frames | 0 |
| python / exposure-auto | passed | after.delivery.measured_fps | 25.1474 |
| python / exposure-auto | passed | after.delivery.p99_interval_ms | 71.8467 |
| python / exposure-auto | passed | after.delivery.missing_frame_numbers | 0 |
| python / exposure-auto | passed | after.source_frames_received.measured_fps | 24.8815 |
| python / exposure-auto | passed | after.source_frames_received.p99_interval_ms | 58.2133 |
| python / exposure-auto | passed | after.source_frames_received.missing_frame_numbers | 0 |
| python / exposure-auto | passed | after.duplicate_source_frames | 0 |
| python / exposure-recommend | passed | before.delivery.measured_fps | 25.1085 |
| python / exposure-recommend | passed | before.delivery.p99_interval_ms | 70.2861 |
| python / exposure-recommend | passed | before.delivery.missing_frame_numbers | 0 |
| python / exposure-recommend | passed | before.source_frames_received.measured_fps | 25.0936 |
| python / exposure-recommend | passed | before.source_frames_received.p99_interval_ms | 58.0636 |
| python / exposure-recommend | passed | before.source_frames_received.missing_frame_numbers | 0 |
| python / exposure-recommend | passed | before.duplicate_source_frames | 0 |
| python / exposure-recommend | passed | after.delivery.measured_fps | 24.9175 |
| python / exposure-recommend | passed | after.delivery.p99_interval_ms | 69.1989 |
| python / exposure-recommend | passed | after.delivery.missing_frame_numbers | 0 |
| python / exposure-recommend | passed | after.source_frames_received.measured_fps | 24.5078 |
| python / exposure-recommend | passed | after.source_frames_received.p99_interval_ms | 64.8153 |
| python / exposure-recommend | passed | after.source_frames_received.missing_frame_numbers | 0 |
| python / exposure-recommend | passed | after.duplicate_source_frames | 0 |
| python / resolution | passed | before.delivery.measured_fps | 25.1613 |
| python / resolution | passed | before.delivery.p99_interval_ms | 70.997 |
| python / resolution | passed | before.delivery.missing_frame_numbers | 0 |
| python / resolution | passed | before.source_frames_received.measured_fps | 25.0783 |
| python / resolution | passed | before.source_frames_received.p99_interval_ms | 58.6143 |
| python / resolution | passed | before.source_frames_received.missing_frame_numbers | 0 |
| python / resolution | passed | before.duplicate_source_frames | 0 |
| python / resolution | passed | after.delivery.measured_fps | 25.0885 |
| python / resolution | passed | after.delivery.p99_interval_ms | 66.6779 |
| python / resolution | passed | after.delivery.missing_frame_numbers | 0 |
| python / resolution | passed | after.source_frames_received.measured_fps | 25.0622 |
| python / resolution | passed | after.source_frames_received.p99_interval_ms | 57.8403 |
| python / resolution | passed | after.source_frames_received.missing_frame_numbers | 0 |
| python / resolution | passed | after.duplicate_source_frames | 0 |
| python / repeat-record-start | failed | measurements | unavailable |
| python / stop-without-recording | passed | stream.delivery.measured_fps | 24.244 |
| python / stop-without-recording | passed | stream.delivery.p99_interval_ms | 70.1869 |
| python / stop-without-recording | passed | stream.delivery.missing_frame_numbers | 0 |
| python / stop-without-recording | passed | stream.source_frames_received.measured_fps | 24.3509 |
| python / stop-without-recording | passed | stream.source_frames_received.p99_interval_ms | 64.3209 |
| python / stop-without-recording | passed | stream.source_frames_received.missing_frame_numbers | 0 |
| python / stop-without-recording | passed | stream.duplicate_source_frames | 0 |
| python / pause-during-recording | passed | stream.delivery.measured_fps | 25.0561 |
| python / pause-during-recording | passed | stream.delivery.p99_interval_ms | 71.4737 |
| python / pause-during-recording | passed | stream.delivery.missing_frame_numbers | 0 |
| python / pause-during-recording | passed | stream.source_frames_received.measured_fps | 25.09 |
| python / pause-during-recording | passed | stream.source_frames_received.p99_interval_ms | 57.8225 |
| python / pause-during-recording | passed | stream.source_frames_received.missing_frame_numbers | 0 |
| python / pause-during-recording | passed | stream.duplicate_source_frames | 0 |
| rust / record | failed | measurements | unavailable |
| rust / record | failed | measurements | unavailable |
| rust / record | failed | measurements | unavailable |
| rust / add-camera | failed | measurements | unavailable |
| rust / remove-camera | failed | measurements | unavailable |
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
| rust / exposure | failed | measurements | unavailable |
| rust / rotation | failed | measurements | unavailable |
| rust / exposure-auto | failed | measurements | unavailable |
| rust / exposure-recommend | failed | measurements | unavailable |
| rust / resolution | failed | measurements | unavailable |
| rust / repeat-record-start | failed | measurements | unavailable |
| rust / stop-without-recording | failed | measurements | unavailable |
| rust / pause-during-recording | failed | measurements | unavailable |

Stage spans overlap and must not be summed. Per-frame/image costs are amortized over the recording, not latency percentiles. After first excludes exactly the first call; it does not assert steady state. Latency p50/p95/p99 were not recorded. Missing measurements are not zero.

Recorded failures:

- python / record: AssertionError: Recording failed capture/video checks
- python / record: AssertionError: Recording failed capture/video checks
- python / close-during-recording: AssertionError: Closing cameras left an incomplete recording
- python / change-backend: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- python / exposure: AssertionError: Requested exposure was not applied to 7cd1
- python / exposure: AssertionError: Requested exposure was not applied to ea74
- python / repeat-record-start: ApiResponseError: HTTP 500: {"detail":"Timed out waiting for cameras to pause: ['7cd1']"}
- rust / record: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- rust / record: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- rust / record: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- rust / add-camera: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
- rust / remove-camera: ApiResponseError: HTTP 500: {"detail":"No cameras detected"}
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
