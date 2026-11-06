# Machine benchmark: mac-mini-m4-pro-24gb

Run: 2026-11-06T12:49:51.753786+00:00 | passed
CPU: Apple M4 Pro | RAM: 24 GiB

AC power; shared desktop; cached model assets and managed Blender; fresh calibration each run; latest sfn26; sequential runs; standard scientific exports and bounded Blender GUI lifecycle enabled

| Workload | Status | Measurement | Value |
|---|---|---|---|
| test_data | passed | worker_elapsed_s | 37.2051 |
| test_data | passed | synchronized_frames_per_worker_second | 5.96692 |
| test_data | passed | camera_images_per_worker_second | 17.9008 |
| test_data | passed | worker_amortized_ms_per_frame | 167.591 |
| test_data | passed | worker_amortized_ms_per_image | 55.8635 |

## test_data — posthoc

Outcome: complete; wall: 24.627 s; 222 synchronized frames / 666 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| graph.camera_batch_wait | 223 | 0.00702968 | 0.0315232 | 2.3075 | 0.0212711 | 2.3075 | 0.0316652 | 31580.4 | 0.0105551 | 94741.2 |
| inference.queue_wait | 222 | 0.0056215 | 0.0253221 | 0.045542 | 0.0252306 | 0.130833 | 0.0253221 | 39491.2 | 0.00844069 | 118474 |
| inference.session_setup | 1 | 5.94227 | 5942.27 | 5942.27 | not recorded | 5942.27 | 26.767 | 37.3594 | 8.92233 | 112.078 |
| inference.process_batch.images=3 | 222 | 8.21902 | 37.0226 | 112.019 | 36.6833 | 112.019 | 37.0226 | 27.0105 | 12.3409 | 81.0315 |
| graph.load_and_track | 1 | 14.286 | 14286 | 14286 | not recorded | 14286 | 64.3515 | 15.5396 | 21.4505 | 46.6189 |
| graph.observation_request | 1 | 0.0301443 | 30.1443 | 30.1443 | not recorded | 30.1443 | 0.135785 | 7364.59 | 0.0452616 | 22093.8 |
| graph.save_observations | 1 | 0.25128 | 251.28 | 251.28 | not recorded | 251.28 | 1.13189 | 883.477 | 0.377297 | 2650.43 |
| graph.match_and_triangulate | 1 | 0.377035 | 377.035 | 377.035 | not recorded | 377.035 | 1.69835 | 588.805 | 0.566118 | 1766.42 |
| graph.filter_trajectories | 1 | 0.00890988 | 8.90988 | 8.90988 | not recorded | 8.90988 | 0.0401346 | 24916.2 | 0.0133782 | 74748.5 |
| graph.align_reference | 1 | 0.304901 | 304.901 | 304.901 | not recorded | 304.901 | 1.37343 | 728.106 | 0.457809 | 2184.32 |
| graph.reconstruction_input | 1 | 0.000955875 | 0.955875 | 0.955875 | not recorded | 0.955875 | 0.00430574 | 232248 | 0.00143525 | 696744 |
| graph.spatial_request | 1 | 0.000878916 | 0.878916 | 0.878916 | not recorded | 0.878916 | 0.00395908 | 252584 | 0.00131969 | 757752 |
| graph.fit_model_dimensions | 1 | 0.0741828 | 74.1828 | 74.1828 | not recorded | 74.1828 | 0.334157 | 2992.61 | 0.111386 | 8977.83 |
| graph.reconstruct_skeletons | 1 | 0.573277 | 573.277 | 573.277 | not recorded | 573.277 | 2.58233 | 387.247 | 0.860777 | 1161.74 |
| graph.save_spatial | 1 | 0.984808 | 984.808 | 984.808 | not recorded | 984.808 | 4.43607 | 225.425 | 1.47869 | 676.274 |
| graph.save_recording | 1 | 0.674846 | 674.846 | 674.846 | not recorded | 674.846 | 3.03985 | 328.964 | 1.01328 | 986.892 |
| graph.annotate_camera_1 | 1 | 3.32455 | 3324.55 | 3324.55 | not recorded | 3324.55 | 14.9754 | 66.776 | 4.99181 | 200.328 |
| graph.annotate_camera_0 | 1 | 3.37959 | 3379.59 | 3379.59 | not recorded | 3379.59 | 15.2234 | 65.6884 | 5.07447 | 197.065 |
| graph.annotate_camera_2 | 1 | 2.44543 | 2445.43 | 2445.43 | not recorded | 2445.43 | 11.0154 | 90.7817 | 3.67181 | 272.345 |
| export.channel_exports | 1 | 0.249611 | 249.611 | 249.611 | not recorded | 249.611 | 1.12437 | 889.385 | 0.374791 | 2668.15 |
| export.blender | 1 | 4.31705 | 4317.05 | 4317.05 | not recorded | 4317.05 | 19.4462 | 51.424 | 6.48205 | 154.272 |
| exports.total | 1 | 4.3177 | 4317.7 | 4317.7 | not recorded | 4317.7 | 19.4491 | 51.4163 | 6.48303 | 154.249 |

## test_data — dataset_worker

Outcome: complete; wall: 36.8043 s; 222 synchronized frames / 666 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| workflow.blender_preparation | 1 | 1.37149 | 1371.49 | 1371.49 | not recorded | 1371.49 | 6.1779 | 161.867 | 2.0593 | 485.602 |
| workflow.inference_service_start | 1 | 6.0375e-05 | 0.060375 | 0.060375 | not recorded | 0.060375 | 0.000271959 | 3.67702e+06 | 9.06531e-05 | 1.10311e+07 |
| workflow.calibration | 1 | 6.07783 | 6077.83 | 6077.83 | not recorded | 6077.83 | 27.3776 | 36.5262 | 9.12586 | 109.579 |
| workflow.mocap | 1 | 24.8623 | 24862.3 | 24862.3 | not recorded | 24862.3 | 111.992 | 8.92919 | 37.3308 | 26.7876 |
| workflow.numerical_validation | 1 | 0.207123 | 207.123 | 207.123 | not recorded | 207.123 | 0.932988 | 1071.83 | 0.310996 | 3215.48 |
| workflow.blender_validation | 1 | 2.66766 | 2667.66 | 2667.66 | not recorded | 2667.66 | 12.0165 | 83.219 | 4.0055 | 249.657 |
| workflow.output_acceptance | 1 | 0.0137978 | 13.7978 | 13.7978 | not recorded | 13.7978 | 0.0621524 | 16089.5 | 0.0207175 | 48268.4 |
| workflow.shutdown | 1 | 0.000494 | 0.494 | 0.494 | not recorded | 0.494 | 0.00222523 | 449393 | 0.000741742 | 1.34818e+06 |

Stage spans overlap and must not be summed. Per-frame/image costs are amortized over the recording, not latency percentiles. After first excludes exactly the first call; it does not assert steady state. Latency p50/p95/p99 were not recorded. Missing measurements are not zero.

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
