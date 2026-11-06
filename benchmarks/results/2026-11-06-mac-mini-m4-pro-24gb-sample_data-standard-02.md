# Machine benchmark: mac-mini-m4-pro-24gb

Run: 2026-11-06T12:50:35.802951+00:00 | passed
CPU: Apple M4 Pro | RAM: 24 GiB

AC power; shared desktop; cached model assets and managed Blender; fresh calibration each run; latest sfn26; sequential runs; standard scientific exports and bounded Blender GUI lifecycle enabled

| Workload | Status | Measurement | Value |
|---|---|---|---|
| sample_data | passed | worker_elapsed_s | 117.999 |
| sample_data | passed | synchronized_frames_per_worker_second | 9.38991 |
| sample_data | passed | camera_images_per_worker_second | 28.1697 |
| sample_data | passed | worker_amortized_ms_per_frame | 106.497 |
| sample_data | passed | worker_amortized_ms_per_image | 35.4991 |

## sample_data — posthoc

Outcome: complete; wall: 78.4366 s; 1108 synchronized frames / 3324 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| graph.camera_batch_wait | 1109 | 0.0261032 | 0.0235376 | 2.72758 | 0.0210972 | 2.72758 | 0.0235589 | 42446.8 | 0.00785296 | 127340 |
| inference.queue_wait | 1108 | 0.0258832 | 0.0233603 | 0.040042 | 0.0233452 | 0.126791 | 0.0233603 | 42807.7 | 0.00778676 | 128423 |
| inference.session_setup | 1 | 5.87074 | 5870.74 | 5870.74 | not recorded | 5870.74 | 5.2985 | 188.733 | 1.76617 | 566.198 |
| inference.process_batch.images=3 | 1108 | 40.3367 | 36.405 | 111.911 | 36.3368 | 186.012 | 36.405 | 27.4688 | 12.135 | 82.4063 |
| graph.load_and_track | 1 | 46.5567 | 46556.7 | 46556.7 | not recorded | 46556.7 | 42.0186 | 23.799 | 14.0062 | 71.3969 |
| graph.observation_request | 1 | 0.0509991 | 50.9991 | 50.9991 | not recorded | 50.9991 | 0.0460281 | 21725.9 | 0.0153427 | 65177.6 |
| graph.match_and_triangulate | 1 | 1.61316 | 1613.16 | 1613.16 | not recorded | 1613.16 | 1.45592 | 686.851 | 0.485307 | 2060.55 |
| graph.filter_trajectories | 1 | 0.0726426 | 72.6426 | 72.6426 | not recorded | 72.6426 | 0.0655619 | 15252.8 | 0.021854 | 45758.3 |
| graph.save_observations | 1 | 1.65302 | 1653.02 | 1653.02 | not recorded | 1653.02 | 1.49189 | 670.29 | 0.497297 | 2010.87 |
| graph.align_reference | 1 | 1.23258 | 1232.58 | 1232.58 | not recorded | 1232.58 | 1.11244 | 898.925 | 0.370813 | 2696.77 |
| graph.spatial_request | 1 | 0.00295912 | 2.95912 | 2.95912 | not recorded | 2.95912 | 0.00267069 | 374435 | 0.00089023 | 1.12331e+06 |
| graph.reconstruction_input | 1 | 0.00998988 | 9.98988 | 9.98988 | not recorded | 9.98988 | 0.00901613 | 110912 | 0.00300538 | 332737 |
| graph.fit_model_dimensions | 1 | 0.167581 | 167.581 | 167.581 | not recorded | 167.581 | 0.151247 | 6611.71 | 0.0504156 | 19835.1 |
| graph.reconstruct_skeletons | 1 | 2.41081 | 2410.81 | 2410.81 | not recorded | 2410.81 | 2.17582 | 459.596 | 0.725275 | 1378.79 |
| graph.save_spatial | 1 | 4.62282 | 4622.82 | 4622.82 | not recorded | 4622.82 | 4.17222 | 239.681 | 1.39074 | 719.042 |
| graph.save_recording | 1 | 3.19873 | 3198.73 | 3198.73 | not recorded | 3198.73 | 2.88694 | 346.387 | 0.962313 | 1039.16 |
| graph.annotate_camera_1 | 1 | 14.488 | 14488 | 14488 | not recorded | 14488 | 13.0758 | 76.477 | 4.35861 | 229.431 |
| graph.annotate_camera_0 | 1 | 14.5952 | 14595.2 | 14595.2 | not recorded | 14595.2 | 13.1726 | 75.9153 | 4.39086 | 227.746 |
| graph.annotate_camera_2 | 1 | 10.4584 | 10458.4 | 10458.4 | not recorded | 10458.4 | 9.43898 | 105.944 | 3.14633 | 317.831 |
| export.channel_exports | 1 | 0.893007 | 893.007 | 893.007 | not recorded | 893.007 | 0.805963 | 1240.75 | 0.268654 | 3722.25 |
| export.blender | 1 | 6.66152 | 6661.52 | 6661.52 | not recorded | 6661.52 | 6.0122 | 166.328 | 2.00407 | 498.985 |
| exports.total | 1 | 6.66258 | 6662.58 | 6662.58 | not recorded | 6662.58 | 6.01316 | 166.302 | 2.00439 | 498.906 |

## sample_data — dataset_worker

Outcome: complete; wall: 117.218 s; 1108 synchronized frames / 3324 camera images. Evidence: structured.

| Stage | Calls | Total s | Mean ms/call | First ms | After first ms | Max ms | Amortized ms/frame | Frames/s | Amortized ms/image | Images/s |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| workflow.blender_preparation | 1 | 1.39062 | 1390.62 | 1390.62 | not recorded | 1390.62 | 1.25507 | 796.766 | 0.418358 | 2390.3 |
| workflow.inference_service_start | 1 | 8.5583e-05 | 0.085583 | 0.085583 | not recorded | 0.085583 | 7.7241e-05 | 1.29465e+07 | 2.5747e-05 | 3.88395e+07 |
| workflow.calibration | 1 | 24.5571 | 24557.1 | 24557.1 | not recorded | 24557.1 | 22.1634 | 45.1194 | 7.3878 | 135.358 |
| workflow.mocap | 1 | 78.6033 | 78603.3 | 78603.3 | not recorded | 78603.3 | 70.9416 | 14.0961 | 23.6472 | 42.2883 |
| workflow.numerical_validation | 1 | 0.84154 | 841.54 | 841.54 | not recorded | 841.54 | 0.759512 | 1316.63 | 0.253171 | 3949.9 |
| workflow.blender_validation | 1 | 10.2163 | 10216.3 | 10216.3 | not recorded | 10216.3 | 9.2205 | 108.454 | 3.0735 | 325.362 |
| workflow.output_acceptance | 1 | 0.0653801 | 65.3801 | 65.3801 | not recorded | 65.3801 | 0.0590073 | 16947 | 0.0196691 | 50841.1 |
| workflow.shutdown | 1 | 0.000578417 | 0.578417 | 0.578417 | not recorded | 0.578417 | 0.000522037 | 1.91557e+06 | 0.000174012 | 5.74672e+06 |

Stage spans overlap and must not be summed. Per-frame/image costs are amortized over the recording, not latency percentiles. After first excludes exactly the first call; it does not assert steady state. Latency p50/p95/p99 were not recorded. Missing measurements are not zero.

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
