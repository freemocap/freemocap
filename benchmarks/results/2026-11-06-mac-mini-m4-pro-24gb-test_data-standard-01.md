# Machine benchmark: mac-mini-m4-pro-24gb

Run: 2026-11-06T12:47:01.738244+00:00 | passed
CPU: Apple M4 Pro | RAM: 24 GiB

AC power; shared desktop; cached model assets and managed Blender; fresh calibration each run; latest sfn26; sequential runs; standard scientific exports and bounded Blender GUI lifecycle enabled

| Workload | Status | Measurement | Value |
|---|---|---|---|
| test_data | passed | worker_elapsed_s | 38.2334 |
| test_data | passed | synchronized_frames_per_worker_second | 5.80645 |
| test_data | passed | camera_images_per_worker_second | 17.4193 |
| test_data | passed | worker_amortized_ms_per_frame | 172.222 |
| test_data | passed | worker_amortized_ms_per_image | 57.4075 |

## test_data — posthoc

Outcome: complete; wall: 25.0374 s; 222 synchronized frames / 666 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| graph.camera_batch_wait | 223 | 0.00682249 | 0.0305941 | 2.31242 | 0.0203157 | 2.31242 | 0.030732 | 32539.4 | 0.010244 | 97618.3 |
| inference.queue_wait | 222 | 0.00649654 | 0.0292637 | 0.024417 | 0.0292856 | 0.106333 | 0.0292637 | 34172 | 0.00975457 | 102516 |
| inference.session_setup | 1 | 5.77394 | 5773.94 | 5773.94 | not recorded | 5773.94 | 26.0088 | 38.4486 | 8.66958 | 115.346 |
| inference.process_batch.images=3 | 222 | 8.1487 | 36.7059 | 104.912 | 36.3972 | 104.912 | 36.7059 | 27.2436 | 12.2353 | 81.7308 |
| graph.load_and_track | 1 | 14.0423 | 14042.3 | 14042.3 | not recorded | 14042.3 | 63.2538 | 15.8093 | 21.0846 | 47.428 |
| graph.observation_request | 1 | 0.0474413 | 47.4413 | 47.4413 | not recorded | 47.4413 | 0.213699 | 4679.47 | 0.0712331 | 14038.4 |
| graph.match_and_triangulate | 1 | 0.39008 | 390.08 | 390.08 | not recorded | 390.08 | 1.75712 | 569.114 | 0.585706 | 1707.34 |
| graph.filter_trajectories | 1 | 0.0118148 | 11.8148 | 11.8148 | not recorded | 11.8148 | 0.05322 | 18789.9 | 0.01774 | 56369.8 |
| graph.align_reference | 1 | 0.272843 | 272.843 | 272.843 | not recorded | 272.843 | 1.22902 | 813.654 | 0.409675 | 2440.96 |
| graph.save_observations | 1 | 0.629023 | 629.023 | 629.023 | not recorded | 629.023 | 2.83344 | 352.929 | 0.944478 | 1058.79 |
| graph.spatial_request | 1 | 0.00113083 | 1.13083 | 1.13083 | not recorded | 1.13083 | 0.00509384 | 196315 | 0.00169795 | 588946 |
| graph.reconstruction_input | 1 | 0.00143538 | 1.43538 | 1.43538 | not recorded | 1.43538 | 0.00646565 | 154663 | 0.00215522 | 463990 |
| graph.fit_model_dimensions | 1 | 0.0682314 | 68.2314 | 68.2314 | not recorded | 68.2314 | 0.307349 | 3253.64 | 0.10245 | 9760.91 |
| graph.reconstruct_skeletons | 1 | 0.499978 | 499.978 | 499.978 | not recorded | 499.978 | 2.25215 | 444.019 | 0.750718 | 1332.06 |
| graph.save_spatial | 1 | 1.01121 | 1011.21 | 1011.21 | not recorded | 1011.21 | 4.55498 | 219.54 | 1.51833 | 658.619 |
| graph.save_recording | 1 | 0.960946 | 960.946 | 960.946 | not recorded | 960.946 | 4.32859 | 231.022 | 1.44286 | 693.067 |
| graph.annotate_camera_1 | 1 | 3.5454 | 3545.4 | 3545.4 | not recorded | 3545.4 | 15.9703 | 62.6163 | 5.32343 | 187.849 |
| graph.annotate_camera_0 | 1 | 3.58056 | 3580.56 | 3580.56 | not recorded | 3580.56 | 16.1286 | 62.0015 | 5.37621 | 186.005 |
| graph.annotate_camera_2 | 1 | 2.42627 | 2426.27 | 2426.27 | not recorded | 2426.27 | 10.9291 | 91.4985 | 3.64305 | 274.496 |
| export.channel_exports | 1 | 0.259197 | 259.197 | 259.197 | not recorded | 259.197 | 1.16755 | 856.491 | 0.389185 | 2569.47 |
| export.blender | 1 | 4.77944 | 4779.44 | 4779.44 | not recorded | 4779.44 | 21.529 | 46.4489 | 7.17634 | 139.347 |
| exports.total | 1 | 4.78009 | 4780.09 | 4780.09 | not recorded | 4780.09 | 21.5319 | 46.4427 | 7.17731 | 139.328 |

## test_data — dataset_worker

Outcome: complete; wall: 37.8207 s; 222 synchronized frames / 666 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| workflow.blender_preparation | 1 | 2.60489 | 2604.89 | 2604.89 | not recorded | 2604.89 | 11.7338 | 85.2242 | 3.91125 | 255.673 |
| workflow.inference_service_start | 1 | 7.1792e-05 | 0.071792 | 0.071792 | not recorded | 0.071792 | 0.000323387 | 3.09227e+06 | 0.000107796 | 9.2768e+06 |
| workflow.calibration | 1 | 5.76191 | 5761.91 | 5761.91 | not recorded | 5761.91 | 25.9545 | 38.5289 | 8.65151 | 115.587 |
| workflow.mocap | 1 | 25.2501 | 25250.1 | 25250.1 | not recorded | 25250.1 | 113.739 | 8.79205 | 37.913 | 26.3761 |
| workflow.numerical_validation | 1 | 0.20133 | 201.33 | 201.33 | not recorded | 201.33 | 0.906891 | 1102.67 | 0.302297 | 3308 |
| workflow.blender_validation | 1 | 2.56019 | 2560.19 | 2560.19 | not recorded | 2560.19 | 11.5324 | 86.7123 | 3.84413 | 260.137 |
| workflow.output_acceptance | 1 | 0.0143508 | 14.3508 | 14.3508 | not recorded | 14.3508 | 0.0646432 | 15469.5 | 0.0215477 | 46408.6 |
| workflow.shutdown | 1 | 0.000503042 | 0.503042 | 0.503042 | not recorded | 0.503042 | 0.00226596 | 441315 | 0.000755318 | 1.32395e+06 |

Stage spans overlap and must not be summed. Per-frame/image costs are amortized over the recording, not latency percentiles. After first excludes exactly the first call; it does not assert steady state. Latency p50/p95/p99 were not recorded. Missing measurements are not zero.

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
