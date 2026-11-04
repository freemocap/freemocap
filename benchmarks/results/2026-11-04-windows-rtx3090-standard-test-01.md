# Machine benchmark: windows-rtx3090

Run: 2026-11-04T17:04:20.413958+00:00 | passed
CPU: 12th Gen Intel(R) Core(TM) i9-12900KF | RAM: 127.796 GiB

Shared desktop; AC power; cached models and raw data; no concurrent agent training; fresh process and calibration; all standard exports; Blender automatically opened at final promoted path with detached stdio; concurrent isolated browser check during startup

| Workload | Status | Measurement | Value |
|---|---|---|---|
| test_data | passed | worker_elapsed_s | 55.3011 |
| test_data | passed | synchronized_frames_per_worker_second | 4.01439 |
| test_data | passed | camera_images_per_worker_second | 12.0432 |
| test_data | passed | worker_amortized_ms_per_frame | 249.104 |
| test_data | passed | worker_amortized_ms_per_image | 83.0347 |

## test_data — posthoc

Outcome: complete; wall: 29.7426 s; 222 synchronized frames / 666 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| graph.camera_batch_wait | 223 | 0.0197508 | 0.0885686 | 10.4085 | 0.0420824 | 10.4085 | 0.0889676 | 11240.1 | 0.0296559 | 33720.2 |
| inference.queue_wait | 222 | 0.0271544 | 0.122317 | 0.1363 | 0.122254 | 2.3181 | 0.122317 | 8175.47 | 0.0407724 | 24526.4 |
| inference.session_setup | 1 | 1.30064 | 1300.64 | 1300.64 | not recorded | 1300.64 | 5.85872 | 170.686 | 1.95291 | 512.057 |
| inference.process_batch.images=3 | 222 | 7.80471 | 35.1563 | 85.4579 | 34.9287 | 85.4579 | 35.1563 | 28.4444 | 11.7188 | 85.3331 |
| graph.load_and_track | 1 | 9.46179 | 9461.79 | 9461.79 | not recorded | 9461.79 | 42.6207 | 23.4628 | 14.2069 | 70.3884 |
| graph.observation_request | 1 | 0.158563 | 158.563 | 158.563 | not recorded | 158.563 | 0.714249 | 1400.07 | 0.238083 | 4200.22 |
| graph.save_observations | 1 | 0.629992 | 629.992 | 629.992 | not recorded | 629.992 | 2.8378 | 352.386 | 0.945933 | 1057.16 |
| graph.match_and_triangulate | 1 | 0.809723 | 809.723 | 809.723 | not recorded | 809.723 | 3.6474 | 274.168 | 1.2158 | 822.504 |
| graph.filter_trajectories | 1 | 0.019688 | 19.688 | 19.688 | not recorded | 19.688 | 0.0886847 | 11275.9 | 0.0295616 | 33827.7 |
| graph.align_reference | 1 | 0.70582 | 705.82 | 705.82 | not recorded | 705.82 | 3.17937 | 314.528 | 1.05979 | 943.584 |
| graph.reconstruction_input | 1 | 0.0044799 | 4.4799 | 4.4799 | not recorded | 4.4799 | 0.0201797 | 49554.7 | 0.00672658 | 148664 |
| graph.spatial_request | 1 | 0.0051552 | 5.1552 | 5.1552 | not recorded | 5.1552 | 0.0232216 | 43063.3 | 0.00774054 | 129190 |
| graph.fit_model_dimensions | 1 | 0.167798 | 167.798 | 167.798 | not recorded | 167.798 | 0.755848 | 1323.02 | 0.251949 | 3969.05 |
| graph.reconstruct_skeletons | 1 | 1.51052 | 1510.52 | 1510.52 | not recorded | 1510.52 | 6.80416 | 146.969 | 2.26805 | 440.907 |
| graph.save_spatial | 1 | 2.44226 | 2442.26 | 2442.26 | not recorded | 2442.26 | 11.0012 | 90.8995 | 3.66706 | 272.698 |
| graph.annotate_camera_1 | 1 | 5.45794 | 5457.94 | 5457.94 | not recorded | 5457.94 | 24.5853 | 40.6747 | 8.1951 | 122.024 |
| graph.annotate_camera_0 | 1 | 5.51111 | 5511.11 | 5511.11 | not recorded | 5511.11 | 24.8248 | 40.2822 | 8.27494 | 120.847 |
| graph.save_recording | 1 | 2.08472 | 2084.72 | 2084.72 | not recorded | 2084.72 | 9.39064 | 106.489 | 3.13021 | 319.467 |
| graph.annotate_camera_2 | 1 | 4.07851 | 4078.51 | 4078.51 | not recorded | 4078.51 | 18.3717 | 54.4317 | 6.12389 | 163.295 |
| export.channel_exports | 1 | 0.50818 | 508.18 | 508.18 | not recorded | 508.18 | 2.2891 | 436.854 | 0.763032 | 1310.56 |
| export.blender | 1 | 10.2891 | 10289.1 | 10289.1 | not recorded | 10289.1 | 46.3474 | 21.5762 | 15.4491 | 64.7285 |
| exports.total | 1 | 10.2912 | 10291.2 | 10291.2 | not recorded | 10291.2 | 46.3567 | 21.5718 | 15.4522 | 64.7155 |

## test_data — dataset_worker

Outcome: complete; wall: 53.5448 s; 222 synchronized frames / 666 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| workflow.blender_preparation | 1 | 3.43007 | 3430.07 | 3430.07 | not recorded | 3430.07 | 15.4508 | 64.7217 | 5.15026 | 194.165 |
| workflow.inference_service_start | 1 | 0.0002475 | 0.2475 | 0.2475 | not recorded | 0.2475 | 0.00111486 | 896970 | 0.000371622 | 2.69091e+06 |
| workflow.calibration | 1 | 11.141 | 11141 | 11141 | not recorded | 11141 | 50.1848 | 19.9263 | 16.7283 | 59.779 |
| workflow.mocap | 1 | 30.0946 | 30094.6 | 30094.6 | not recorded | 30094.6 | 135.561 | 7.37675 | 45.187 | 22.1302 |
| workflow.numerical_validation | 1 | 0.50837 | 508.37 | 508.37 | not recorded | 508.37 | 2.28995 | 436.69 | 0.763318 | 1310.07 |
| workflow.blender_validation | 1 | 5.09967 | 5099.67 | 5099.67 | not recorded | 5099.67 | 22.9715 | 43.5322 | 7.65716 | 130.597 |
| workflow.output_acceptance | 1 | 0.0256259 | 25.6259 | 25.6259 | not recorded | 25.6259 | 0.115432 | 8663.11 | 0.0384773 | 25989.3 |
| workflow.shutdown | 1 | 0.0005372 | 0.5372 | 0.5372 | not recorded | 0.5372 | 0.00241982 | 413254 | 0.000806607 | 1.23976e+06 |

Stage spans overlap and must not be summed. Per-frame/image costs are amortized over the recording, not latency percentiles. After first excludes exactly the first call; it does not assert steady state. Latency p50/p95/p99 were not recorded. Missing measurements are not zero.

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
