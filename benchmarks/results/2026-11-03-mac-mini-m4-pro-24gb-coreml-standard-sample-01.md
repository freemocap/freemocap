# Machine benchmark: mac-mini-m4-pro-24gb

Run: 2026-11-03T17:48:14.070659+00:00 | passed
CPU: Apple M4 Pro | RAM: 24 GiB

AC power; shared desktop with other agents active; cached models and Blender; CoreML automatic selection after correction; fresh calibration; no idle-machine claim

| Workload | Status | Measurement | Value |
|---|---|---|---|
| sample_data | passed | worker_elapsed_s | 122.753 |
| sample_data | passed | synchronized_frames_per_worker_second | 9.02622 |
| sample_data | passed | camera_images_per_worker_second | 27.0787 |
| sample_data | passed | worker_amortized_ms_per_frame | 110.788 |
| sample_data | passed | worker_amortized_ms_per_image | 36.9294 |

## sample_data — posthoc

Outcome: complete; wall: 82.9502 s; 1108 synchronized frames / 3324 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| graph.camera_batch_wait | 1109 | 0.0277565 | 0.0250284 | 2.63546 | 0.0226724 | 2.63546 | 0.025051 | 39918.6 | 0.00835034 | 119756 |
| inference.queue_wait | 1108 | 0.0509723 | 0.0460039 | 0.03125 | 0.0460172 | 3.62375 | 0.0460039 | 21737.3 | 0.0153346 | 65211.8 |
| inference.session_setup | 1 | 6.02399 | 6023.99 | 6023.99 | not recorded | 6023.99 | 5.43682 | 183.931 | 1.81227 | 551.793 |
| inference.process_batch.images=3 | 1108 | 41.6202 | 37.5633 | 112.788 | 37.4954 | 158.112 | 37.5633 | 26.6217 | 12.5211 | 79.8651 |
| graph.load_and_track | 1 | 48.0198 | 48019.8 | 48019.8 | not recorded | 48019.8 | 43.3392 | 23.0738 | 14.4464 | 69.2214 |
| graph.observation_request | 1 | 0.0486868 | 48.6868 | 48.6868 | not recorded | 48.6868 | 0.0439412 | 22757.7 | 0.0146471 | 68273.1 |
| graph.match_and_triangulate | 1 | 1.56341 | 1563.41 | 1563.41 | not recorded | 1563.41 | 1.41102 | 708.707 | 0.47034 | 2126.12 |
| graph.filter_trajectories | 1 | 0.0712398 | 71.2398 | 71.2398 | not recorded | 71.2398 | 0.0642958 | 15553.1 | 0.0214319 | 46659.3 |
| graph.save_observations | 1 | 1.60511 | 1605.11 | 1605.11 | not recorded | 1605.11 | 1.44866 | 690.295 | 0.482886 | 2070.88 |
| graph.align_reference | 1 | 1.34689 | 1346.89 | 1346.89 | not recorded | 1346.89 | 1.21561 | 822.633 | 0.405203 | 2467.9 |
| graph.spatial_request | 1 | 0.00163775 | 1.63775 | 1.63775 | not recorded | 1.63775 | 0.00147811 | 676538 | 0.000492705 | 2.02961e+06 |
| graph.reconstruction_input | 1 | 0.0107076 | 10.7076 | 10.7076 | not recorded | 10.7076 | 0.00966388 | 103478 | 0.00322129 | 310434 |
| graph.fit_model_dimensions | 1 | 0.188292 | 188.292 | 188.292 | not recorded | 188.292 | 0.169938 | 5884.49 | 0.0566461 | 17653.5 |
| graph.reconstruct_skeletons | 1 | 2.98903 | 2989.03 | 2989.03 | not recorded | 2989.03 | 2.69768 | 370.689 | 0.899227 | 1112.07 |
| graph.save_spatial | 1 | 5.03105 | 5031.05 | 5031.05 | not recorded | 5031.05 | 4.54066 | 220.232 | 1.51355 | 660.697 |
| graph.save_recording | 1 | 3.24653 | 3246.53 | 3246.53 | not recorded | 3246.53 | 2.93008 | 341.288 | 0.976693 | 1023.86 |
| graph.annotate_camera_1 | 1 | 15.1308 | 15130.8 | 15130.8 | not recorded | 15130.8 | 13.656 | 73.228 | 4.552 | 219.684 |
| graph.annotate_camera_0 | 1 | 15.2465 | 15246.5 | 15246.5 | not recorded | 15246.5 | 13.7604 | 72.6723 | 4.5868 | 218.017 |
| graph.annotate_camera_2 | 1 | 12.9295 | 12929.5 | 12929.5 | not recorded | 12929.5 | 11.6692 | 85.6954 | 3.88975 | 257.086 |
| export.blender | 1 | 6.59213 | 6592.13 | 6592.13 | not recorded | 6592.13 | 5.94957 | 168.079 | 1.98319 | 504.238 |
| exports.total | 1 | 6.593 | 6593 | 6593 | not recorded | 6593 | 5.95036 | 168.057 | 1.98345 | 504.171 |

## sample_data — dataset_worker

Outcome: complete; wall: 121.98 s; 1108 synchronized frames / 3324 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| workflow.blender_preparation | 1 | 1.37489 | 1374.89 | 1374.89 | not recorded | 1374.89 | 1.24087 | 805.884 | 0.413625 | 2417.65 |
| workflow.inference_service_start | 1 | 6.9541e-05 | 0.069541 | 0.069541 | not recorded | 0.069541 | 6.27626e-05 | 1.5933e+07 | 2.09209e-05 | 4.77991e+07 |
| workflow.calibration | 1 | 24.8832 | 24883.2 | 24883.2 | not recorded | 24883.2 | 22.4577 | 44.5281 | 7.48591 | 133.584 |
| workflow.mocap | 1 | 83.1818 | 83181.8 | 83181.8 | not recorded | 83181.8 | 75.0738 | 13.3202 | 25.0246 | 39.9607 |
| workflow.numerical_validation | 1 | 0.858271 | 858.271 | 858.271 | not recorded | 858.271 | 0.774613 | 1290.97 | 0.258204 | 3872.9 |
| workflow.blender_validation | 1 | 10.0792 | 10079.2 | 10079.2 | not recorded | 10079.2 | 9.09676 | 109.929 | 3.03225 | 329.788 |
| workflow.output_acceptance | 1 | 0.0664868 | 66.4868 | 66.4868 | not recorded | 66.4868 | 0.0600061 | 16665 | 0.020002 | 49994.9 |
| workflow.shutdown | 1 | 0.000577583 | 0.577583 | 0.577583 | not recorded | 0.577583 | 0.000521284 | 1.91834e+06 | 0.000173761 | 5.75502e+06 |

Stage spans overlap and must not be summed. Per-frame/image costs are amortized over the recording, not latency percentiles. After first excludes exactly the first call; it does not assert steady state. Latency p50/p95/p99 were not recorded. Missing measurements are not zero.

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
