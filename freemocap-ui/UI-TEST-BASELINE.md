# macOS UI integration baseline

Baseline source: `8c209ec2` (2026-11-02), before the Skull theme refactor.
Harness branch: `sfn26-ui-harness`; local design remote: `refactor`.
Initial baseline work is complete with the acceptance failures documented below.

## Reproduce

Run from `repos/freemocap-ui-harness/freemocap-ui` unless stated otherwise.

- `npm install`, then `npm install-scripts approve electron esbuild`.
- In `../packages/freemocap-client`: `npm install && npm run build` first.
- `npx playwright install chromium`.
- `npm test`: existing SDK/typecheck/unit runner, including camera and operation-progress checks.
- `npm run test:styles`: all source CSS variable definitions, exact-case `icons.css` targets, and hex additions relative to `8c209ec2` outside `styles/color.css`.
- `VSCODE_DEBUG=1 npm run dev`: UI at port 7777 without automatic Electron launch.
- `npm run test:harness`: main screens, all eight modal sections, full modal processing POST, axe contrast, and Electron startup. Screens use a fixed clock, 1280×720 viewport, en-US, dark mode, and disconnected camera/server state. Backend processing is tested separately.
- `npm run test:harness -- --update-snapshots`: explicit initial visual capture only. Never update baseline images while checking a refactor. The committed request fixture is never auto-updated.
- From checkout root: `../freemocap/.venv/bin/python -B freemocap-ui/e2e/fixtures/create_decoder_fixture.py` generates ignored media without rewriting tracked fixture data.
- `FREEMOCAP_TEST_PYTHON=/absolute/path/to/repos/freemocap/.venv/bin/python FREEMOCAP_PYTHON=/absolute/path/to/repos/freemocap/.venv/bin/python npm run test:standard`: existing Playwright specs, serial, with full JSON results.
- From checkout root, using Core's configured Python environment: `poe test-reference` now invokes all reference-recording tests. Set `FREEMOCAP_REFERENCE_RECORDINGS_ROOT`, `FREEMOCAP_PROVENANCE_PREPARED_ROOT`, `FREEMOCAP_TEST_DATA_PATH`, and `FREEMOCAP_BASE_FOLDER` to isolated ignored directories. Pipeline tests are under `freemocap/tests/pipelines/`; the recorded realtime path moved to `reference_recordings/test_realtime_pipeline.py`.

Artifacts live in the checkout root `.test-artifacts/baselines/`, `.test-artifacts/harness-results/`, and `.test-artifacts/standard-results/`. PNGs remain local; the request JSON in `e2e/fixtures/` is an intentional, portable fixture. Full contrast violations and cases requiring manual review are attached to Playwright JSON results. Definitions are checked source-wide; the static guard cannot prove CSS cascade availability, so browser checks remain necessary.

## Setup findings and fixes

Apple Silicon Mac; Python 3.12.14, Node 24.20.0, Playwright 1.59.0, Electron 35.7.5.

1. Sandboxed npm could not resolve registry.npmjs.org; network-enabled installation succeeded.
2. npm blocked install scripts; approved Electron/esbuild explicitly.
3. UI imports failed before building the local `@freemocap/client` package. Building it restored a clean UI typecheck.
4. `uv sync --frozen --group dev` failed linking SkellyCam: `ld: library 'turbojpeg-static' not found`. The downloaded macOS ARM64 archive contains `libturbojpeg.a`. Initially installed the Python environment with `--no-install-package skellycam-rust`. After owner approval, SkellyCam commit `e7eeda45` corrected the macOS static library name. Full `uv sync --frozen --group dev` then succeeded and `_skellycam_rust` imported successfully. Native camera capture remains unverified without hardware.
5. Core's pre-existing dirty `uv.lock` is preserved. Editable imports resolve to canonical sibling SkellyCam, Tracker and Forge checkouts; import evidence is saved locally.
6. Backend on port 8005 returned HTTP 200 for `/openapi.json`. UI shell starts in Electron. Initial launch-to-React-root/fonts-ready measurement: 2595.30 ms; this excludes backend readiness and is not a cold-install benchmark.
7. Standard reference processing fails during Blender preflight: `Automatic Blender packaging is not yet supported for Blender 5.2, Python 3.13, macos-arm64`. Numerical-only results do not certify standard exports.
8. Existing tooltip tests defaulted to Microsoft Edge, absent on this Mac; harness defaults to installed Playwright Chromium. Generated H.264 B-frame fixture was absent; its generator now writes ignored artifacts. Example test's Python fallback now supports POSIX.

## Initial findings

- Typecheck: pass after client build.
- Unit runner: 96 passing tests plus one reference-file skip, two camera assertions passing, and seven operation-progress tests passing (103 named passes total).
- Static guard: 32 undefined-variable use locations (some with fallback values), two invalid icon paths, zero new hex values against the baseline. These are failures, not grandfathered passes.
- Visual repeat: all 11 PNG comparisons pass on repeat at the initial tolerance; the default modal POST matches the committed fixture. Existing separate request tests cover 36 alignment/filter combinations.
- Contrast: baseline failures include 4.0:1 action-button text, 2.56:1 secondary labels, and 3.33:1 black button text. All three main surfaces and the modal have violations in stable disconnected state. Full node/ratio evidence is retained.
- Initial existing E2E suite: 74 passed, 12 failed, 10 not reached. Missing fixture, incomplete Python setup, Edge default, stale streaming-output selectors and a Parquet setup timeout were identified. Configured rerun: 92 passed, three stale streaming-output tests failed, one real-Parquet test skipped without its file environment variable. All three then passed after updating their selectors and assertions to the existing VMC/LSL controls and explicit-refresh behavior; no product code changed. Original output is preserved.
- Standard reference run failed before processing (worker lifecycle 5.10 s). Numerical test-data run passed: mocap 63.002 s; worker lifecycle 73.324 s; tracking 56.676 s. Timings are observations under concurrent UI testing, not isolated performance benchmarks. Sample-data numerical run passed: mocap 220.190 s; worker lifecycle 250.299 s. The pipeline directory suite passed all 29 tests; the final reference results are recorded below.

## First refactor comparison

Design commit `367fd72c` (theme `52b97572`) was merged into the harness at `551bbb4f`. All 96 configured E2E tests pass with the real reference Parquet, with zero skips. Typecheck and unit runner pass with reference manifest supplied (104 named tests plus two camera checks). The complete modal POST is unchanged. Icon paths and hex additions pass; 26 undefined-variable locations remain. Eleven strict image comparisons record the intended palette changes. Contrast still fails, including newly reported white-on-gray controls at 3.41:1 and error text at 2.39:1. Pixel comparison now uses threshold zero because the default tolerance concealed subtle palette shifts; frozen baseline PNGs were not updated. The per-commit report is in the design checkout under `.test-artifacts/reports/367fd72c.md`.

## Harness audit

`npm test` and `poe test-reference` were missing; explicit entry points now exist. Nox still installs `.[dev]` although dev is a dependency group, and its legacy file lists need separate maintenance; the direct configured environment is used here. Some historical TESTING.md file names no longer exist. Main-screen visual and contrast assertions, modal full-request comparison, and source style/icon checks were missing. Existing component specs remain useful and are retained.

No live cameras are attached. UI no-camera state is covered; real capture, camera enumeration accuracy and capture timing are not certified. CUDA provider-switch cases cannot run on this CPU-only Mac and must be reported individually. Other missing prerequisites or failed tests are not classified as camera skips.

## Measured numerical reference baseline

These operation intervals overlap and must not be summed. Calibration solver time is narrower than complete calibration. Parquet checksums identify these exact artifacts; a fresh run can differ because it includes run identity and timestamps. Numerical equality checks in the reference suite are the semantic regression guard.

| Operation | Test data (222 frames), s | Sample data (1,108 frames), s |
| --- | ---: | ---: |
| Reading videos and detecting poses and requested board points | 56.6756 | 192.1594 |
| Drawing tracking overlays and saving annotated video 1 | 3.5389 | 16.7058 |
| Drawing tracking overlays and saving annotated video 2 | 3.4915 | 16.5922 |
| Matching camera views and calculating 3D points | 0.3791 | 1.7729 |
| Preparing detected image points for saving | 0.0350 | 0.0478 |
| Saving detected image points to disk | 0.3156 | 1.7674 |
| Filling gaps and smoothing 3D point movements | 0.0091 | 0.0632 |
| Orienting 3D motion in the recording coordinate system | 0.3392 | 1.4876 |
| Preparing 3D points for skeleton fitting | 0.0019 | 0.0094 |
| Preparing reconstructed 3D points for saving | 0.0005 | 0.0005 |
| Saving reconstructed 3D points to disk | 1.0911 | 5.3881 |
| Fitting skeleton body dimensions to this recording | 0.0701 | 0.2092 |
| Calculating skeleton positions and joint rotations | 0.6903 | 3.0821 |
| Saving reconstructed motion to the recording Parquet file | 0.7622 | 4.0126 |
| Drawing tracking overlays and saving annotated video 3 | 2.5551 | 11.1368 |

| Artifact | SHA-256 |
| --- | --- |
| freemocap_test_data_data.parquet | `a5f2649d5071ea9eb9d0bbb013da642ed789ffac096ace1c27f6b31b7f0018d1` |
| freemocap_test_data_camera_calibration.toml | `95ad6396dbf6babb196da3d70f724f350363584caef8f75986d0728aacd4c9f6` |
| freemocap_sample_data_data.parquet | `1c28762383480a74bf08bdef8c51bbcfc9122071b60e1888e34483d0cb780eef` |
| freemocap_sample_data_camera_calibration.toml | `a67e9861f1b07d268d25dfd1d770a2e68e3a8c672e27b7eeda4214567107497f` |

Re-extract and independently verify checksums from checkout root:

```sh
python3 freemocap-ui/tools/reference-baseline.py --prepared-root .test-artifacts/prepared-numerical --output .test-artifacts/baselines/reference-numerical.json
```

## Final reference matrix

51 cases: **34 passed, 9 failed, 4 setup errors, 4 skipped**, 717.28 seconds. Recorded-video replay cases passed; no test was skipped for missing physical cameras. The four skips require CUDA.

The fresh standard producer fails Blender preflight. Eight downstream failures and four fixture errors reject numerical-only preparation as certification of standard outputs. These are unresolved acceptance failures, not passing exports. Both numerical artifact sets were rehashed after the suite and match the original baseline exactly.

Full output: `.test-artifacts/baselines/reference-tests.log`; JUnit: `.test-artifacts/baselines/reference-tests.xml`.

| Status | Test | Exact message |
| --- | --- | --- |
| failure | `test_saved_blender_matches_all_reference_frames[freemocap_test_data]` | ValueError: Numerical-only preparation does not certify a complete standard run |
| failure | `test_saved_blender_matches_all_reference_frames[freemocap_sample_data]` | ValueError: Numerical-only preparation does not certify a complete standard run |
| failure | `test_saved_blender_rejects_changed_geometry[landmark]` | ValueError: Numerical-only preparation does not certify a complete standard run |
| failure | `test_saved_blender_rejects_changed_geometry[armature]` | ValueError: Numerical-only preparation does not certify a complete standard run |
| failure | `test_fresh_calibration_and_mocap_publish_current_recording` | subprocess.CalledProcessError: Command '['/Users/jon-mac-mini/code-stuff/github/freemocap/project/repos/freemocap/.venv/bin/python3', '-B', '-m', 'freemocap.tools.datasets.preparation', '--worker', '/Users/jon-mac-mini/code-stuff/github/freemocap/project/repos/freemocap-ui-harness/.test-artifacts/prepared-numerical/freemocap_test_data/scratch/request.json']' returned non-zero exit status 1. |
| error | `test_reference_playback_frame_grid_and_human_model` | failed on setup with "ValueError: Numerical-only preparation does not certify a complete standard run" |
| error | `test_reference_human_inputs_and_matching_scale_fit` | failed on setup with "ValueError: Numerical-only preparation does not certify a complete standard run" |
| error | `test_reference_calibration_and_alignment_provenance` | failed on setup with "ValueError: Numerical-only preparation does not certify a complete standard run" |
| error | `test_reference_playback_http_bytes_and_revision` | failed on setup with "ValueError: Numerical-only preparation does not certify a complete standard run" |
| failure | `test_fresh_outputs_then_filter_restart_preserve_provenance[freemocap_test_data-222-1.0]` | ValueError: Numerical-only preparation does not certify a complete standard run |
| failure | `test_fresh_outputs_then_filter_restart_preserve_provenance[freemocap_sample_data-1108-4.0]` | ValueError: Numerical-only preparation does not certify a complete standard run |
| skipped | `test_provider_switch_reuses_capture_and_releases_sessions[test-data-centralized]` | CPU-to-CUDA replay needs a CUDA runtime |
| skipped | `test_provider_switch_reuses_capture_and_releases_sessions[test-data-per-camera]` | CPU-to-CUDA replay needs a CUDA runtime |
| skipped | `test_provider_switch_reuses_capture_and_releases_sessions[sample-data-centralized]` | CPU-to-CUDA replay needs a CUDA runtime |
| skipped | `test_provider_switch_reuses_capture_and_releases_sessions[sample-data-per-camera]` | CPU-to-CUDA replay needs a CUDA runtime |
| failure | `test_tall_export_matches_every_production_sample[freemocap_test_data]` | ValueError: Numerical-only preparation does not certify a complete standard run |
| failure | `test_tall_export_matches_every_production_sample[freemocap_sample_data]` | ValueError: Numerical-only preparation does not certify a complete standard run |

## Watching

The active `freemocap-ui-integration-watch` chat heartbeat checks the local refactor remote every five minutes. Its durable cursor is `.test-artifacts/watch/last-tested.json`. It stays quiet when unchanged and reports completed new results. Keep this Mac and the desktop app running. Test-managed backend and Vite servers were stopped after the initial run.
