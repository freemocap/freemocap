# Machine benchmark: mac-mini-m4-pro-24gb

Run: 2026-11-06T12:52:43.199383+00:00 | passed
CPU: Apple M4 Pro | RAM: 24 GiB

AC power; shared desktop; cached model assets and managed Blender; fresh calibration each run; latest sfn26; sequential runs; standard scientific exports and bounded Blender GUI lifecycle enabled

| Workload | Status | Measurement | Value |
|---|---|---|---|
| test_data | passed | worker_elapsed_s | 37.688 |
| test_data | passed | synchronized_frames_per_worker_second | 5.89046 |
| test_data | passed | camera_images_per_worker_second | 17.6714 |
| test_data | passed | worker_amortized_ms_per_frame | 169.766 |
| test_data | passed | worker_amortized_ms_per_image | 56.5886 |

## test_data — posthoc

Outcome: complete; wall: 25.0155 s; 222 synchronized frames / 666 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| graph.camera_batch_wait | 223 | 0.00722274 | 0.032389 | 2.32867 | 0.0220454 | 2.32867 | 0.0325349 | 30736.2 | 0.010845 | 92208.7 |
| inference.queue_wait | 222 | 0.00607374 | 0.0273592 | 0.0375 | 0.0273133 | 0.1 | 0.0273592 | 36550.8 | 0.00911973 | 109652 |
| inference.session_setup | 1 | 6.03497 | 6034.97 | 6034.97 | not recorded | 6034.97 | 27.1845 | 36.7856 | 9.06151 | 110.357 |
| inference.process_batch.images=3 | 222 | 8.23998 | 37.117 | 110.213 | 36.7863 | 110.213 | 37.117 | 26.9418 | 12.3723 | 80.8254 |
| graph.load_and_track | 1 | 14.4005 | 14400.5 | 14400.5 | not recorded | 14400.5 | 64.867 | 15.4162 | 21.6223 | 46.2485 |
| graph.observation_request | 1 | 0.0301666 | 30.1666 | 30.1666 | not recorded | 30.1666 | 0.135886 | 7359.13 | 0.0452952 | 22077.4 |
| graph.save_observations | 1 | 0.240927 | 240.927 | 240.927 | not recorded | 240.927 | 1.08526 | 921.441 | 0.361752 | 2764.32 |
| graph.match_and_triangulate | 1 | 0.368511 | 368.511 | 368.511 | not recorded | 368.511 | 1.65996 | 602.425 | 0.55332 | 1807.27 |
| graph.filter_trajectories | 1 | 0.00900888 | 9.00888 | 9.00888 | not recorded | 9.00888 | 0.0405805 | 24642.4 | 0.0135268 | 73927.1 |
| graph.align_reference | 1 | 0.291795 | 291.795 | 291.795 | not recorded | 291.795 | 1.31439 | 760.809 | 0.43813 | 2282.43 |
| graph.spatial_request | 1 | 0.00143942 | 1.43942 | 1.43942 | not recorded | 1.43942 | 0.00648386 | 154229 | 0.00216129 | 462687 |
| graph.reconstruction_input | 1 | 0.0033835 | 3.3835 | 3.3835 | not recorded | 3.3835 | 0.015241 | 65612.5 | 0.00508033 | 196838 |
| graph.fit_model_dimensions | 1 | 0.107233 | 107.233 | 107.233 | not recorded | 107.233 | 0.483032 | 2070.26 | 0.161011 | 6210.77 |
| graph.reconstruct_skeletons | 1 | 0.54695 | 546.95 | 546.95 | not recorded | 546.95 | 2.46374 | 405.887 | 0.821246 | 1217.66 |
| graph.save_spatial | 1 | 1.02213 | 1022.13 | 1022.13 | not recorded | 1022.13 | 4.6042 | 217.193 | 1.53473 | 651.579 |
| graph.save_recording | 1 | 0.725953 | 725.953 | 725.953 | not recorded | 725.953 | 3.27006 | 305.805 | 1.09002 | 917.414 |
| graph.annotate_camera_1 | 1 | 3.46956 | 3469.56 | 3469.56 | not recorded | 3469.56 | 15.6286 | 63.9851 | 5.20955 | 191.955 |
| graph.annotate_camera_0 | 1 | 3.50781 | 3507.81 | 3507.81 | not recorded | 3507.81 | 15.801 | 63.2873 | 5.26698 | 189.862 |
| graph.annotate_camera_2 | 1 | 2.54613 | 2546.13 | 2546.13 | not recorded | 2546.13 | 11.4691 | 87.1911 | 3.82302 | 261.573 |
| export.channel_exports | 1 | 0.252341 | 252.341 | 252.341 | not recorded | 252.341 | 1.13667 | 879.763 | 0.37889 | 2639.29 |
| export.blender | 1 | 4.34667 | 4346.67 | 4346.67 | not recorded | 4346.67 | 19.5796 | 51.0735 | 6.52654 | 153.221 |
| exports.total | 1 | 4.34736 | 4347.36 | 4347.36 | not recorded | 4347.36 | 19.5827 | 51.0655 | 6.52757 | 153.196 |

## test_data — dataset_worker

Outcome: complete; wall: 37.2655 s; 222 synchronized frames / 666 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| workflow.blender_preparation | 1 | 1.45865 | 1458.65 | 1458.65 | not recorded | 1458.65 | 6.57052 | 152.195 | 2.19017 | 456.585 |
| workflow.inference_service_start | 1 | 7.975e-05 | 0.07975 | 0.07975 | not recorded | 0.07975 | 0.000359234 | 2.7837e+06 | 0.000119745 | 8.3511e+06 |
| workflow.calibration | 1 | 6.109 | 6109 | 6109 | not recorded | 6109 | 27.518 | 36.3398 | 9.17268 | 109.019 |
| workflow.mocap | 1 | 25.1808 | 25180.8 | 25180.8 | not recorded | 25180.8 | 113.427 | 8.81624 | 37.809 | 26.4487 |
| workflow.numerical_validation | 1 | 0.201942 | 201.942 | 201.942 | not recorded | 201.942 | 0.909647 | 1099.33 | 0.303216 | 3297.98 |
| workflow.blender_validation | 1 | 2.62819 | 2628.19 | 2628.19 | not recorded | 2628.19 | 11.8387 | 84.4689 | 3.94622 | 253.407 |
| workflow.output_acceptance | 1 | 0.0141473 | 14.1473 | 14.1473 | not recorded | 14.1473 | 0.0637267 | 15692 | 0.0212422 | 47076 |
| workflow.shutdown | 1 | 0.000575291 | 0.575291 | 0.575291 | not recorded | 0.575291 | 0.0025914 | 385892 | 0.0008638 | 1.15767e+06 |

Stage spans overlap and must not be summed. Per-frame/image costs are amortized over the recording, not latency percentiles. After first excludes exactly the first call; it does not assert steady state. Latency p50/p95/p99 were not recorded. Missing measurements are not zero.

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
