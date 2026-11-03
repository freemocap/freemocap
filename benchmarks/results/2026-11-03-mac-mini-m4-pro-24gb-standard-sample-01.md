# Machine benchmark: mac-mini-m4-pro-24gb

Run: 2026-11-03T13:01:43.904493+00:00 | passed
CPU: Apple M4 Pro | RAM: 24 GiB

Shared desktop; cached tracking models and automatically prepared Blender package/profile; fresh full standard workflow with Blender scene export and reopen validation.

| Workload | Status | Measurement | Value |
|---|---|---|---|
| sample_data | passed | worker_elapsed_s | 245.851 |
| sample_data | passed | synchronized_frames_per_worker_second | 4.50679 |
| sample_data | passed | camera_images_per_worker_second | 13.5204 |

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
