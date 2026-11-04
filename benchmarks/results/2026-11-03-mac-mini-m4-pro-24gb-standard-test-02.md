# Machine benchmark: mac-mini-m4-pro-24gb

Run: 2026-11-03T12:59:51.828322+00:00 | passed
CPU: Apple M4 Pro | RAM: 24 GiB

Shared desktop; cached tracking models; full standard workflow after correcting Core platform dispatch; automatic Blender setup included.

| Workload | Status | Measurement | Value |
|---|---|---|---|
| test_data | passed | worker_elapsed_s | 67.5521 |
| test_data | passed | synchronized_frames_per_worker_second | 3.28635 |
| test_data | passed | camera_images_per_worker_second | 9.85906 |

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
