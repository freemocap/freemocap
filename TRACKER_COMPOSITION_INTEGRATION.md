# RTMW and MediaPipe hand integration

The opt-in `rtmw_mediapipe_hands` preset uses RTMW body, feet and face keypoints
with cropped MediaPipe hands. The default remains `rtmpose`. Selecting this preset
does not enable MediaPipe face tracking or a DLC model.

## Ownership and representation

SkellyTracker owns `human_tracker_config`, `tracker_profile`, crop definitions,
keypoint schemas/connections, prepared assembly indices and mapping selection.
Core's `tracker_config_for_settings` translates application field names. Core
coordinates camera sessions, reconstruction, recording, API and UI settings.
Core does not reconstruct the preset's detector tree or rename MediaPipe fingers
as RTMW fingers. Tracker `Observation` is a tracking container; it is distinct from
the anatomical observations produced by applying mappings.

Returned keypoint values remain dense arrays. Assembly reuses prepared index and
schema metadata, but each returned observation owns its numerical storage so later
frames cannot overwrite retained observations. Missing MediaPipe hands are explicit
NaN coordinates with zero visibility, without silently falling back to RTMW hands.

Tracker's `TRACKER_COMPOSITION.md` defines the schema and crop contract. Adding a
Charuco stage through `with_charuco_tracker` preserves the preset identity and
assembly declaration in both post-hoc implementations.

## Validation

Completed on 2026-10-31 using the existing environments and local source checkouts:

- Core focused contracts: 138 passed; TypeScript type checking passed.
- Tracker preset/consumer contracts: 53 passed, including fresh-process registration
  without Core, SkellyCam or SkellyForge imports.
- Tracker custom ONNX/sidecar contracts: 23 passed, including real CPU execution
  of synthetic local ONNX artifacts at batch sizes one and three.
- Both complete reference recordings passed centralized and per-camera live
  replay, including reconstruction, filter updates, shutdown and cleanup.
- Both complete reference recordings passed graph and current post-hoc pipelines
  with the combined preset, fresh calibration and saved numerical validation.

Reference coverage is 222 synchronized frames for test data and 1,108 for sample
data, with three cameras each. Replay is not a camera/UI frame-rate measurement.
The numerical output profile does not certify Blender export. No user camera
connections or application servers were started for this validation.

Ignored local evidence is under `.test-artifacts/combined-final-contracts.xml`,
`combined-realtime.xml`, `combined-posthoc-graph.log` and
`combined-posthoc-current.log`. Post-hoc ready records are under the external
temporary roots `fc-g4g` and `fc-g4c`, separately from accepted recording outputs.

## Reproduce the preset comparison

Run each recording sequentially with no competing inference jobs:

```powershell
.venv/Scripts/python.exe -B -m freemocap.tools.datasets.hand_tracker_comparison --recording RECORDING_PATH --output .test-artifacts/NEW_COMPARISON --execution-provider cuda --repeats 2
```

The tool refuses an existing output directory. It uses recorded timestamps,
verifies the requested provider, reverses preset order on alternate repeats,
checks source video hashes and compares the retained RTMW keypoints exactly.
It saves dense numerical evidence in NPZ files and timing/availability summaries
in `report.json`. Tracking-call time includes detector processing and output
assembly, but excludes video decoding, result copying, reconstruction and UI work.
Hand availability means finite image-plane coordinates with positive visibility;
it is not ground-truth accuracy or calibrated confidence.

Measured with an NVIDIA GeForce RTX 3090, driver 610.60, CUDA-selected ONNX
sessions and CPU MediaPipe hands. Model: `rtmw-x-l_256x192`. Each row combines two
full-recording runs with reversed order; each tracking call processes three cameras.

| Recording | Preset | Mean tracking ms | 95th percentile ms | Available hand keypoints |
| --- | --- | ---: | ---: | ---: |
| Test (222 frames) | RTMW | 14.19 | 17.24 | 95.45% |
| Test (222 frames) | RTMW + MediaPipe hands | 55.37 | 87.93 | 21.70% |
| Sample (1,108 frames) | RTMW | 12.65 | 13.48 | 95.74% |
| Sample (1,108 frames) | RTMW + MediaPipe hands | 47.87 | 59.19 | 26.50% |

Test-data combined run means were 60.02 and 50.72 ms; sample means were 47.47 and
48.28 ms. First-use costs are included. This is a descriptive two-repeat comparison,
not a confidence interval or live UI measurement. Both recordings exceed the
33.3 ms tracking-only budget for 30 Hz with the combined preset. Crops and MediaPipe
thresholds are initial settings, not empirically optimized defaults.

The 91 retained RTMW body/feet/face keypoints and their visibility values matched
exactly in every repeat, including missing values. Source video hashes remained
unchanged. Availability also repeated exactly. The additional hand computation
and lower availability justify keeping this option experimental until visual
assessment and further tuning. Lower availability alone does not prove worse
accuracy; higher availability does not prove correct hand positions.

Reports and dense evidence are in ignored directories
`.test-artifacts/hand-preset-test-20261031/` and
`.test-artifacts/hand-preset-sample-20261031/`. No default was changed.

## Live visual comparison

### Hybrid acceptance corrections — 2026-11-01

The backend/reference validations above did not establish completion in the live
GUI. The user found that the actual Skeleton Setup popup still offered only two
detectors. The earlier guidance pointed to the pipeline-tree selector without
tracing `SettingsOverlay` to `RTPSkeletonSetup`. That was a missed application
entry point, not evidence of a stale frontend or a different branch.

Registered correction scope; the first two direct fixes are validated below.
The remaining items are open follow-up work, not completed GPU implementation
or a claim that hand quality is already acceptable.

- [x] **1. Fix the Skeleton Setup popup** to expose RTMW + MediaPipe hands and its applicable settings.
- [x] **2. Correct MediaPipe device reporting** so task configuration and logs agree about CPU execution.
- [x] **3. Preserve and display hand crop rectangles** without duplicating assembled keypoints.
- [ ] **4. Investigate missing and blinking hands** using recorded inputs and your live comparison.
- [ ] **5. Implement and measure GPU hand inference** after establishing which hand behavior we want to preserve.

1. `realtimepipeline-mediapipedetector-settings.tsx` now uses the same
   `DETECTOR_OPTIONS` as the pipeline tree and post-hoc setup. Hybrid selection
   exposes RTMW model/provider controls and MediaPipe hand confidence controls;
   MediaPipe body complexity remains exclusive to the full MediaPipe preset.
   TypeScript checking passed. A browser regression exercises the actual popup
   and real Redux store, including detector changes and conditional settings.
   Every browser request is intercepted; the user's server/cameras are untouched.
2. Tracker removes the misleading pose-model GPU probe and explicitly requests
   CPU for hand, body and face tasks. The default and `disable_gpu=True` select
   CPU; `disable_gpu=False` now rejects the unsupported native GPU request.
   Twenty-one device/session tests passed, including native hand-output equality
   against the previous implicit CPU default on three frames per camera from
   both reference recordings (18 camera frames total, not full-recording replay).
   One shared-session test mock needed its missing `keypoint_assembly=None` field.
3. Tracker's `PreparedKeypointAssembly.apply` copies hand keypoint arrays into
   the parent output and then removes the consumed child stages. Their crop
   rectangles are lost, although the assembled hand coordinates survive. Core's
   `channel_helpers.camera_bounding_boxes` also only reads declared top-level
   stages and excludes detectors without an external object detector. Fix both
   boundaries, preserve camera/image coordinate meaning and crop identity, and
   test the overlay end to end. Do not restore duplicate keypoints into mapping
   or triangulation inputs merely to preserve crop information.
4. Compare crop placement, detection/presence rejection, handedness and temporal
   reacquisition on identical inputs. Measure missing intervals as well as hand
   coordinate changes; user visual assessment remains required. Pure MediaPipe
   and the hybrid are distinct presets and must be identified in every report.
5. Tracker owns any ONNX hand adapter and model equivalence checks. Reuse sidecar
   loading/shared sessions and dense assembly; validate crop transforms, output
   decoding and actual supported batching. Compare retained quality and measured
   timing against the current CPU hand task before claiming a GPU improvement.

The first two corrections do not modify crop assembly, confidence thresholds,
filtering, model weights or the user's running server. Source changes require
the running frontend/backend to load the updated code; no restart was performed.

### Hybrid WebSocket crash correction — 2026-11-01

The subsequent live run exposed another omitted integration boundary:
`channel_helpers._OBSERVATION_BY_DETECTOR` did not register
`rtmw_mediapipe_hands`. `OverlayProducer.fill` raised `KeyError` during frame
composition, and the fatal WebSocket handler shut down the application. Earlier
tracking/reference tests and the popup test did not exercise this publication
path; their success was insufficient evidence of live application readiness.

Core now registers the hybrid's existing `skeleton_observation/body` output and
recognizes its RTMW person detector for BOXES_2D publication. This is transport
coordination, not a duplicate Tracker recipe. No inference, numerical assembly,
filter defaults or fatal-error handling changed. Child hand-crop publication
remains open in correction 3 above; the person-box repair does not complete it.

`test_detector_streaming.py` reproduced the exact logged KeyError before the fix.
It enumerates every human detector declared by `CameraNodeConfig` and exercises
real frame composition plus CBOR encoding with one, three and four cameras.
It verifies keypoint names, coordinates, missing rows and person-box payloads.
All 29 tests passed across this regression, existing box channels, full-loop
reconstruction and Charuco integration.

Saved hybrid detector arrays from both complete reference recordings also passed
through the actual composer and encoder with exact expected float32 overlay values:
222 frames/666 camera overlays for test data and 1,108 frames/3,324 overlays for
sample data. This is saved-output replay, not new model inference or a live UI
frame-rate measurement. The ignored reproduction script and report are
`.test-artifacts/replay_hybrid_streaming.py` and
`.test-artifacts/hybrid-streaming-replay-report.json`. No cameras or server were
started, no dependencies changed, and no Git state was mutated.

### Matched historical comparison — 2026-11-01

The earlier table compares configurations in the new code, not historical
performance. A separate matched comparison now runs Tracker `8354a67` with the
exact RTMW recipe from Core `2cbb1161`, versus Tracker `01107fa` with its owned
presets (consumed by Core `58709a50`). Both source revisions run through normal
standalone imports using the same existing Python environment, without installing
dependencies, changing checkouts, or changing Git state.

Each case ran both full recordings three times, with case order rotated across
repeats and fresh processes/sessions. Video bytes, timestamps, model bytes, CUDA
provider, RTMW stage configuration and dependency versions were verified equal.
MediaPipe hands use CPU. Times below are milliseconds per three-camera tracking
call, including preprocessing, inference and assembly; initialization, decoding,
output copies, reconstruction and UI are excluded. First tracking calls are included.

| Recording | RTMW before mean / p95 | RTMW after mean / p95 | Mean change |
| --- | ---: | ---: | ---: |
| Test | 13.77 / 16.87 ms | 13.60 / 15.54 ms | -1.23% |
| Sample | 13.09 / 15.45 ms | 13.50 / 18.41 ms | +3.15% |

| Recording | Current RTMW mean | RTMW + MediaPipe hands mean / p95 | Added mean cost | Time multiplier | Available hand keypoints: RTMW → combined |
| --- | ---: | ---: | ---: | ---: | ---: |
| Test | 13.60 ms | 48.06 / 62.42 ms | +34.45 ms | 3.53× | 95.45% → 21.70% |
| Sample | 13.50 ms | 46.83 / 61.90 ms | +33.33 ms | 3.47× | 95.74% → 26.50% |

All 133 RTMW keypoints and visibility values matched exactly before/after; all 91
retained non-hand keypoints also matched the combined preset, including missing
values. No overall RTMW speedup is established: test mean decreased slightly,
while sample mean and its latency tail increased. Three repeats do not establish
whether the small RTMW mean differences are code effects or run variability.
The added hand computation has a large, consistent cost. Availability is not
ground-truth accuracy, and no visual-quality advantage has been established here.

Reproduction scripts, frozen source snapshots, per-run dense tensors, hashes,
settings and results are in ignored `.test-artifacts/matched-hands-20261101/`.
`summary.md` includes per-repeat means; `verified_comparison.json` contains the
comparison checks. These are tracking-computation benchmarks, not whole-application
or live-camera frame-rate measurements.

### User-controlled comparison

On the next application launch, stop the active tracking pipeline and choose
**RTMW + MediaPipe hands** in the detector settings before starting it again.
Compare against **RTMPose** using the same camera, calibration and reconstruction
settings. The new preset adds MediaPipe hand inference after RTMW whole-body
inference. Its extra processing cost and missing-hand behavior must be acceptable
before considering any default change. The user judges visual quality; the
recording benchmarks do not establish that judgment.

## Custom-model boundary

The original sidecar/session integration was limited to supported local ONNX
artifacts. The DLC integration below now adds a bounded importer and generic
coordinate-keypoint detector; it does not imply arbitrary architecture support.
Session warm-up currently assumes float32, three-channel NCHW input. Tracker's
contract tests explicitly exercise these unsupported cases. Model-specific
preprocessing, output metadata, decoding and keypoint schemas belong in Tracker;
Core must not add them to work around missing Tracker support.


### Hand crop publication completed — 2026-11-01

Correction 3 is implemented and tested. Tracker fixes the image-coordinate error,
retains executed hand crop rectangles after dense keypoint assembly, and exposes
crop stage identities through TrackerProfile. Core publishes those rectangles as
additional rows in the existing BOXES_2D channel: body, body/right_hand and
body/left_hand for the hybrid. Pure MediaPipe publishes only the two hand rows.
The existing renderer already handles these named rows and labels them, including
when no hand keypoints are detected. There is no new channel or hand-specific
renderer. Missing crops stay declared NaN rows; no duplicate hand keypoints enter
mapping or triangulation. Box payload assembly now uses a dense ChannelValues array.

Twenty streaming/factory tests and 22 observation/recording compatibility tests
passed. Two renderer tests passed, explicitly checking a named hand rectangle
without hand keypoints. Four recording tests required an unsandboxed rerun because
the sandbox blocked their temporary-directory cleanup; all four then passed.
Tracker's 38 focused tests and four real-model reference tests also passed, covering
both recordings, both inference paths and 144 camera observations. Live visual
acceptance and further hand-quality investigation remain correction 4; ONNX hand
inference remains correction 5. The application was not restarted by these tests.

## DLC application integration: model-only calibrated keypoints

Tracker owns DLC model inspection, single-subject ResNet50 GroupNorm checkpoint
conversion, preprocessing, decoding and named keypoint recipes. Core connects the
existing conversion jobs, CPU/CUDA FP32 inference, calibrated triangulation,
recording and self-describing stream. Training and synthetic data generation are
separate workflows; an already validated checkpoint can be used immediately.

In the live camera view, open **Skeleton Setup**, choose **DLC**, then click
**Choose DLC project** and select the project's `config.yaml`. Tracker selects the
latest saved epoch from its matching training run and infers the companion
configuration and input size. Preparation starts automatically: reuse a validated
conversion when available, otherwise convert on CPU and validate the result.
The UI shows the checkpoint, elapsed time and estimates from measured conversions.
An optional checkpoint picker overrides the latest-epoch default. Ambiguous
training runs or missing dimensions request only the unresolved information.

**Model ready and selected** means the resulting model was successfully applied
to the running pipeline or saved for the next run. Conversion completion alone
does not establish selection success. A failed application preserves the previous
selection and offers **Retry selection** without converting again. After success,
optionally choose object geometry, click **Done**, connect the cameras, and click
the lightning bolt to start tracking. A running pipeline applies selection live.
The separate **Load a different converted model (optional)** section accepts an
existing sidecar; it is not another required step.

Conversion uses Tracker's configured optional Python environment, including its
persistent `~/.config/skellytracker/dlc-converter.json` or the explicit
`SKELLYTRACKER_DLC_CONVERTER_PYTHON` override. The normal app environment need not
contain PyTorch or DeepLabCut. Preserve the sidecar beside its ONNX artifact.
Unsupported model architectures fail explicitly.

Choose **CPU FP32** or **CUDA FP32** and enable 2D Tracking. The DLC settings
checkbox **Reconstruct 3D from calibrated cameras** uses the existing
live triangulation setting. Calibrated multicamera points use the ordinary
keypoint channel and viewport; they require neither an anatomical skeleton nor
an STL. Without applicable multicamera calibration, the DLC stream retains its
2D overlays and does not publish pixel-plane values as metric 3D points.
Disable the checkbox for model-only 2D use. The live calibration and reference
transform controls retain their existing meaning.

For posthoc processing, select the recording and its calibration, choose DLC and
its sidecar, then enable the same checkbox for triangulation and filtering.
Leaving it off saves only observations. DLC spatial processing preserves the
calibration reference frame and does not infer a human ground plane, pelvis or
body alignment. Names and source identities remain declared in saved channels.
The current model-only path stops before skeleton fitting and Blender export.

Optional rigid-object/STL reconstruction is a separate geometry association.
A detector's points do not define a mesh origin, axes, physical units or landmark
correspondences. That association must preserve the authored mesh frame and use
Forge reconstruction rather than a human model or a new solver in Core. This
geometry association is selected in **Rigid object geometry (Optional)**.
Click **Choose geometry** and select the feature-definition JSON. It is saved
automatically; **Remove geometry** returns to keypoints only.
With triangulation enabled, live fitting and posthoc reconstruction use the existing
Forge rigid-body solver. Leave the geometry field blank for model-only keypoints.
The feature names and order must exactly match the selected detector sidecar;
an STL alone cannot supply those correspondences.

The definition includes millimeter feature positions, an explicit nominal reference
unit, and the original source-mesh frame. The runtime publishes fitted scale and
segment pose through existing channels. Optional `object_geometry` metadata carries
row-major homogeneous transforms from object millimeters and original source mesh
units to dimensionless segment reference coordinates, plus the inverse mesh transform.
It is retained in saved model snapshots and every self-describing model definition.
Use the measured fitted scale when placing the original mesh; do not substitute the
nominal reference size or assume the segment origin is the STL origin. Forge owns
the composition through `StlRigidBodyDefinition.source_mesh_to_world_matrix`.
The current app draws points and rigid reconstruction, not a loaded STL surface.
Blender export remains disabled for DLC in this integration.

CPU verification covers observation-only and calibrated spatial recording,
calibration-frame preservation, self-contained named 3D transport and the actual
SDK decoder/resolver-to-viewport buffer path. Live cameras, GPU performance and
visual acceptance remain distinct checks; software tests do not establish them.
