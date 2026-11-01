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

On the next application launch, stop the active tracking pipeline and choose
**RTMW + MediaPipe hands** in the detector settings before starting it again.
Compare against **RTMPose** using the same camera, calibration and reconstruction
settings. The new preset adds MediaPipe hand inference after RTMW whole-body
inference. Its extra processing cost and missing-hand behavior must be acceptable
before considering any default change. The user judges visual quality; the
recording benchmarks do not establish that judgment.

## Custom-model boundary

The sidecar/session path can load a supported local ONNX artifact. It does not
provide a DLC importer, generic detector, heatmap decoder or coordinate decoder.
Session warm-up currently assumes float32, three-channel NCHW input. Tracker's
contract tests explicitly exercise these unsupported cases. Model-specific
preprocessing, output metadata, decoding and keypoint schemas belong in Tracker;
Core must not add them to work around missing Tracker support.
