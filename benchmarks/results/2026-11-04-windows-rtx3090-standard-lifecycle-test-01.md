# Machine benchmark: windows-rtx3090

Run: 2026-11-04T17:14:13.565558+00:00 | passed
CPU: 12th Gen Intel(R) Core(TM) i9-12900KF | RAM: 127.796 GiB

Shared desktop; AC power; cached models and raw data; no concurrent agent training or camera audit; fresh process and calibration; all standard exports; final promoted Blender GUI opens then verifies loaded path and quits via2second timer; bounded owned-process teardown

| Workload | Status | Measurement | Value |
|---|---|---|---|
| test_data | passed | worker_elapsed_s | 56.0108 |
| test_data | passed | synchronized_frames_per_worker_second | 3.96352 |
| test_data | passed | camera_images_per_worker_second | 11.8906 |
| test_data | passed | worker_amortized_ms_per_frame | 252.301 |
| test_data | passed | worker_amortized_ms_per_image | 84.1002 |

## test_data — posthoc

Outcome: complete; wall: 29.5254 s; 222 synchronized frames / 666 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| graph.camera_batch_wait | 223 | 0.0225157 | 0.100967 | 13.0744 | 0.0425284 | 13.0744 | 0.101422 | 9859.79 | 0.0338074 | 29579.4 |
| inference.queue_wait | 222 | 0.0271667 | 0.122373 | 0.112 | 0.122419 | 2.2321 | 0.122373 | 8171.77 | 0.0407908 | 24515.3 |
| inference.session_setup | 1 | 1.33511 | 1335.11 | 1335.11 | not recorded | 1335.11 | 6.01399 | 166.279 | 2.00466 | 498.837 |
| inference.process_batch.images=3 | 222 | 7.61392 | 34.2969 | 79.2365 | 34.0936 | 79.2365 | 34.2969 | 29.1571 | 11.4323 | 87.4714 |
| graph.load_and_track | 1 | 9.28554 | 9285.54 | 9285.54 | not recorded | 9285.54 | 41.8268 | 23.9081 | 13.9423 | 71.7244 |
| graph.observation_request | 1 | 0.122743 | 122.743 | 122.743 | not recorded | 122.743 | 0.552899 | 1808.65 | 0.1843 | 5425.95 |
| graph.save_observations | 1 | 0.563378 | 563.378 | 563.378 | not recorded | 563.378 | 2.53774 | 394.051 | 0.845913 | 1182.15 |
| graph.match_and_triangulate | 1 | 0.719362 | 719.362 | 719.362 | not recorded | 719.362 | 3.24037 | 308.607 | 1.08012 | 925.82 |
| graph.filter_trajectories | 1 | 0.0211684 | 21.1684 | 21.1684 | not recorded | 21.1684 | 0.0953532 | 10487.3 | 0.0317844 | 31462 |
| graph.align_reference | 1 | 0.67911 | 679.11 | 679.11 | not recorded | 679.11 | 3.05905 | 326.899 | 1.01968 | 980.696 |
| graph.reconstruction_input | 1 | 0.0038461 | 3.8461 | 3.8461 | not recorded | 3.8461 | 0.0173248 | 57720.8 | 0.00577492 | 173162 |
| graph.spatial_request | 1 | 0.007072 | 7.072 | 7.072 | not recorded | 7.072 | 0.0318559 | 31391.4 | 0.0106186 | 94174.2 |
| graph.fit_model_dimensions | 1 | 0.135375 | 135.375 | 135.375 | not recorded | 135.375 | 0.609796 | 1639.89 | 0.203265 | 4919.68 |
| graph.reconstruct_skeletons | 1 | 1.39796 | 1397.96 | 1397.96 | not recorded | 1397.96 | 6.29712 | 158.803 | 2.09904 | 476.408 |
| graph.save_spatial | 1 | 2.27017 | 2270.17 | 2270.17 | not recorded | 2270.17 | 10.226 | 97.79 | 3.40866 | 293.37 |
| graph.annotate_camera_0 | 1 | 5.34058 | 5340.58 | 5340.58 | not recorded | 5340.58 | 24.0567 | 41.5685 | 8.01889 | 124.706 |
| graph.annotate_camera_1 | 1 | 5.34346 | 5343.46 | 5343.46 | not recorded | 5343.46 | 24.0696 | 41.5461 | 8.02321 | 124.638 |
| graph.save_recording | 1 | 2.07915 | 2079.15 | 2079.15 | not recorded | 2079.15 | 9.36552 | 106.775 | 3.12184 | 320.324 |
| graph.annotate_camera_2 | 1 | 4.13082 | 4130.82 | 4130.82 | not recorded | 4130.82 | 18.6073 | 53.7423 | 6.20243 | 161.227 |
| export.channel_exports | 1 | 0.504686 | 504.686 | 504.686 | not recorded | 504.686 | 2.27336 | 439.877 | 0.757787 | 1319.63 |
| export.blender | 1 | 10.2456 | 10245.6 | 10245.6 | not recorded | 10245.6 | 46.1513 | 21.6679 | 15.3838 | 65.0036 |
| exports.total | 1 | 10.2476 | 10247.6 | 10247.6 | not recorded | 10247.6 | 46.1605 | 21.6636 | 15.3868 | 64.9907 |

## test_data — dataset_worker

Outcome: complete; wall: 54.2882 s; 222 synchronized frames / 666 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| workflow.blender_preparation | 1 | 3.51342 | 3513.42 | 3513.42 | not recorded | 3513.42 | 15.8262 | 63.1863 | 5.2754 | 189.559 |
| workflow.inference_service_start | 1 | 0.0002397 | 0.2397 | 0.2397 | not recorded | 0.2397 | 0.00107973 | 926158 | 0.00035991 | 2.77847e+06 |
| workflow.calibration | 1 | 11.78 | 11780 | 11780 | not recorded | 11780 | 53.0629 | 18.8455 | 17.6876 | 56.5366 |
| workflow.mocap | 1 | 29.8566 | 29856.6 | 29856.6 | not recorded | 29856.6 | 134.489 | 7.43553 | 44.8298 | 22.3066 |
| workflow.numerical_validation | 1 | 0.492821 | 492.821 | 492.821 | not recorded | 492.821 | 2.21992 | 450.467 | 0.739972 | 1351.4 |
| workflow.blender_validation | 1 | 5.05673 | 5056.73 | 5056.73 | not recorded | 5056.73 | 22.7781 | 43.9019 | 7.59269 | 131.706 |
| workflow.output_acceptance | 1 | 0.0251486 | 25.1486 | 25.1486 | not recorded | 25.1486 | 0.113282 | 8827.53 | 0.0377607 | 26482.6 |
| workflow.shutdown | 1 | 0.0006056 | 0.6056 | 0.6056 | not recorded | 0.6056 | 0.00272793 | 366579 | 0.000909309 | 1.09974e+06 |

Stage spans overlap and must not be summed. Per-frame/image costs are amortized over the recording, not latency percentiles. After first excludes exactly the first call; it does not assert steady state. Latency p50/p95/p99 were not recorded. Missing measurements are not zero.

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
