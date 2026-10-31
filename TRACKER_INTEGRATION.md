# Tracker registry integration into sfn26

Global 2, approved 2026-10-31. Preserve numerical values, authored landmark order,
confidence semantics, source timing, shared-session ownership and Core's direct
ONNX construction lock. Dependency installation is outside this approval.

- [x] **2.1. Replace Core's hard-coded session discovery with Tracker's registry requests, preserving shared-session ownership and ONNX construction locking.**
- [x] **2.2. Update Core's RTMW imports and schema access, with tests for model names, confidence values, landmark ordering and skeleton connections.**
- [x] **2.3. Validate the migrated Core factory through real-time replay and post-hoc processing of both reference recordings.**
- [x] **2.4. Publish the tested Core integration and prepare the execution-provider controls handoff.**

## Session discovery

Core's `tracker_session_requests` now adapts application settings to Tracker's
registry API. Session allocation remains in Core's existing locked factory or
`InferenceService`/`SharedSessionPool`; discovery does not allocate models.
Empty detector configurations remain errors. Nested RTMPose body/hand/face
detectors no longer need additional Core type checks, and duplicate models
produce one request. Existing bounding-box and confidence settings are unchanged.

Step 2.1 validation: 71 tests plus two subtests passed, covering independent
model/backend expectations, nested registry discovery, allocation-free requests,
serialized direct ONNX creation, rollback, inference state and cancellation.
Logs/JUnit are ignored under `.test-artifacts/sidecar-integration/stage21.*`.

## RTMW configuration and schema

Core factory, camera defaults and post-hoc configuration now import canonical
`RTMWWholebodyDetectorConfig`. Direct session construction uses the canonical
detector's model descriptors. `tracker_definitions.py` and `tracker_mappings.py`
use public RTMW schema methods instead of constructing paths to RTMPose YAML.
The saved `rtmpose` detector identifier and `rtmpose_wholebody` source name remain
unchanged. Existing sorted mapping-name and authored emitted-name contracts are
preserved; no coordinate/confidence conversion changed.

Tracker's allocation-free `keypoint_names()` accessor was tested and published
as `4118b5481458e2383719fc6535d559dc8f2a51b9` before Core adoption. Its eight
focused tests passed. The expanded Core suite passed 98 tests plus seven
subtests, including all RTMW variants, default/custom confidence, source names,
connections, provider/device propagation, dataflow consumers and schema imports
without native inference libraries. The first run exposed an incorrectly typed
test mock; the corrected mock returns an empty `OnnxSession`, without inference.
Logs/JUnit: `.test-artifacts/sidecar-integration/stage22.*`.

## Reference validation

All 16 real-time replay cases passed across the complete test and sample
recordings: centralized/per-camera inference, explicit/latest calibration, and
board-only/board-plus-human tracking. Checks cover complete ordered frames,
source timing, reconstruction, live filter updates without worker replacement,
worker shutdown, shared-memory release and unchanged input-file hashes. These
are lockstep recorded-frame tests, not live-camera or display-FPS measurements.
Reference frames can still contain unsolved hand segments and camera-geometry
warnings handled by the configured continue policy; passing does not mean every
segment is solved on every frame.

Both full graph post-hoc runs completed fresh calibration, tracking,
triangulation, alignment, filtering, scale fitting, reconstruction and validated
Parquet publication. Test data produced 222 frames per camera and 1,865,466 rows;
sample data produced 1,108 frames per camera and 9,310,524 rows. Both have three
cameras. Fresh calibration reprojection errors were 0.358428 and 0.389837 pixels,
respectively. These repeated calibration results are not an accuracy benchmark
against the previous run, which recalibrated independently.

The selectable older post-hoc implementation also completed test data. Nine
dense tensor, ownership, source timing and replay consumer tests passed against
the newly written results. The numerical processing profile was selected
explicitly; Blender export and GUI/hardware-camera acceptance were not run.

All six saved `OVERLAY_2D` channel arrays across both full recordings matched the
Global 1 outputs exactly: values, presence masks, frame IDs, timestamps and
landmark names. Their shapes are `[222, 225, 3]` and `[1108, 225, 3]` per camera,
including the configured human and board landmarks. These checks compare stored
2D outputs, not equality of 3D solves after fresh calibration.

Controlled inference comparisons loaded the prior Core factory from `ccfda109`
in memory without checking out or modifying Git state. They used the same
installed dependencies, input frames and detector configuration for old/new
factories. All 96 camera-frame observations matched exactly with automatic
provider selection, and another 96 matched with explicit CUDA through shared
session requests. Coordinates, confidence, landmark order and missingness agree;
sessions were released after tracker/lease closure.

An initial comparison to the older standalone Tracker baseline was not a valid
same-environment comparison: Tracker's environment has OpenCV 5.0.0, while Core
has 4.12.0. Both use ONNX Runtime 1.26.0 and NumPy 2.4.6. On the same first
reference frame, decoded pixels were identical but RTMW preprocessing tensors
differed by up to 0.017507076 in normalized input. The failed cross-environment
comparison is retained as diagnostic evidence, not counted as a pass. No
dependency or provider defaults were changed. Later acceleration benchmarks
must control preprocessing-library versions as well as model/provider settings.

Artifacts are ignored under `.test-artifacts/sidecar-integration/stage23-*`.
Fresh graph outputs and `ready.json` reports are under
`%LOCALAPPDATA%/Temp/fc-sc23-20261031/`; older-pipeline results are under
`%LOCALAPPDATA%/Temp/fc-sc23-current-20261031/`. Global 1 outputs under
`fc-sc15-20261031/` supplied the prior saved tensors and real-time replay inputs.
Original recordings were not overwritten. Correctness runs overlapped; their
elapsed times are not speedup or live-FPS measurements.

## Execution-provider controls handoff: Global 3

Global 2 is complete. Core implementation/tests were published as
[`38c67163`](https://github.com/freemocap/freemocap/commit/38c67163c7fb0b0f15647edd92ab1006fbb49c8c),
with Tracker's schema accessor in
[`4118b54`](https://github.com/freemocap/skellytracker/commit/4118b5481458e2383719fc6535d559dc8f2a51b9).
Both `origin/sfn26` revisions were verified after pushing. Core's pre-existing
100-line `references.bib` addition remains unstaged and unchanged. No generated
artifacts, dependency declarations or lockfiles were included. This documentation
checkpoint records completion after publication; Global 3 remains unstarted.

PR #931 has not been merged or applied in Global 2. Review it against these
current paths before integration:

- Centralized live inference already has
  `RealtimeSkeletonInferenceNodeConfig.execution_provider`. The skeleton node
  passes it into Core's registry-request adapter and then the shared inference
  service. Preserve that pool and its per-client state when adding controls.
- Per-camera live inference in `camera_node.py` calls
  `build_skeleton_onnx_session` without a provider argument. Its selection is
  automatic; controls must reach this path too.
- Graph post-hoc processing already exposes `graph_execution_provider` through
  `PosthocMocapPipelineConfig`, `application_pipeline.py`, the setup modal's
  `graphExecutionProvider` state and `services/recording/posthoc-processing.ts`.
  Its automatic selection chooses CUDA/CPU, while centralized live `None`
  delegates to Tracker's automatic policy. Do not assume these policies are
  already identical.
- Live settings travel through `api/http/realtime/realtime_router.py` (`/apply`),
  the UI realtime store and `RealtimePipelineConfigTree.tsx`. Reconcile API,
  stored settings, UI selection and actual applied session settings together.
- Report requested and actual providers distinctly, test unavailable-provider
  behavior, and preserve cleanup when settings change. Current logs can name
  requested TensorRT while actual sessions use CUDA after fallback. Do not infer
  runtime acceleration from the requested name or install new runtimes as part
  of the already approved migration.

### Proposed Global 3 checklist — awaiting approval

- [ ] **3.1. Review PR #931 against Core's current live, post-hoc and shared-session provider paths.**
- [ ] **3.2. Integrate provider controls through the API, UI and tracker requests without replacing shared-session ownership.**
- [ ] **3.3. Test provider selection, applied-provider reporting, unavailable-provider behavior and session cleanup.**
- [ ] **3.4. Validate both reference recordings, publish the provider integration and pause with the PR comment.**
