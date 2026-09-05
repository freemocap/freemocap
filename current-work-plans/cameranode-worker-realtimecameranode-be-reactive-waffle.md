# Posthoc pipeline revival on a shared computational core

> **2026-09-05 planning update:** Implementation ordering, recording schema and stage reuse are now
> specified in [Posthoc rebuild](02-pipeline/posthoc-rebuild.md) and
> [Recording data model](03-transport/recording-data-model-proposal.md). Use those plans where this
> exploration defers the schema, infers completion from channel presence, or equates a growing-window
> reconstruction pass with a completed global fit. This document retains the earlier design context.

## Context

The posthoc mocap path returns HTTP 500 before spawning a worker. The cause is narrower than it
looks: the posthoc *machinery* is healthy — `PosthocPipeline`, `VideoNode`, `PosthocAggregationNode`,
progress reporting end-to-end, annotated-video writing, and posthoc **calibration** all work today.
Exactly one leaf is missing: "turn triangulated 3D into a skeleton and write files", which lived in
`skellyforge.skellymodels.Human` / `Board` and was deleted upstream. Three freemocap modules still
import `skellyforge.{skellymodels,post_processing,data_models}` and are unimportable.

So this is a **re-point onto the realtime core**, not a rebuild — which is what the user wants
anyway: one implementation of every piece of math, realtime and posthoc differing *only* in temporal
policy.

**The shared core already exists — the extraction this plan used to call "one refactor away" has
landed.** `reconstruct_skeleton` is already a pure function of one frame given a caller-owned
`SkeletonReconstructionState` (see `reconstruction_state.py`); `TrackedSkeletonBundle` is genuinely
frozen, and the state holds the scale source and roll resolver beside it. Both the realtime aggregator
and — once re-pointed — the posthoc driver call the very same function, differing only in which scale
source and temporal policy they pass. The "streaming fitter with a big window IS the global fit"
equivalence is already pinned by `test_reconstruction_state.py`.

**Three whole-dataset algorithms already exist and posthoc simply never calls them:**

| Want | Already exists | Verified |
|---|---|---|
| Global scale fit over the whole take | `StreamingModelScaleFitter.current_fit()` *literally calls* `fit_model_scale(scale_samples=self._windows, …)`. With `window_frames=T` the ring never wraps. | `model_scale_fitting.py:450-456` |
| Central-difference CoM velocity | `center_of_mass_velocity(positions=(N,3), timestamps=(N,))` | `derived_kinematics.py:18` — realtime doesn't even use it |
| Whole-recording triangulation in one call | `Triangulator.triangulate` already accepts `dict[cam, (T,P,2)]` and vectorizes | `triangulator.py:166`, batch path `:225` |

Posthoc's "better math" is therefore mostly *free*.

### Settled decisions

1. **Parity = same code, not same numbers.** Posthoc defaults to batch-optimal algorithms, plus a
   test that drives the posthoc driver with the *streaming* policy set and asserts bitwise-identical
   output to realtime. Enforceable version of the archived "E5 parity proof".
2. **Stage artifacts live in one channel-distinguished store** — "what's in the store" IS "what
   stages are done".
3. **Blender / BVH / glTF / the export suite are OUT OF SCOPE**, to be rebuilt around the new data
   model after this and the skellyforge refactors land.
4. **The tidy-long parquet schema is NOT decided here** — see below.

### Deferred: the on-disk schema gets its own design session

The schema is genuinely undecided. `03-transport/serialization-tidy.md` is a 17-line stub ("Not built
yet"); the only real column list is in `archive/` (history, not guidance) and is human-shaped. The two
sources even disagree on row grain: the stub says `(frame, subject, segment/keypoint, channel)`, the
archive says `(frame, trajectory, component)` melted.

`clients/bs/python_code/ferret_gaze/analyzable_output_csvs.md` is the shape hint. What it gets **right**
— and what any successor must keep:

- Melted grain `(frame, timestamp_s, trajectory, component, value, units)`. `component` as a *column*
  is the only form that holds 3-vectors, `wxyz` quaternions, `roll/pitch/yaw`, `major/minor` and
  scalars without a schema change.
- `units` first-class per row; `timestamp_s` first-class, zeroed to recording start.

What it gets **wrong**, and must not survive:

- `keypoint__nose` — a dotted composite key inside `trajectory`. This is the banned pattern verbatim
  ("names are opaque identifiers; a naming scheme that has to be regex-able is a design that lost its
  structure upstream"). The archive already flagged it as "bs/'s one wart".
- **Identity lives in the filename** (`skull_`, `left_eye_`, `toy_`) — the same sin one level up, and
  it cannot express "a human and a board, two instances, two detectors" that the wire already handles
  with `model_id` / `instance_id` / `tracker_id` / `camera_id`.
- **Reference frame stated in prose** ("coordinates are in the eye camera frame") when it is a
  per-row fact.
- Inconsistencies: `timestamp_s` vs `timestamp`; `angular_velocity_local` with components `x,y,z` in
  one table and `roll,pitch,yaw` in another; the basis-vectors file abandoning the format for wide
  `world_x/world_y/world_z`.

One shape fact the session must resolve: **`SEGMENT_LENGTHS` is per-take posthoc** (that is the whole
point of the global fit) where realtime re-emits it per frame.

Phase 4 therefore lands against an explicitly-provisional encoding so the resume logic is built and
tested *before* the schema exists; the session then swaps the encoder behind one seam.

---

## The design

### 1. `SkeletonReconstructionState` — already extracted

`freemocap/core/skeletons/reconstruction_state.py` already exists and holds everything reconstructing
one skeleton remembers between frames, beside the bundle:

```python
@runtime_checkable
class ModelScaleSource(Protocol):
    def observe_pose(self, *, pose: SkeletonPose) -> None: ...
    @property
    def has_model_scale(self) -> bool: ...
    def current_fit(self) -> ModelScaleFit: ...

@dataclass(slots=True)
class SkeletonReconstructionState:
    model_id: str
    scale_source: ModelScaleSource
    roll_resolver: ContinuousRollResolver | None
    previous_center_of_mass: tuple[np.ndarray, float] | None = None
    def reset(self) -> None: ...
```

`StreamingModelScaleFitter` already satisfies `ModelScaleSource` (no adapter) and `FrozenModelScale`
(one fit offered to every frame) already exists. `reconstruct_skeleton(*, bundle, state,
filtered_keypoints, compute_center_of_mass)` already takes the state, and `TrackedSkeletonBundle` is
already frozen. Nothing in this section is new work — it is retained only as the reference for the
split below.

**Remaining new work — split for the two-pass cost:** `solve_skeleton_pose(...) -> SkeletonPose | None`
and `describe_skeleton(...) -> SkeletonReconstruction`, with `reconstruct_skeleton` as the composition
realtime keeps calling. Pass B needs only the first half. A split, not a duplication.

### 2. The posthoc driver

`freemocap/core/reconstruction/` (NEW) holds temporal policy and drivers — **adapters only, no
formulas**. The batch *algorithms* (zero-phase Butterworth, gap interpolation) go into skellyforge
beside `core/biomechanics/derived_kinematics.py`, where the whole-dataset counterparts already live.

| Pass | Calls |
|---|---|
| P0–P1 | `ObservationBuffer.to_keypoints_array()` → **one** `Triangulator.triangulate(data2d={cam: (T,P,2)})`. **Not** via `CalibrationStateTracker.try_angulate` (per-frame streaming wrapper) |
| P2–P3 | vectorized reprojection-error mask → NaN; `_to_blender` over `(T,P,3)` (express the per-point form as `to_blender_batch(p[None])[0]` so there is one implementation) |
| A | gate → interpolate → smooth over the whole series (note the ordering fix, R1) |
| B | `for t: solve_skeleton_pose(...)` with `state.scale_source = StreamingModelScaleFitter(window_frames=T)`; keep only scale samples |
| — | global fit = `state.scale_source.current_fit()`, which **is** `fit_model_scale` |
| C | `state.scale_source = FrozenModelScale(fit)`; `roll_resolver.reset()`; full `reconstruct_skeleton` |
| D | stack CoM → `center_of_mass_velocity(...)` → the *same* `extrapolated_center_of_mass` realtime calls |

### 3. Temporal policy: no `if posthoc:` anywhere

The pipeline *manager* picks a policy set; the driver sees only Protocols; the math sees neither.
One shared data shape — `KeypointSeries{names, timestamps (T,), positions (T,P,3), predicted (T,P)}`,
where **realtime passes `T == 1`**:

```python
@dataclass(frozen=True, slots=True)
class TemporalPolicySet:
    keypoint_series: KeypointSeriesPolicy
    point_gate: PointGatePolicy
    center_of_mass_derivative: CenterOfMassDerivativePolicy
    scale_source_for: Callable[[TrackedSkeletonBundle], ModelScaleSource]

    @classmethod
    def streaming(cls, *, config) -> TemporalPolicySet: ...
    @classmethod
    def batch(cls, *, config, frame_count: int) -> TemporalPolicySet: ...
```

Streaming implementations are **adapters holding the existing `RealtimeKeypointFilter` /
`RealtimePointGate`** — not a line of One Euro math is touched. Roll needs no new protocol:
`ContinuousRollResolver` *is* the streaming policy; the batch policy runs the same `resolve_pose`
forward and backward and selects per (segment, frame) from the nearer **anchored** frame (the anchored
tier at `roll_resolution.py:190-210` is history-free whenever the parent hydrated). v1: seed from the
best-hydrated frame instead of "frame 0, whatever it was".

### 4. Config unification — one `tracker_config_for_fps`

`CameraNodeConfig` and `PosthocMocapPipelineConfig` duplicate ~85% of detector config *including the
whole `TrackerConfig`-building `@model_validator`*, with divergent defaults. The structural cause:
`redetect_interval` is a function of fps, so a config that must be complete at construction invented
`_ASSUMED_CAMERA_FPS = 30.0`.

One `SkeletonDetectionConfig` with `tracker_config_for_fps(*, frames_per_second)` kills **four** copies
of that block (both validators, `tracker_factory.build_skeleton_tracker`'s own, and
`CameraNodeConfig.confidence_threshold` — a fourth copy of the rtmpose number under another name).

- **rtmpose confidence → 0.0025** (realtime's). It is a keypoint floor whose job is to keep marginal
  keypoints available so the *downstream geometric* gates judge them, not the detector photometrically.
  Posthoc now inherits those same gates.
- **mediapipe complexity → named at the construction site** (realtime `LITE`, posthoc `HEAVY`), visible
  rather than hidden in two field defaults nobody compares.
- **fps → real fps, always.** Realtime uses `CameraConfig.framerate` (the *requested* rate, a config
  value known at construction — never a measured rate, which would be a runtime fallback).

### 5. Detection batching — the axis is CAMERAS, never time

`Tracker.process_batch` takes one frame number and N cameras; `StageState` is per batch element.
Batching over time would corrupt the bbox crop chain. That is exactly `process_video_list`.

Don't call it directly (it writes `.npy`, picks filenames, has no progress/cache/annotation hook).
Factor its loop body into skellytracker as `iterate_synchronized_video_observations(...)` and rewrite
`process_video_list` on top. freemocap gains **one `SynchronizedVideoNode` replacing N `VideoNode`
processes**, with `batch_size=len(camera_ids)` instead of today's `batch_size=1` — currently 1/N GPU
efficiency. `auto_detect_provider()` stays the default (resolved once at session creation);
`require_provider()` when explicitly named — its refusal to silently degrade is the house rule.

### 6. Stages and resumability

```python
class MocapPipelineStage(StrEnum):
    DETECT_KEYPOINTS_2D | TRIANGULATE_3D | SMOOTH_AND_GATE_3D | RECONSTRUCT_SKELETONS | DERIVE_KINEMATICS
```

Each artifact carries a **stage manifest**: `{stage, config_fingerprint, upstream_fingerprint,
frame_range, camera_ids, model_ids, produced_at}`.

- `config_fingerprint` hashes **only the fields that stage's output depends on**, declared per stage —
  hashing the whole config would invalidate 2D detections when an export checkbox flips.
- `upstream_fingerprint` chains: change the calibration and everything downstream self-invalidates.
  No separate dependency graph to keep in sync.
- Validation is **structural**, generalizing `video_node.py:497`'s board-fingerprint check.
- **Partial credit for `DETECT_KEYPOINTS_2D` only** (the charuco cache's real virtue); the other four
  are whole-dataset and all-or-nothing.
- **Compute the whole plan up front, log it, then run.** Deciding per-frame mid-run is a runtime fallback.

`ProcessMocapRecordingRequest` gains `startAtStage` / `forceRecomputeFrom`, both defaulting to None =
"resume from the earliest incomplete stage". If 2D is satisfied, **no source node is built at all**.

`PosthocAggregationNode` currently hard-requires `T × N` live pubsub messages. Extract the collection
step behind `FrameObservationSource` (Protocol) with two implementations — `PubSubFrameObservationSource`
(today's loop *verbatim*, completeness check included) and `StoredKeypointSource`. `_run` never knows
which it got. `compute_recording_status` reads the *same* manifests, so UI status and the resume
decision cannot disagree.

New phase strings must land **with** the backend change in `BACKEND_PHASE_MAP`
(`ServerContextProvider.tsx:444`), and its `?? PipelinePhase.PROCESSING_VIDEOS` must become a
`console.error` on unknown — `PIPELINE_TYPE_MAP` ten lines above already does exactly that.

### 7. The parity test

Parity is a **policy set, not a mode flag** — no `if streaming_equivalent:` in production code. The
test constructs the posthoc driver with `TemporalPolicySet.streaming(...)` exactly as the manager
would, feeds it the same per-frame triangulated keypoints captured from a real realtime run
(`MockCameraGroup` + real `RealtimeAggregatorNode` over real IPC), and asserts **bitwise**
(`assert_array_equal`, not `allclose`) equality of landmarks, world/local rotations, segment lengths,
`fitted_scale_mm`, joint angles, CoM. Same code, same inputs, same order ⇒ same floats; a tolerance
would hide the exact divergence this exists to catch.

**Prerequisite:** `frame_time = time.perf_counter()` makes realtime non-reproducible against itself.
The aggregator must take the frame timestamp from frame metadata (skellycam already carries it).
Independently correct — today a dropped frame makes One Euro's `dt` reflect scheduler jitter.

### 8. The four empty ABCs → delete

`PipelineABC`, `PipelineManagerABC`, `AggregatorNode`, `SourceNode` are `pass` with TODOs.
`RealtimePipeline` isn't even declared a `PipelineABC` subclass, so the abstraction is already
empirically optional. An empty ABC is worse than none — it invites people to *satisfy* it rather than
notice they have nothing in common, and it makes the two aggregators look substitutable in a type
hint. `PipelineIPC` already carries the real shared thing and is **composed** — the same reasoning
`message_model.py` gives for composing `MessageEnvelope`. Keep `BaseNode` + `PipelineIPC`. Revisit the
two node ABCs in Phase 5, when this design makes the aggregators actually converge; a base class earns
its place by holding code.

---

## Phases

**Phase 0 — logging fixture (prerequisite).** `tests/pipelines/conftest.py:277` already calls
`create_websocket_log_queue()`, but only inside one fixture. Anything constructing a `PipelineIPC`
outside `tests/pipelines/` dies with `ValueError: Websocket log queue not created yet`. Move it to
`freemocap/tests/conftest.py` as an **autouse session fixture** (~5 lines) so no new test can miss it.
Hard prerequisite for the parity test, which must live outside `tests/pipelines/`.

**Phase 1 — Unbreak posthoc. No schema.** `SkeletonReconstructionState` is already extracted and
tested — skip that step. Rewrite the dead `skeleton_from_mediapipe_observations.py` as the posthoc
driver *on top of the existing `reconstruct_skeleton`*; **keep writing the existing `.npy` filenames**
`recording_status.BLENDER_INPUT_FILES_BY_DETECTOR` already expects, so `POST /mocap/recording/process`
goes 500 → 200 with nothing about the on-disk schema decided. Delete
`charuco_model_from_observations.py` and `triangulate_trajectory_array.py` (a third broken importer,
whose fuzzy substring camera matching also violates structure-not-strings); posthoc calibration's board
model becomes the same `reconstruct_skeleton` path, removing the `try/except ImportError`.

**Phase 2 — Temporal policies + config unification. No schema.** `TemporalPolicySet`, `KeypointSeries`,
streaming adapters; `tracker_config_for_fps`; frame timestamps from metadata. **Gate: the parity test
lands here and passes.**

**Phase 3 — Batched detection. No schema.** `iterate_synchronized_video_observations` in skellytracker;
`SynchronizedVideoNode`; bounded per-frame topic.

**Phase 4 — Stages + resumability.** Against a **provisional** encoding (`.npz` + JSON manifest),
explicitly marked placeholder, so plan/resume logic is exercised before the schema session.

**Phase 5 — Convergence cleanup.** Delete the ABCs; fold the aggregators where they now coincide.

**Then, separately:** the schema design session, then Blender/BVH/glTF/export suite.

---

## Risks

**R1 — the gate/filter ordering bug (verified, must fix before the parity test).**
`realtime_aggregator_node.py:813-824` gates the **raw** keypoints, then overwrites
`filtered_keypoints[name]` with the gate's hold-last-accepted value whenever it isn't NaN — so One Euro
smoothing is **discarded** on every frame the gate produces a value. Latent only because
`filter_enabled` defaults `False`. Batch order must be gate → interpolate → smooth. **Reconcile
realtime to gate-first in Phase 2 and re-baseline**, or the parity test enshrines the bug.

**R2 — reset semantics.** Three sites call `bundle.reset()`; two also clear
`previous_center_of_mass_by_model` but the **detector-change path does not** — a pre-existing leak the
extraction surfaces. Mitigation: make bundle+state construction a single call returning a paired
record, so rebuilding one without the other is inexpressible.

**R3 — deleting `_ASSUMED_CAMERA_FPS` changes realtime behaviour.** At 60 fps, `redetect_interval` goes
150 → 300 frames: YOLOX currently redetects twice as often in wall-clock as intended and will start
redetecting correctly every 5 s. Land with a log line naming resolved fps and interval; hand-check a
60 fps rig.

**R4 — memory.** `VideoNodeOutputTopic` has `queue_maxsize=0` and the aggregator waits for 100% before
processing, so peak ≈ the whole recording of `Observation`s in the queue *and again* in
`video_outputs_by_frame`. Phase 3 cuts message count by N and makes bounding possible, but the
aggregator must **also** stop holding the whole take (stream to the 2D artifact, read back for
triangulation) or the bound just relocates the memory.

**R5 — two-pass cost.** 2 × T × 61 `RigidPointSet.fit_pose` calls. The
`solve_skeleton_pose`/`describe_skeleton` split halves the redundant part; batched Kabsch/SVD is the
escape hatch. Measure first.

**R6 — roll continuity across the pass boundary.** Pass B's carry must not reach pass C. Explicit
`reset()` plus a test that pass C is invariant to whether pass B ran.

**R7 — charuco cache inside a synchronized batch.** Cache coverage may differ per camera, leaving the
batch one element short. Keep substitution per-camera *inside* the loop;
`test_calibration_cache_alignment.py` guards it.

---

## Doc / code drift to reconcile

- `02-pipeline/posthoc-rebuild.md` says **"Deferred by decision"** while `IMPLEMENTATION_PLAN.md` lists
  posthoc under `[IN]` as "the current initiative" and the README repeats "deferred". Three places, two
  answers.
- Same doc, item 2: "solve batch-wise with `hydrate_skeleton(require_all=True)`" is **wrong** — a batch
  solve still has occluded frames; posthoc's advantage comes from interpolating *before* hydration, not
  from demanding completeness. Both should be `require_all=False`. Its "damped online vs undamped batch"
  describes a solver knob that does not exist.
- `message-contract.md` channel list **omits `JOINT_ANGLES`**, which exists at `message_model.py:66`,
  is populated by `reconstruct_skeleton`, and is consumed by the frontend.
- `playback_router.py:722` `_find_recording_parquet`'s `rglob("*.parquet") → matches[0]` is a banned
  runtime fallback and nondeterministic across filesystems. *Touches the parquet path — flag for the
  schema session.*
- `recording_status.missing_blender_input_files(path, detector)` overwrites `detector` immediately; the
  parameter is dead.

---

## Verification

**Phase 1** — `pytest freemocap/tests/pipelines/test_posthoc_mocap_pipeline.py` green is the gate (its
fixture currently dies at `create_mocap_pipeline`). The two extraction properties are *already* pinned by
`test_reconstruction_state.py` (same bundle + two fresh states ⇒ identical; and
`StreamingModelScaleFitter(window_frames=T).current_fit() == fit_model_scale(scale_samples=collected)`),
so Phase 1 only needs to re-point the dead leaf, not re-prove them.

**Phase 2** — the parity test is the gate. `test_realtime_keypoint_filter.py` rewritten against
`KeypointSeries` with `T == 1`, reproducing current per-frame expectations exactly.
`tracker_config_for_fps(frames_per_second=60) ⇒ redetect_interval == 300`; at 30 ⇒ 150.

**Phase 3** — **the batch-axis guard**: `process_image` over one video vs `process_batch` over that
video plus a second; assert the first camera's `Observation` keypoints are *identical*. Plus: the
observation topic never exceeds maxsize over a full run; `@pytest.mark.slow` 3-camera batched detection
< 2× single-camera wall clock.

**Phase 4** — resume (run twice; assert no detection phase emitted and output bitwise identical);
invalidation (change `rtmpose_confidence_threshold`; assert detection *and every downstream stage*
re-ran); partial credit (delete half the 2D frames; assert only those re-detected); manifest corruption
(assert recompute, logged reason, decision taken *before* any frame processed).

**Cross-cutting** — extend `tests/http/test_mocap_router_import.py` so `POST /mocap/recording/process`
returns 200 (it currently only guards the import that *is* the bug). Add a drift test parsing
`MocapStage` and `BACKEND_PHASE_MAP` and asserting set equality — the `??` fallback is precisely what
lets that drift silently.

## Critical files

- `freemocap/core/skeletons/reconstruct_skeleton.py`, `reconstruction_state.py`, `tracked_skeleton_bundle.py`
- `freemocap/core/pipeline/realtime/realtime_aggregator_node.py`, `camera_node_config.py`
- `freemocap/core/tasks/mocap/mocap_helpers/skeleton_from_mediapipe_observations.py`
- `freemocap/core/pipeline/posthoc/video_node.py`, `posthoc_aggregation_node.py`
- `skellytracker/core/io/process_video.py`
- `skellyforge/core/skeleton/pose/model_scale_fitting.py`, `roll_resolution.py`
