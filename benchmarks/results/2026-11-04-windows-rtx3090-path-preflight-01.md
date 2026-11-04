# Machine benchmark: windows-rtx3090

Run: 2026-11-04T16:55:13.138639+00:00 | failed
CPU: 12th Gen Intel(R) Core(TM) i9-12900KF | RAM: 127.796 GiB

Shared desktop; AC power; existing models and raw reference data; first measured process; no concurrent agent training; GPU precheck31percent and4572MiB; all standard exports and Blender auto-open enabled

| Workload | Status | Measurement | Value |
|---|---|---|---|
| test_data | failed | measurements | unavailable |

Stage spans overlap and must not be summed. Per-frame/image costs are amortized over the recording, not latency percentiles. After first excludes exactly the first call; it does not assert steady state. Latency p50/p95/p99 were not recorded. Missing measurements are not zero.

Worker timing includes setup, calibration, processing, validation and shutdown; it is not realtime inference FPS.
Camera measurements come from the existing suite; differing devices are retained as context.
Failed cases are evidence, not successful throughput. Shared-machine load and first-run caches affect results.
