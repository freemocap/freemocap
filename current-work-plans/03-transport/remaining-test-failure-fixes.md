# Remaining test failure fixes

The owner approved fixing all 24 failures identified after the API cleanup.
Work remains local and uncommitted in the existing cleanup worktrees.

## Approved execution checklist

- [x] **1.** Repair logging fixtures, typed mocks, stale inputs, and assertions; rerun to expose any further masked failures.
- [x] **2.** Fix time conversion and timebase deserialization.
- [x] **3.** Resolve and implement the PubSub overwrite contract.
- [x] **4.** Replace the ambiguous scale test with explicit cold-start and temporal-stability checks.
- [x] **5.** Rerun the full suites and affected recording/timestamp workflows.

## Changes

### SkellyCam

- Lightweight tests now register the normal custom logging levels and supply an
  isolated logging queue, without installing file handlers. Fixture teardown
  restores logger methods and closes the queue. PubSub managers close their
  subscriptions after each test.
- WebSocket fixtures use a CameraBackendManager-specified mock. The state test
  asserts the actual message and camera state instead of swallowing exceptions;
  endpoint tests have a timeout. Invalid-input tests assert the existing runtime
  type-checking contract. Camera configuration, filename, integer timestamp, and
  shutdown signal fixtures match the current implementation.
- Millisecond conversion returns integer nanoseconds: Python ints for scalars,
  int64 arrays preserving input shape. Floating inputs round to nearest with ties
  to even; integer inputs avoid a float intermediate. Nonfinite values and signed
  64-bit overflow are rejected. Tests cover zero-dimensional and empty arrays,
  positive/negative rounding, integer precision near the range limit, and oversized
  Python/NumPy integers.
- Timebase deserialization accepts a scalar record, a zero-dimensional record
  array, or the one-row array produced by its writer. It extracts scalar fields
  without a float conversion and rejects empty, multi-row, or ambiguous shapes.
- The unused PubSub overwrite option was removed. Repository consumer searches
  found no production call to it; the separate shared-memory frame overwrite
  mechanism is unchanged. Publication now has one contract: enqueue every message
  for every subscriber without draining pending messages. A 100-message burst
  verifies ordering and completeness for two subscribers without feeder sleeps.

### Core scale acceptance

The numerical scale algorithm and the existing 5% temporal tolerance are unchanged.
The previous test compared two independent cold starts with different visible
anatomy from a non-template-proportioned subject. It has been replaced by:

- A partial-view cold-start check: plausible stature, no invented lower-leg/foot
  measurements, and unobserved segment lengths derived from the estimated scale
  and authored proportions.
- A temporal check: build a complete observation window, hide the lower-body
  points for twice that window, then restore them. Scale and leg/foot dimensions
  must remain within 5% of the established fit throughout.

The existing SkellyForge proportional-geometry tests continue to assert exact
recovery from known geometry, including partial visibility. All 14 pass. The five
core mapping/scale checks pass.

## Validation

All 24 original failures are resolved. Final validation on 2026-10-31:

| Validation | Result |
| --- | --- |
| Complete core suite, including reference-recording acceptance, both Blender import routes, and frozen backend | 1,246 passed; 117 subtests passed |
| Fresh posthoc producer (run separately to isolate generated outputs) | 1 passed |
| Complete SkellyCam suite | 378 passed; 1 hardware opt-in skip |
| Skipped native-camera lifecycle test, rerun with camera index 0 enabled | 1 passed |
| Complete SkellyForge suite | 903 passed; 1 skip: shipped model has no adjacent rigid-fit pairs |
| Complete browser suite | 87 passed |
| Physical recording and persisted timestamp/video audit, Python and Rust backends | Both passed |
| Physical tracking/recording and video audit, Python and Rust backends | Both passed |

All four physical harness runs reported server cleanup with exit code 0 and no
cleanup errors. Core emitted 32 warnings but no failures or skips. The remaining
Forge skip has a missing model prerequisite; it is not a failing assertion.
Critical Python lint checks and diff whitespace checks passed. No generated
artifacts appeared among the worktrees' untracked files.

Focused results: 104 repaired-fixture checks
passed (only the three then-pending timestamp failures remained); 46 timestamp,
metadata, and recording-reader checks passed; 35 PubSub/WebSocket/manager/worker
checks passed; 47 final timestamp/PubSub boundary checks passed.

Logs and JUnit reports are retained outside the repositories at
`C:/Users/jonma/AppData/Local/Temp/fmc-fixes-e68bfa1d`.
Real-camera reports are ignored under core's `.test-artifacts/remaining-fixes/`.
Prepared-data and Blender prerequisites are recorded in the existing ignored
`.test-artifacts/api-cleanup/full-validation/paths.json` manifest.
