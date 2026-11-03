# Machine benchmark: mac-mini-m4-pro-24gb

Run: 2026-11-03T13:29:10.690384+00:00 | passed
CPU: Apple M4 Pro | RAM: 24 GiB

AC power; shared desktop and other agents active; cached models and managed Blender package; fresh calibration; detailed timing instrumentation

| Workload | Status | Measurement | Value |
|---|---|---|---|
| test_data | passed | worker_elapsed_s | 62.6139 |
| test_data | passed | synchronized_frames_per_worker_second | 3.54554 |
| test_data | passed | camera_images_per_worker_second | 10.6366 |
| test_data | passed | worker_amortized_ms_per_frame | 282.045 |
| test_data | passed | worker_amortized_ms_per_image | 94.0148 |

## test_data — posthoc

Outcome: complete; wall: 50.4135 s; 222 synchronized frames / 666 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Amortized ms/image |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| graph.camera_batch_wait | 223 | 0.00689325 | 0.0309114 | 2.41979 | 0.0201507 | 2.41979 | 0.0310507 | 0.0103502 |
| inference.queue_wait | 222 | 0.00578791 | 0.0260717 | 0.036958 | 0.0260224 | 0.549375 | 0.0260717 | 0.00869056 |
| inference.session_setup | 1 | 1.01265 | 1012.65 | 1012.65 | not recorded | 1012.65 | 4.56149 | 1.5205 |
| inference.process_batch.images=3 | 222 | 38.7187 | 174.408 | 857.169 | 171.319 | 869.683 | 174.408 | 58.1361 |
| graph.load_and_track | 1 | 39.8322 | 39832.2 | 39832.2 | not recorded | 39832.2 | 179.424 | 59.8082 |
| graph.observation_request | 1 | 0.0413256 | 41.3256 | 41.3256 | not recorded | 41.3256 | 0.186151 | 0.0620505 |
| graph.save_observations | 1 | 0.233758 | 233.758 | 233.758 | not recorded | 233.758 | 1.05296 | 0.350987 |
| graph.match_and_triangulate | 1 | 0.375984 | 375.984 | 375.984 | not recorded | 375.984 | 1.69362 | 0.56454 |
| graph.filter_trajectories | 1 | 0.00904958 | 9.04958 | 9.04958 | not recorded | 9.04958 | 0.0407639 | 0.013588 |
| graph.align_reference | 1 | 0.242152 | 242.152 | 242.152 | not recorded | 242.152 | 1.09078 | 0.363592 |
| graph.spatial_request | 1 | 0.000629958 | 0.629958 | 0.629958 | not recorded | 0.629958 | 0.00283765 | 0.000945883 |
| graph.reconstruction_input | 1 | 0.00116958 | 1.16958 | 1.16958 | not recorded | 1.16958 | 0.00526839 | 0.00175613 |
| graph.fit_model_dimensions | 1 | 0.0703236 | 70.3236 | 70.3236 | not recorded | 70.3236 | 0.316773 | 0.105591 |
| graph.reconstruct_skeletons | 1 | 0.55454 | 554.54 | 554.54 | not recorded | 554.54 | 2.49793 | 0.832642 |
| graph.save_spatial | 1 | 1.01281 | 1012.81 | 1012.81 | not recorded | 1012.81 | 4.5622 | 1.52073 |
| graph.save_recording | 1 | 0.732674 | 732.674 | 732.674 | not recorded | 732.674 | 3.30034 | 1.10011 |
| graph.annotate_camera_1 | 1 | 3.44959 | 3449.59 | 3449.59 | not recorded | 3449.59 | 15.5387 | 5.17956 |
| graph.annotate_camera_0 | 1 | 3.45256 | 3452.56 | 3452.56 | not recorded | 3452.56 | 15.5521 | 5.18403 |
| graph.annotate_camera_2 | 1 | 2.60153 | 2601.53 | 2601.53 | not recorded | 2601.53 | 11.7186 | 3.90621 |
| export.blender | 1 | 4.28277 | 4282.77 | 4282.77 | not recorded | 4282.77 | 19.2918 | 6.43059 |
| exports.total | 1 | 4.28322 | 4283.22 | 4283.22 | not recorded | 4283.22 | 19.2938 | 6.43127 |

## test_data — dataset_worker

Outcome: complete; wall: 62.2148 s; 222 synchronized frames / 666 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Amortized ms/image |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| workflow.blender_preparation | 1 | 1.36081 | 1360.81 | 1360.81 | not recorded | 1360.81 | 6.12979 | 2.04326 |
| workflow.inference_service_start | 1 | 8.0834e-05 | 0.080834 | 0.080834 | not recorded | 0.080834 | 0.000364117 | 0.000121372 |
| workflow.calibration | 1 | 6.0073 | 6007.3 | 6007.3 | not recorded | 6007.3 | 27.0599 | 9.01997 |
| workflow.mocap | 1 | 50.652 | 50652 | 50652 | not recorded | 50652 | 228.162 | 76.0541 |
| workflow.numerical_validation | 1 | 0.211784 | 211.784 | 211.784 | not recorded | 211.784 | 0.953984 | 0.317995 |
| workflow.blender_validation | 1 | 2.5635 | 2563.5 | 2563.5 | not recorded | 2563.5 | 11.5473 | 3.84909 |
| workflow.output_acceptance | 1 | 0.0129072 | 12.9072 | 12.9072 | not recorded | 12.9072 | 0.0581404 | 0.0193801 |
| workflow.shutdown | 1 | 0.000534792 | 0.534792 | 0.534792 | not recorded | 0.534792 | 0.00240897 | 0.000802991 |

Stage spans overlap and must not be summed. Per-frame/image costs are amortized over the recording, not latency percentiles. After first excludes exactly the first call; it does not assert steady state. Latency p50/p95/p99 were not recorded. Missing measurements are not zero.

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
