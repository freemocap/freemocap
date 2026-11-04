# Machine benchmark: windows-rtx3090

Run: 2026-11-04T16:59:55.942079+00:00 | failed
CPU: 12th Gen Intel(R) Core(TM) i9-12900KF | RAM: 127.796 GiB

Shared desktop; AC power; cached models and raw data; no concurrent agent training; fresh process and calibration; all standard exports and Blender auto-open enabled; GUI stdio detached from worker; prior intervention run excluded from throughput baseline

| Workload | Status | Measurement | Value |
|---|---|---|---|
| test_data | failed | worker_elapsed_s | 78.4631 |

## test_data — posthoc

Outcome: complete; wall: 36.0711 s; 222 synchronized frames / 666 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| graph.camera_batch_wait | 223 | 0.0261633 | 0.117324 | 12.2692 | 0.062586 | 12.2692 | 0.117853 | 8485.17 | 0.0392842 | 25455.5 |
| inference.queue_wait | 222 | 0.038703 | 0.174338 | 0.1698 | 0.174358 | 3.4562 | 0.174338 | 5735.99 | 0.0581126 | 17208 |
| inference.session_setup | 1 | 1.97714 | 1977.14 | 1977.14 | not recorded | 1977.14 | 8.90605 | 112.283 | 2.96868 | 336.85 |
| inference.process_batch.images=3 | 222 | 10.2729 | 46.2742 | 117.979 | 45.9497 | 117.979 | 46.2742 | 21.6103 | 15.4247 | 64.8309 |
| graph.load_and_track | 1 | 12.6831 | 12683.1 | 12683.1 | not recorded | 12683.1 | 57.1312 | 17.5036 | 19.0437 | 52.5107 |
| graph.observation_request | 1 | 0.134817 | 134.817 | 134.817 | not recorded | 134.817 | 0.607282 | 1646.68 | 0.202427 | 4940.04 |
| graph.save_observations | 1 | 0.707828 | 707.828 | 707.828 | not recorded | 707.828 | 3.18841 | 313.636 | 1.0628 | 940.907 |
| graph.match_and_triangulate | 1 | 0.876443 | 876.443 | 876.443 | not recorded | 876.443 | 3.94794 | 253.297 | 1.31598 | 759.89 |
| graph.filter_trajectories | 1 | 0.0324199 | 32.4199 | 32.4199 | not recorded | 32.4199 | 0.146036 | 6847.65 | 0.0486785 | 20542.9 |
| graph.align_reference | 1 | 1.06886 | 1068.86 | 1068.86 | not recorded | 1068.86 | 4.81469 | 207.698 | 1.6049 | 623.093 |
| graph.reconstruction_input | 1 | 0.0042903 | 4.2903 | 4.2903 | not recorded | 4.2903 | 0.0193257 | 51744.6 | 0.00644189 | 155234 |
| graph.spatial_request | 1 | 0.0110401 | 11.0401 | 11.0401 | not recorded | 11.0401 | 0.0497302 | 20108.5 | 0.0165767 | 60325.5 |
| graph.fit_model_dimensions | 1 | 0.719075 | 719.075 | 719.075 | not recorded | 719.075 | 3.23908 | 308.73 | 1.07969 | 926.19 |
| graph.reconstruct_skeletons | 1 | 2.58628 | 2586.28 | 2586.28 | not recorded | 2586.28 | 11.6499 | 85.8376 | 3.8833 | 257.513 |
| graph.save_spatial | 1 | 3.94216 | 3942.16 | 3942.16 | not recorded | 3942.16 | 17.7575 | 56.3143 | 5.91916 | 168.943 |
| graph.annotate_camera_0 | 1 | 7.48438 | 7484.38 | 7484.38 | not recorded | 7484.38 | 33.7134 | 29.6618 | 11.2378 | 88.9853 |
| graph.annotate_camera_1 | 1 | 7.48988 | 7489.88 | 7489.88 | not recorded | 7489.88 | 33.7382 | 29.64 | 11.2461 | 88.92 |
| graph.save_recording | 1 | 2.28076 | 2280.76 | 2280.76 | not recorded | 2280.76 | 10.2737 | 97.3361 | 3.42456 | 292.008 |
| graph.annotate_camera_2 | 1 | 4.09861 | 4098.61 | 4098.61 | not recorded | 4098.61 | 18.4622 | 54.1647 | 6.15407 | 162.494 |
| export.channel_exports | 1 | 0.504439 | 504.439 | 504.439 | not recorded | 504.439 | 2.27225 | 440.093 | 0.757415 | 1320.28 |
| export.blender | 1 | 11.2302 | 11230.2 | 11230.2 | not recorded | 11230.2 | 50.5865 | 19.7681 | 16.8622 | 59.3043 |
| exports.total | 1 | 11.2324 | 11232.4 | 11232.4 | not recorded | 11232.4 | 50.5965 | 19.7642 | 16.8655 | 59.2927 |

## test_data — dataset_worker

Outcome: complete; wall: 76.2367 s; 222 synchronized frames / 666 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| workflow.blender_preparation | 1 | 3.89461 | 3894.61 | 3894.61 | not recorded | 3894.61 | 17.5433 | 57.0018 | 5.84776 | 171.006 |
| workflow.inference_service_start | 1 | 0.0003083 | 0.3083 | 0.3083 | not recorded | 0.3083 | 0.00138874 | 720078 | 0.000462913 | 2.16023e+06 |
| workflow.calibration | 1 | 24.2744 | 24274.4 | 24274.4 | not recorded | 24274.4 | 109.344 | 9.14542 | 36.4481 | 27.4363 |
| workflow.mocap | 1 | 36.5468 | 36546.8 | 36546.8 | not recorded | 36546.8 | 164.625 | 6.0744 | 54.8751 | 18.2232 |
| workflow.numerical_validation | 1 | 0.569046 | 569.046 | 569.046 | not recorded | 569.046 | 2.56327 | 390.126 | 0.854424 | 1170.38 |
| workflow.blender_validation | 1 | 7.1287 | 7128.7 | 7128.7 | not recorded | 7128.7 | 32.1113 | 31.1417 | 10.7038 | 93.4251 |
| workflow.output_acceptance | 1 | 0.0285043 | 28.5043 | 28.5043 | not recorded | 28.5043 | 0.128398 | 7788.3 | 0.0427992 | 23364.9 |
| workflow.shutdown | 1 | 0.0005989 | 0.5989 | 0.5989 | not recorded | 0.5989 | 0.00269775 | 370680 | 0.000899249 | 1.11204e+06 |

Stage spans overlap and must not be summed. Per-frame/image costs are amortized over the recording, not latency percentiles. After first excludes exactly the first call; it does not assert steady state. Latency p50/p95/p99 were not recorded. Missing measurements are not zero.

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
