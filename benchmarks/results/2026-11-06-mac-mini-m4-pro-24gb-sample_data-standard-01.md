# Machine benchmark: mac-mini-m4-pro-24gb

Run: 2026-11-06T12:47:46.668523+00:00 | passed
CPU: Apple M4 Pro | RAM: 24 GiB

AC power; shared desktop; cached model assets and managed Blender; fresh calibration each run; latest sfn26; sequential runs; standard scientific exports and bounded Blender GUI lifecycle enabled

| Workload | Status | Measurement | Value |
|---|---|---|---|
| sample_data | passed | worker_elapsed_s | 115.913 |
| sample_data | passed | synchronized_frames_per_worker_second | 9.55888 |
| sample_data | passed | camera_images_per_worker_second | 28.6766 |
| sample_data | passed | worker_amortized_ms_per_frame | 104.615 |
| sample_data | passed | worker_amortized_ms_per_image | 34.8716 |

## sample_data — posthoc

Outcome: complete; wall: 77.3815 s; 1108 synchronized frames / 3324 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| graph.camera_batch_wait | 1109 | 0.0252629 | 0.0227799 | 2.48875 | 0.0205542 | 2.48875 | 0.0228004 | 43858.9 | 0.00760014 | 131577 |
| inference.queue_wait | 1108 | 0.028714 | 0.0259152 | 0.052834 | 0.0258909 | 0.150917 | 0.0259152 | 38587.4 | 0.0086384 | 115762 |
| inference.session_setup | 1 | 5.90955 | 5909.55 | 5909.55 | not recorded | 5909.55 | 5.33353 | 187.493 | 1.77784 | 562.479 |
| inference.process_batch.images=3 | 1108 | 40.2942 | 36.3666 | 108.206 | 36.3017 | 143.167 | 36.3666 | 27.4978 | 12.1222 | 82.4933 |
| graph.load_and_track | 1 | 46.5458 | 46545.8 | 46545.8 | not recorded | 46545.8 | 42.0088 | 23.8045 | 14.0029 | 71.4136 |
| graph.observation_request | 1 | 0.0510021 | 51.0021 | 51.0021 | not recorded | 51.0021 | 0.0460308 | 21724.6 | 0.0153436 | 65173.8 |
| graph.match_and_triangulate | 1 | 1.46944 | 1469.44 | 1469.44 | not recorded | 1469.44 | 1.32621 | 754.029 | 0.442069 | 2262.09 |
| graph.save_observations | 1 | 1.48189 | 1481.89 | 1481.89 | not recorded | 1481.89 | 1.33745 | 747.694 | 0.445815 | 2243.08 |
| graph.filter_trajectories | 1 | 0.0746586 | 74.6586 | 74.6586 | not recorded | 74.6586 | 0.0673814 | 14840.9 | 0.0224605 | 44522.7 |
| graph.align_reference | 1 | 1.18328 | 1183.28 | 1183.28 | not recorded | 1183.28 | 1.06794 | 936.383 | 0.35598 | 2809.15 |
| graph.spatial_request | 1 | 0.000749833 | 0.749833 | 0.749833 | not recorded | 0.749833 | 0.000676745 | 1.47766e+06 | 0.000225582 | 4.43299e+06 |
| graph.reconstruction_input | 1 | 0.0102788 | 10.2788 | 10.2788 | not recorded | 10.2788 | 0.00927689 | 107795 | 0.0030923 | 323384 |
| graph.fit_model_dimensions | 1 | 0.149452 | 149.452 | 149.452 | not recorded | 149.452 | 0.134885 | 7413.74 | 0.0449616 | 22241.2 |
| graph.reconstruct_skeletons | 1 | 2.28914 | 2289.14 | 2289.14 | not recorded | 2289.14 | 2.06601 | 484.024 | 0.688671 | 1452.07 |
| graph.save_spatial | 1 | 4.0685 | 4068.5 | 4068.5 | not recorded | 4068.5 | 3.67193 | 272.336 | 1.22398 | 817.009 |
| graph.save_recording | 1 | 2.92957 | 2929.57 | 2929.57 | not recorded | 2929.57 | 2.64401 | 378.213 | 0.881338 | 1134.64 |
| graph.annotate_camera_1 | 1 | 13.4617 | 13461.7 | 13461.7 | not recorded | 13461.7 | 12.1496 | 82.3075 | 4.04985 | 246.923 |
| graph.annotate_camera_0 | 1 | 13.6043 | 13604.3 | 13604.3 | not recorded | 13604.3 | 12.2782 | 81.4449 | 4.09275 | 244.335 |
| graph.annotate_camera_2 | 1 | 10.3341 | 10334.1 | 10334.1 | not recorded | 10334.1 | 9.32682 | 107.218 | 3.10894 | 321.653 |
| export.channel_exports | 1 | 0.90251 | 902.51 | 902.51 | not recorded | 902.51 | 0.814539 | 1227.69 | 0.271513 | 3683.06 |
| export.blender | 1 | 6.78803 | 6788.03 | 6788.03 | not recorded | 6788.03 | 6.12638 | 163.228 | 2.04213 | 489.685 |
| exports.total | 1 | 6.78874 | 6788.74 | 6788.74 | not recorded | 6788.74 | 6.12702 | 163.211 | 2.04234 | 489.634 |

## sample_data — dataset_worker

Outcome: complete; wall: 115.179 s; 1108 synchronized frames / 3324 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| workflow.blender_preparation | 1 | 1.33478 | 1334.78 | 1334.78 | not recorded | 1334.78 | 1.20467 | 830.1 | 0.401558 | 2490.3 |
| workflow.inference_service_start | 1 | 8.2209e-05 | 0.082209 | 0.082209 | not recorded | 0.082209 | 7.41959e-05 | 1.34778e+07 | 2.4732e-05 | 4.04335e+07 |
| workflow.calibration | 1 | 23.8581 | 23858.1 | 23858.1 | not recorded | 23858.1 | 21.5326 | 46.4413 | 7.17752 | 139.324 |
| workflow.mocap | 1 | 77.5837 | 77583.7 | 77583.7 | not recorded | 77583.7 | 70.0213 | 14.2814 | 23.3404 | 42.8441 |
| workflow.numerical_validation | 1 | 0.841746 | 841.746 | 841.746 | not recorded | 841.746 | 0.759698 | 1316.31 | 0.253233 | 3948.94 |
| workflow.blender_validation | 1 | 9.95745 | 9957.45 | 9957.45 | not recorded | 9957.45 | 8.98686 | 111.274 | 2.99562 | 333.821 |
| workflow.output_acceptance | 1 | 0.0650375 | 65.0375 | 65.0375 | not recorded | 65.0375 | 0.0586981 | 17036.3 | 0.019566 | 51109 |
| workflow.shutdown | 1 | 0.000515959 | 0.515959 | 0.515959 | not recorded | 0.515959 | 0.000465667 | 2.14746e+06 | 0.000155222 | 6.44237e+06 |

Stage spans overlap and must not be summed. Per-frame/image costs are amortized over the recording, not latency percentiles. After first excludes exactly the first call; it does not assert steady state. Latency p50/p95/p99 were not recorded. Missing measurements are not zero.

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
