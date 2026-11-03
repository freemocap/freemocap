# Machine benchmark: mac-mini-m4-pro-24gb

Run: 2026-11-03T12:26:29.149538+00:00 | passed
CPU: arm | RAM: 24 GiB

Shared desktop with other agents/apps active; AC power; cached model assets; fresh calibration and processing; Blender excluded.

| Workload | Status | Measurement | Value |
|---|---|---|---|
| test_data | passed | worker_elapsed_s | 53.7119 |
| test_data | passed | synchronized_frames_per_worker_second | 4.13316 |
| test_data | passed | camera_images_per_worker_second | 12.3995 |

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
