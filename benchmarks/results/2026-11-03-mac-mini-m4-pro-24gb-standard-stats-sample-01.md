# Machine benchmark: mac-mini-m4-pro-24gb

Run: 2026-11-03T13:30:23.221227+00:00 | passed
CPU: Apple M4 Pro | RAM: 24 GiB

AC power; shared desktop and other agents active; cached models and managed Blender package; fresh calibration; detailed timing instrumentation

| Workload | Status | Measurement | Value |
|---|---|---|---|
| sample_data | passed | worker_elapsed_s | 244.811 |
| sample_data | passed | synchronized_frames_per_worker_second | 4.52594 |
| sample_data | passed | camera_images_per_worker_second | 13.5778 |
| sample_data | passed | worker_amortized_ms_per_frame | 220.949 |
| sample_data | passed | worker_amortized_ms_per_image | 73.6496 |

## sample_data — posthoc

Outcome: complete; wall: 205.729 s; 1108 synchronized frames / 3324 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Amortized ms/image |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| graph.camera_batch_wait | 1109 | 0.0267198 | 0.0240936 | 2.89733 | 0.0215004 | 2.89733 | 0.0241153 | 0.00803844 |
| inference.queue_wait | 1108 | 0.0253751 | 0.0229017 | 0.030875 | 0.0228945 | 0.158458 | 0.0229017 | 0.00763391 |
| inference.session_setup | 1 | 0.970137 | 970.137 | 970.137 | not recorded | 970.137 | 0.875574 | 0.291858 |
| inference.process_batch.images=3 | 1108 | 173.138 | 156.261 | 875 | 155.612 | 897.134 | 156.261 | 52.0871 |
| graph.load_and_track | 1 | 174.436 | 174436 | 174436 | not recorded | 174436 | 157.433 | 52.4777 |
| graph.observation_request | 1 | 0.0560925 | 56.0925 | 56.0925 | not recorded | 56.0925 | 0.050625 | 0.016875 |
| graph.save_observations | 1 | 1.6341 | 1634.1 | 1634.1 | not recorded | 1634.1 | 1.47482 | 0.491608 |
| graph.match_and_triangulate | 1 | 1.79952 | 1799.52 | 1799.52 | not recorded | 1799.52 | 1.62411 | 0.541372 |
| graph.filter_trajectories | 1 | 0.0502747 | 50.2747 | 50.2747 | not recorded | 50.2747 | 0.0453743 | 0.0151248 |
| graph.align_reference | 1 | 1.26091 | 1260.91 | 1260.91 | not recorded | 1260.91 | 1.138 | 0.379334 |
| graph.spatial_request | 1 | 0.000811 | 0.811 | 0.811 | not recorded | 0.811 | 0.000731949 | 0.000243983 |
| graph.reconstruction_input | 1 | 0.00814904 | 8.14904 | 8.14904 | not recorded | 8.14904 | 0.00735473 | 0.00245158 |
| graph.fit_model_dimensions | 1 | 0.150684 | 150.684 | 150.684 | not recorded | 150.684 | 0.135997 | 0.0453323 |
| graph.reconstruct_skeletons | 1 | 2.33994 | 2339.94 | 2339.94 | not recorded | 2339.94 | 2.11186 | 0.703952 |
| graph.save_spatial | 1 | 4.21623 | 4216.23 | 4216.23 | not recorded | 4216.23 | 3.80526 | 1.26842 |
| graph.save_recording | 1 | 3.05961 | 3059.61 | 3059.61 | not recorded | 3059.61 | 2.76138 | 0.920459 |
| graph.annotate_camera_1 | 1 | 13.8992 | 13899.2 | 13899.2 | not recorded | 13899.2 | 12.5444 | 4.18146 |
| graph.annotate_camera_0 | 1 | 14.0244 | 14024.4 | 14024.4 | not recorded | 14024.4 | 12.6574 | 4.21914 |
| graph.annotate_camera_2 | 1 | 10.4399 | 10439.9 | 10439.9 | not recorded | 10439.9 | 9.42229 | 3.14076 |
| export.blender | 1 | 6.69311 | 6693.11 | 6693.11 | not recorded | 6693.11 | 6.04071 | 2.01357 |
| exports.total | 1 | 6.69363 | 6693.63 | 6693.63 | not recorded | 6693.63 | 6.04118 | 2.01373 |

## sample_data — dataset_worker

Outcome: complete; wall: 244.02 s; 1108 synchronized frames / 3324 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Amortized ms/image |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| workflow.blender_preparation | 1 | 1.37624 | 1376.24 | 1376.24 | not recorded | 1376.24 | 1.24209 | 0.414031 |
| workflow.inference_service_start | 1 | 8.4125e-05 | 0.084125 | 0.084125 | not recorded | 0.084125 | 7.59251e-05 | 2.53084e-05 |
| workflow.calibration | 1 | 24.1834 | 24183.4 | 24183.4 | not recorded | 24183.4 | 21.8262 | 7.27541 |
| workflow.mocap | 1 | 206.003 | 206003 | 206003 | not recorded | 206003 | 185.924 | 61.9746 |
| workflow.numerical_validation | 1 | 0.858796 | 858.796 | 858.796 | not recorded | 858.796 | 0.775086 | 0.258362 |
| workflow.blender_validation | 1 | 10.05 | 10050 | 10050 | not recorded | 10050 | 9.07041 | 3.02347 |
| workflow.output_acceptance | 1 | 0.0649156 | 64.9156 | 64.9156 | not recorded | 64.9156 | 0.0585881 | 0.0195294 |
| workflow.shutdown | 1 | 0.000532875 | 0.532875 | 0.532875 | not recorded | 0.532875 | 0.000480934 | 0.000160311 |

Stage spans overlap and must not be summed. Per-frame/image costs are amortized over the recording, not latency percentiles. After first excludes exactly the first call; it does not assert steady state. Latency p50/p95/p99 were not recorded. Missing measurements are not zero.

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
