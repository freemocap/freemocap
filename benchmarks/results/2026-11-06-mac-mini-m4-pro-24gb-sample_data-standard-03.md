# Machine benchmark: mac-mini-m4-pro-24gb

Run: 2026-11-06T12:53:27.896884+00:00 | passed
CPU: Apple M4 Pro | RAM: 24 GiB

AC power; shared desktop; cached model assets and managed Blender; fresh calibration each run; latest sfn26; sequential runs; standard scientific exports and bounded Blender GUI lifecycle enabled

| Workload | Status | Measurement | Value |
|---|---|---|---|
| sample_data | passed | worker_elapsed_s | 119.303 |
| sample_data | passed | synchronized_frames_per_worker_second | 9.28727 |
| sample_data | passed | camera_images_per_worker_second | 27.8618 |
| sample_data | passed | worker_amortized_ms_per_frame | 107.674 |
| sample_data | passed | worker_amortized_ms_per_image | 35.8914 |

## sample_data — posthoc

Outcome: complete; wall: 78.8276 s; 1108 synchronized frames / 3324 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| graph.camera_batch_wait | 1109 | 0.0265934 | 0.0239796 | 2.57417 | 0.021678 | 2.57417 | 0.0240013 | 41664.5 | 0.00800043 | 124993 |
| inference.queue_wait | 1108 | 0.0257536 | 0.0232434 | 0.025875 | 0.023241 | 0.129084 | 0.0232434 | 43023.1 | 0.00774778 | 129069 |
| inference.session_setup | 1 | 6.00516 | 6005.16 | 6005.16 | not recorded | 6005.16 | 5.41982 | 184.508 | 1.80661 | 553.524 |
| inference.process_batch.images=3 | 1108 | 40.5573 | 36.6041 | 105.816 | 36.5415 | 143.155 | 36.6041 | 27.3194 | 12.2014 | 81.9581 |
| graph.load_and_track | 1 | 46.9148 | 46914.8 | 46914.8 | not recorded | 46914.8 | 42.3419 | 23.6173 | 14.114 | 70.8518 |
| graph.observation_request | 1 | 0.0519079 | 51.9079 | 51.9079 | not recorded | 51.9079 | 0.0468483 | 21345.5 | 0.0156161 | 64036.5 |
| graph.match_and_triangulate | 1 | 1.55066 | 1550.66 | 1550.66 | not recorded | 1550.66 | 1.39952 | 714.533 | 0.466505 | 2143.6 |
| graph.save_observations | 1 | 1.56514 | 1565.14 | 1565.14 | not recorded | 1565.14 | 1.41258 | 707.924 | 0.47086 | 2123.77 |
| graph.filter_trajectories | 1 | 0.0696738 | 69.6738 | 69.6738 | not recorded | 69.6738 | 0.0628825 | 15902.7 | 0.0209608 | 47708 |
| graph.align_reference | 1 | 1.24622 | 1246.22 | 1246.22 | not recorded | 1246.22 | 1.12475 | 889.086 | 0.374917 | 2667.26 |
| graph.spatial_request | 1 | 0.00119492 | 1.19492 | 1.19492 | not recorded | 1.19492 | 0.00107844 | 927261 | 0.000359482 | 2.78178e+06 |
| graph.reconstruction_input | 1 | 0.0105137 | 10.5137 | 10.5137 | not recorded | 10.5137 | 0.00948891 | 105386 | 0.00316297 | 316159 |
| graph.fit_model_dimensions | 1 | 0.175622 | 175.622 | 175.622 | not recorded | 175.622 | 0.158503 | 6309.02 | 0.0528344 | 18927.1 |
| graph.reconstruct_skeletons | 1 | 2.42488 | 2424.88 | 2424.88 | not recorded | 2424.88 | 2.18852 | 456.93 | 0.729506 | 1370.79 |
| graph.save_spatial | 1 | 4.39577 | 4395.77 | 4395.77 | not recorded | 4395.77 | 3.9673 | 252.06 | 1.32243 | 756.181 |
| graph.save_recording | 1 | 3.23337 | 3233.37 | 3233.37 | not recorded | 3233.37 | 2.9182 | 342.677 | 0.972735 | 1028.03 |
| graph.annotate_camera_1 | 1 | 14.6782 | 14678.2 | 14678.2 | not recorded | 14678.2 | 13.2474 | 75.4863 | 4.41581 | 226.459 |
| graph.annotate_camera_0 | 1 | 14.7698 | 14769.8 | 14769.8 | not recorded | 14769.8 | 13.3301 | 75.0181 | 4.44337 | 225.054 |
| graph.annotate_camera_2 | 1 | 10.2633 | 10263.3 | 10263.3 | not recorded | 10263.3 | 9.2629 | 107.957 | 3.08763 | 323.872 |
| export.channel_exports | 1 | 0.906236 | 906.236 | 906.236 | not recorded | 906.236 | 0.817903 | 1222.64 | 0.272634 | 3667.92 |
| export.blender | 1 | 6.72068 | 6720.68 | 6720.68 | not recorded | 6720.68 | 6.06559 | 164.864 | 2.02186 | 494.593 |
| exports.total | 1 | 6.72144 | 6721.44 | 6721.44 | not recorded | 6721.44 | 6.06628 | 164.846 | 2.02209 | 494.537 |

## sample_data — dataset_worker

Outcome: complete; wall: 118.594 s; 1108 synchronized frames / 3324 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| workflow.blender_preparation | 1 | 1.43232 | 1432.32 | 1432.32 | not recorded | 1432.32 | 1.29271 | 773.571 | 0.430902 | 2320.71 |
| workflow.inference_service_start | 1 | 5.7917e-05 | 0.057917 | 0.057917 | not recorded | 0.057917 | 5.22716e-05 | 1.91308e+07 | 1.74239e-05 | 5.73925e+07 |
| workflow.calibration | 1 | 25.642 | 25642 | 25642 | not recorded | 25642 | 23.1426 | 43.2104 | 7.71419 | 129.631 |
| workflow.mocap | 1 | 79.0566 | 79056.6 | 79056.6 | not recorded | 79056.6 | 71.3507 | 14.0153 | 23.7836 | 42.0458 |
| workflow.numerical_validation | 1 | 0.846715 | 846.715 | 846.715 | not recorded | 846.715 | 0.764183 | 1308.59 | 0.254728 | 3925.76 |
| workflow.blender_validation | 1 | 9.93943 | 9939.43 | 9939.43 | not recorded | 9939.43 | 8.97061 | 111.475 | 2.9902 | 334.426 |
| workflow.output_acceptance | 1 | 0.0649827 | 64.9827 | 64.9827 | not recorded | 64.9827 | 0.0586487 | 17050.7 | 0.0195496 | 51152.1 |
| workflow.shutdown | 1 | 0.000483833 | 0.483833 | 0.483833 | not recorded | 0.483833 | 0.000436672 | 2.29005e+06 | 0.000145557 | 6.87014e+06 |

Stage spans overlap and must not be summed. Per-frame/image costs are amortized over the recording, not latency percentiles. After first excludes exactly the first call; it does not assert steady state. Latency p50/p95/p99 were not recorded. Missing measurements are not zero.

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
