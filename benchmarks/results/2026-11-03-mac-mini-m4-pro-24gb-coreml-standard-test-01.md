# Machine benchmark: mac-mini-m4-pro-24gb

Run: 2026-11-03T17:46:23.904758+00:00 | passed
CPU: Apple M4 Pro | RAM: 24 GiB

AC power; shared desktop; cached models and Blender; first measured CoreML run after fixing graph automatic provider selection; fresh calibration

| Workload | Status | Measurement | Value |
|---|---|---|---|
| test_data | passed | worker_elapsed_s | 38.6086 |
| test_data | passed | synchronized_frames_per_worker_second | 5.75002 |
| test_data | passed | camera_images_per_worker_second | 17.2501 |
| test_data | passed | worker_amortized_ms_per_frame | 173.912 |
| test_data | passed | worker_amortized_ms_per_image | 57.9708 |

## test_data — posthoc

Outcome: complete; wall: 25.0752 s; 222 synchronized frames / 666 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| graph.camera_batch_wait | 223 | 0.00790829 | 0.0354632 | 3.26575 | 0.0209123 | 3.26575 | 0.0356229 | 28071.8 | 0.0118743 | 84215.4 |
| inference.queue_wait | 222 | 0.00561979 | 0.0253144 | 0.075833 | 0.0250858 | 0.097042 | 0.0253144 | 39503.3 | 0.00843812 | 118510 |
| inference.session_setup | 1 | 5.95129 | 5951.29 | 5951.29 | not recorded | 5951.29 | 26.8076 | 37.3028 | 8.93587 | 111.909 |
| inference.process_batch.images=3 | 222 | 8.175 | 36.8243 | 110.004 | 36.4932 | 110.004 | 36.8243 | 27.156 | 12.2748 | 81.4679 |
| graph.load_and_track | 1 | 14.2492 | 14249.2 | 14249.2 | not recorded | 14249.2 | 64.1858 | 15.5798 | 21.3953 | 46.7393 |
| graph.observation_request | 1 | 0.0347238 | 34.7238 | 34.7238 | not recorded | 34.7238 | 0.156413 | 6393.32 | 0.0521378 | 19180 |
| graph.save_observations | 1 | 0.240818 | 240.818 | 240.818 | not recorded | 240.818 | 1.08476 | 921.859 | 0.361588 | 2765.58 |
| graph.match_and_triangulate | 1 | 0.377282 | 377.282 | 377.282 | not recorded | 377.282 | 1.69947 | 588.42 | 0.566489 | 1765.26 |
| graph.filter_trajectories | 1 | 0.00890804 | 8.90804 | 8.90804 | not recorded | 8.90804 | 0.0401263 | 24921.3 | 0.0133754 | 74763.9 |
| graph.align_reference | 1 | 0.283468 | 283.468 | 283.468 | not recorded | 283.468 | 1.27688 | 783.158 | 0.425627 | 2349.48 |
| graph.reconstruction_input | 1 | 0.000874583 | 0.874583 | 0.874583 | not recorded | 0.874583 | 0.00393956 | 253835 | 0.00131319 | 761506 |
| graph.spatial_request | 1 | 0.000766208 | 0.766208 | 0.766208 | not recorded | 0.766208 | 0.00345139 | 289739 | 0.00115046 | 869216 |
| graph.fit_model_dimensions | 1 | 0.0858171 | 85.8171 | 85.8171 | not recorded | 85.8171 | 0.386563 | 2586.9 | 0.128854 | 7760.69 |
| graph.reconstruct_skeletons | 1 | 0.743747 | 743.747 | 743.747 | not recorded | 743.747 | 3.35021 | 298.488 | 1.11674 | 895.465 |
| graph.save_spatial | 1 | 1.12994 | 1129.94 | 1129.94 | not recorded | 1129.94 | 5.08983 | 196.47 | 1.69661 | 589.41 |
| graph.save_recording | 1 | 0.781165 | 781.165 | 781.165 | not recorded | 781.165 | 3.51876 | 284.191 | 1.17292 | 852.572 |
| graph.annotate_camera_0 | 1 | 3.56258 | 3562.58 | 3562.58 | not recorded | 3562.58 | 16.0477 | 62.3143 | 5.34922 | 186.943 |
| graph.annotate_camera_1 | 1 | 3.61824 | 3618.24 | 3618.24 | not recorded | 3618.24 | 16.2984 | 61.3558 | 5.43279 | 184.067 |
| graph.annotate_camera_2 | 1 | 2.62255 | 2622.55 | 2622.55 | not recorded | 2622.55 | 11.8133 | 84.6505 | 3.93776 | 253.951 |
| export.blender | 1 | 4.38708 | 4387.08 | 4387.08 | not recorded | 4387.08 | 19.7616 | 50.6031 | 6.58721 | 151.809 |
| exports.total | 1 | 4.38749 | 4387.49 | 4387.49 | not recorded | 4387.49 | 19.7635 | 50.5984 | 6.58782 | 151.795 |

## test_data — dataset_worker

Outcome: complete; wall: 38.1849 s; 222 synchronized frames / 666 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| workflow.blender_preparation | 1 | 2.20896 | 2208.96 | 2208.96 | not recorded | 2208.96 | 9.95025 | 100.5 | 3.31675 | 301.5 |
| workflow.inference_service_start | 1 | 7.4167e-05 | 0.074167 | 0.074167 | not recorded | 0.074167 | 0.000334086 | 2.99324e+06 | 0.000111362 | 8.97973e+06 |
| workflow.calibration | 1 | 6.22344 | 6223.44 | 6223.44 | not recorded | 6223.44 | 28.0335 | 35.6716 | 9.34451 | 107.015 |
| workflow.mocap | 1 | 25.2786 | 25278.6 | 25278.6 | not recorded | 25278.6 | 113.868 | 8.78213 | 37.9558 | 26.3464 |
| workflow.numerical_validation | 1 | 0.203572 | 203.572 | 203.572 | not recorded | 203.572 | 0.916992 | 1090.52 | 0.305664 | 3271.57 |
| workflow.blender_validation | 1 | 2.64798 | 2647.98 | 2647.98 | not recorded | 2647.98 | 11.9279 | 83.8374 | 3.97595 | 251.512 |
| workflow.output_acceptance | 1 | 0.0139224 | 13.9224 | 13.9224 | not recorded | 13.9224 | 0.0627134 | 15945.6 | 0.0209045 | 47836.7 |
| workflow.shutdown | 1 | 0.000565542 | 0.565542 | 0.565542 | not recorded | 0.565542 | 0.00254749 | 392544 | 0.000849162 | 1.17763e+06 |

Stage spans overlap and must not be summed. Per-frame/image costs are amortized over the recording, not latency percentiles. After first excludes exactly the first call; it does not assert steady state. Latency p50/p95/p99 were not recorded. Missing measurements are not zero.

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
