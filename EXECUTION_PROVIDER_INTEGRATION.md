# Execution provider controls on sfn26

Global 3, approved 2026-10-31. Full merge of PR #931 at
`3f833d9fa7f7469a1258d3f3a9ebe42a3878ac14`, adapted to the current shared
inference service, settings layout and post-hoc graph [@freemocapExecutionProviderPr931].

- [x] **3.1. Review PR #931 against Core's current live, post-hoc and shared-session provider paths.**
- [x] **3.2. Integrate provider controls through the API, UI and tracker requests without replacing shared-session ownership.**
- [x] **3.3. Test provider selection, applied-provider reporting, unavailable-provider behavior and session cleanup.**
- [x] **3.4. Validate both reference recordings, publish the provider integration and pause with the PR comment.**

## Configuration and ownership

The live selector sets `skeleton_inference_node_config.execution_provider`.
Both centralized inference and per-camera workers consume it. Provider or model
changes rebuild the affected inference resources; filter-only updates retain
them. Camera capture is not reconnected. Replaced inference workers release their
message subscriptions under the relay lock, so frame fan-out does not accumulate
abandoned consumers. Per-camera startup failures now close
their shared-memory attachment as well as initialized trackers.

Post-hoc `executionProvider` selects the ONNX provider for both pipeline
implementations. The graph-only UI selector was removed. Older API requests
using `graphExecutionProvider` remain accepted; conflicting explicit choices
raise validation errors. Hidden ONNX settings do not select a MediaPipe device.

Automatic defaults are unchanged: graph RTMW processing chooses CUDA when
advertised, otherwise CPU; graph MediaPipe uses CPU. Live and older post-hoc
RTMW processing delegate Auto to Tracker. This integration does not tune these
policies or alter model precision.

Core continues using Tracker's registry requests, its own ONNX construction
lock and the existing `SharedSessionPool`. Sessions are not allocated by the
provider-discovery endpoint, nor are provider checks repeated per frame.

## Requested versus applied providers

`GET /freemocap/onnx/execution_providers` lists providers advertised by the
installed ONNX build. That is not proof their native libraries can load.
The UI refreshes this information after reconnects/server changes; a failed
query does not advertise every provider as supported.

After model construction, Core records each model's requested selection and
`get_providers()` result. Explicit selections fail if their requested provider
was silently dropped. Auto permits Tracker's fallback. Failed clients release
their leases without running image inference. Direct construction closes a
rejected session before raising.

`GET /freemocap/onnx/session_providers` exposes those startup records for active
shared live/post-hoc clients. An empty model list means initialization has not
completed; it is not an applied-provider claim. Per-camera process sessions
publish equivalent startup logs. Provider registration does not prove that
every model operation executes on that provider.

## Validation

Focused regression suite: 127 tests plus seven subtests passed. Five UI service
tests and the TypeScript no-emit check passed. Tests cover provider propagation,
fallback, schema/model preservation, resource cleanup, live changes and filter
continuity. Two additional startup-failure/API tests passed; the final provider,
inference and lifecycle rerun passed 50 tests plus two subtests. Changed Python
files passed targeted fatal-error lint; bibliography validation and its eight
tests passed. No generated files were staged.

All 20 reference replay cases passed (16 complete-recording combinations plus
four CPU-to-CUDA switch cases). After the final subscription cleanup change,
the four switch cases passed again, verifying unchanged camera workers,
unchanged subscriber counts, actual CPU/CUDA session providers, complete frame
sequences, and no surviving workers or shared memory. These are recorded-frame
replays, not hardware-camera/UI FPS measurements. Other provider names have
contract tests, not hardware validation on this Windows machine.

Both graph post-hoc runs completed calibration, tracking, reconstruction and
Parquet validation: test data has 222 frames per camera and 1,865,466 rows;
sample data has 1,108 frames per camera and 9,310,524 rows. Both have three
cameras. The selectable older pipeline also completed both recordings. Its
sample run initially hit the existing Windows output-path limit; rerunning
under a shorter temporary root succeeded without changing application behavior.

All six saved 2D camera-channel tensors matched Global 2 exactly: values,
presence masks, frame IDs, timestamps and landmark names. Nine tensor/timing
consumer tests passed on the new graph outputs. Independent fresh calibrations
mean this is not an assertion of identical 3D solutions. Reference frames can
still have unsolved skeleton segments; no claim of universal solved tracking is
made. Runs overlapped for correctness checks, so elapsed times are not speed
benchmarks. The numerical output profile was explicit; Blender exports and the
live GUI were not part of this acceptance.

Graph outputs: `%LOCALAPPDATA%/Temp/fc-sc34-20261031/`.
Older-pipeline outputs: `fc-sc34-current-20261031/` for test data and `c34c/` for
sample data under that same temporary parent. Original recordings were not
overwritten. PR #931 is the only bibliography entry included; the unrelated
90-line bibliography addition remains uncommitted.

Local logs, JUnit and UI bundles are ignored under
`.test-artifacts/sidecar-integration/stage33-*` and `stage34-*`.
No dependency installation or lockfile change is part of this integration.
