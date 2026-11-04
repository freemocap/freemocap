# Machine benchmark: windows-rtx3090

Run: 2026-11-04T16:56:25.938753+00:00 | passed
CPU: 12th Gen Intel(R) Core(TM) i9-12900KF | RAM: 127.796 GiB

Shared desktop; AC power; existing models and raw data; no concurrent agent training; fresh process and calibration; all standard exports and Blender auto-open enabled; external temporary root required by Windows path-length preflight; INTERVENTION: auto-opened Blender inherited worker output pipe; only benchmark GUI gracefully closed manually to release shutdown; elapsed includes wait and is excluded from performance comparison

| Workload | Status | Measurement | Value |
|---|---|---|---|
| test_data | passed | worker_elapsed_s | 164.931 |
| test_data | passed | synchronized_frames_per_worker_second | 1.34601 |
| test_data | passed | camera_images_per_worker_second | 4.03804 |
| test_data | passed | worker_amortized_ms_per_frame | 742.934 |
| test_data | passed | worker_amortized_ms_per_image | 247.645 |

## test_data — posthoc

Outcome: complete; wall: 32.7649 s; 222 synchronized frames / 666 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| graph.camera_batch_wait | 223 | 0.0228982 | 0.102683 | 13.252 | 0.0434514 | 13.252 | 0.103145 | 9695.09 | 0.0343817 | 29085.3 |
| inference.queue_wait | 222 | 0.0254635 | 0.1147 | 0.1445 | 0.114566 | 0.3342 | 0.1147 | 8718.36 | 0.0382335 | 26155.1 |
| inference.session_setup | 1 | 2.50408 | 2504.08 | 2504.08 | not recorded | 2504.08 | 11.2796 | 88.6555 | 3.75987 | 265.966 |
| inference.process_batch.images=3 | 222 | 7.96113 | 35.8609 | 79.3223 | 35.6643 | 81.8408 | 35.8609 | 27.8855 | 11.9536 | 83.6565 |
| graph.load_and_track | 1 | 10.8052 | 10805.2 | 10805.2 | not recorded | 10805.2 | 48.672 | 20.5457 | 16.224 | 61.637 |
| graph.match_and_triangulate | 1 | 0.534335 | 534.335 | 534.335 | not recorded | 534.335 | 2.40691 | 415.47 | 0.802304 | 1246.41 |
| graph.filter_trajectories | 1 | 0.019323 | 19.323 | 19.323 | not recorded | 19.323 | 0.0870405 | 11488.9 | 0.0290135 | 34466.7 |
| graph.align_reference | 1 | 0.668139 | 668.139 | 668.139 | not recorded | 668.139 | 3.00964 | 332.266 | 1.00321 | 996.799 |
| graph.reconstruction_input | 1 | 0.0069841 | 6.9841 | 6.9841 | not recorded | 6.9841 | 0.0314599 | 31786.5 | 0.0104866 | 95359.5 |
| graph.fit_model_dimensions | 1 | 0.0745828 | 74.5828 | 74.5828 | not recorded | 74.5828 | 0.335959 | 2976.56 | 0.111986 | 8929.67 |
| graph.reconstruct_skeletons | 1 | 1.22661 | 1226.61 | 1226.61 | not recorded | 1226.61 | 5.52529 | 180.986 | 1.84176 | 542.958 |
| graph.observation_request | 1 | 3.6836 | 3683.6 | 3683.6 | not recorded | 3683.6 | 16.5928 | 60.2671 | 5.53093 | 180.801 |
| graph.spatial_request | 1 | 0.0157556 | 15.7556 | 15.7556 | not recorded | 15.7556 | 0.0709712 | 14090.2 | 0.0236571 | 42270.7 |
| graph.save_observations | 1 | 0.621922 | 621.922 | 621.922 | not recorded | 621.922 | 2.80145 | 356.958 | 0.933817 | 1070.87 |
| graph.annotate_camera_1 | 1 | 5.81559 | 5815.59 | 5815.59 | not recorded | 5815.59 | 26.1963 | 38.1733 | 8.73211 | 114.52 |
| graph.annotate_camera_0 | 1 | 5.87687 | 5876.87 | 5876.87 | not recorded | 5876.87 | 26.4724 | 37.7752 | 8.82413 | 113.326 |
| graph.save_spatial | 1 | 1.57832 | 1578.32 | 1578.32 | not recorded | 1578.32 | 7.10953 | 140.656 | 2.36984 | 421.969 |
| graph.save_recording | 1 | 1.70622 | 1706.22 | 1706.22 | not recorded | 1706.22 | 7.68568 | 130.112 | 2.56189 | 390.336 |
| graph.annotate_camera_2 | 1 | 4.36604 | 4366.04 | 4366.04 | not recorded | 4366.04 | 19.6668 | 50.847 | 6.55561 | 152.541 |
| export.channel_exports | 1 | 0.506317 | 506.317 | 506.317 | not recorded | 506.317 | 2.2807 | 438.461 | 0.760235 | 1315.38 |
| export.blender | 1 | 11.1357 | 11135.7 | 11135.7 | not recorded | 11135.7 | 50.1609 | 19.9358 | 16.7203 | 59.8075 |
| exports.total | 1 | 11.1387 | 11138.7 | 11138.7 | not recorded | 11138.7 | 50.1744 | 19.9305 | 16.7248 | 59.7915 |

## test_data — dataset_worker

Outcome: complete; wall: 82.0937 s; 222 synchronized frames / 666 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| workflow.blender_preparation | 1 | 20.6622 | 20662.2 | 20662.2 | not recorded | 20662.2 | 93.0728 | 10.7443 | 31.0243 | 32.2328 |
| workflow.inference_service_start | 1 | 0.0007415 | 0.7415 | 0.7415 | not recorded | 0.7415 | 0.00334009 | 299393 | 0.00111336 | 898179 |
| workflow.calibration | 1 | 15.5573 | 15557.3 | 15557.3 | not recorded | 15557.3 | 70.0779 | 14.2698 | 23.3593 | 42.8095 |
| workflow.mocap | 1 | 33.2473 | 33247.3 | 33247.3 | not recorded | 33247.3 | 149.763 | 6.67723 | 49.9209 | 20.0317 |
| workflow.numerical_validation | 1 | 0.627021 | 627.021 | 627.021 | not recorded | 627.021 | 2.82442 | 354.055 | 0.941473 | 1062.17 |
| workflow.blender_validation | 1 | 7.56055 | 7560.55 | 7560.55 | not recorded | 7560.55 | 34.0565 | 29.363 | 11.3522 | 88.0889 |
| workflow.output_acceptance | 1 | 0.0313905 | 31.3905 | 31.3905 | not recorded | 31.3905 | 0.141399 | 7072.2 | 0.0471329 | 21216.6 |
| workflow.shutdown | 1 | 0.0008925 | 0.8925 | 0.8925 | not recorded | 0.8925 | 0.00402027 | 248739 | 0.00134009 | 746218 |

Stage spans overlap and must not be summed. Per-frame/image costs are amortized over the recording, not latency percentiles. After first excludes exactly the first call; it does not assert steady state. Latency p50/p95/p99 were not recorded. Missing measurements are not zero.

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
