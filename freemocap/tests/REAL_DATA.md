# Reference recording tests

## Acquisition and inspection

The raw datasets live at `~/freemocap_data/recordings/freemocap_test_data`
and `~/freemocap_data/recordings/freemocap_sample_data`.
`recording_datasets.acquire_recording` reuses an existing recording or downloads
and extracts the corresponding release. It accepts an explicit recordings root.
An incomplete existing directory is preserved and reported, not overwritten.
Acquisition currently checks directory structure only; it does not establish
video validity or processing readiness. The older pipeline fixtures are not
yet wired to this helper.

Read-only inspection, from the core repository using its installed Python:

```powershell
.\.venv\Scripts\python.exe -B -m freemocap.tests.inspect_recording_datasets
```

On other platforms use `.venv/bin/python`. Options: `--dataset test|sample|all`
and `--recordings-root PATH`. The inspector does not download or process data.
It decodes all frames, checks the reference frame counts and matching camera
presentation timelines, validates board metadata, and reports SHA-256 video
fingerprints and available calibration, Parquet, and timestamp files.

## Measured contents, 2026-09-23

| Property | Test data | Sample data |
| --- | --- | --- |
| Cameras | 3 | 3 |
| Decoded frames per camera | 222 | 1,108 |
| Video dimensions | 720 x 1280 | 720 x 1280 |
| Nominal playback FPS | 6 | 30 |
| First / last frame timestamps, seconds | 0 / 36.833333 | 0 / 36.9 |
| Board | 7 x 5, 58 mm squares | 7 x 5, 58 mm squares |
| Bundled calibration TOML | Yes | Yes |
| Processed Parquet | No | No |
| Timestamp sidecars | No | No |

All six videos decoded successfully. The owner confirms both datasets are the
same recording: ChArUco calibration movement followed by body movement. Test
data is temporally decimated; measured playback rates indicate a factor of five.
Exact frame-to-frame correspondence and movement intervals have not yet been
verified. Presentation timestamps describe playback, not original capture-clock
measurements. Do not use these recordings as evidence of hardware synchronization.

Release archive SHA-256 values reported by GitHub (not independently verified
against downloaded archive bytes by the current helper):

- Test: `543a38c86e591476975a8c3d8dd05c5243777a769c696e116c6aaea43f5170b1`
- Sample: `c23d6a24f9ed8cca74bccf171128543d661b47e5780df5b446d60063ac4acf4f`

## Preparing reusable results

From the core repository:

```powershell
.\.venv\Scripts\python.exe -B -m freemocap.tests.prepare_recording_dataset --dataset test
```

The helper acquires missing raw data, inspects it, copies videos into an isolated
attempt, regenerates calibration with the explicit 7 x 5 board, and runs the real
RTMPose posthoc mocap pipeline. It does not copy the bundled calibration into the
attempt. Application settings and calibration writes are isolated too. The
installed core environment must already contain the pipeline dependencies and
have access to required detector assets.

Prepared recordings live at
`~/freemocap_data/testing/prepared/<dataset>/current/recordings/<dataset>/`.
The command prints this stable directory. Keep its normal outputs, including
annotated videos, diagnostics, calibration, and Parquet. The testing root gets
`FILES_IN_THIS_FOLDER_GET_DELETED_AUTOMATICALLY_DO_NOT_STORE_ANYTHING_YOU_CARE_ABOUT.txt`.
The original downloads remain outside this disposable space.
A ready marker is published only after both tasks
report successful completion and current Parquet validation passes: frame grid,
camera geometry, standard human model, sample schema, and finite values in the
required channels. The result report retains calibration and alignment history.
These are readiness checks, not independent reconstruction-accuracy benchmarks.

Completed results are reused after checking input identity, output hashes, and
current Parquet compatibility. Software and preparer fingerprints are retained
as provenance; changes to them do not automatically rerun expensive processing.
Detector weight files are not yet fingerprinted. Changed inputs or damaged
outputs fail explicitly rather than silently regenerating them. To deliberately
regenerate prepared data, stop consumers and remove that dataset's preparation
directory, then run the helper again.

`--fresh` executes both pipelines in a fixed `scratch/` sibling of `current/`.
It clears previous scratch outputs before execution so old files cannot satisfy
a producer test. A successful run removes scratch and preserves existing prepared
results; when no prepared result exists, the first success becomes `current/`.
A failed scratch run stays available for diagnosis until the next fresh attempt.
Its request, log, and partial outputs never qualify as prepared results. Dataset
locking serializes helper runs; cleanup rejects filesystem links and targets only
scratch. Consumers must not manually delete or regenerate data while it is in use.
Options also include `--recordings-root`, `--prepared-root`, and a per-pipeline
`--timeout` in seconds.

The helper adopts a compatible successful preparation from the previous hashed
layout without rerunning processing. Historical failed attempts are not swept by
normal cleanup: they can be removed manually after checking that their old workers
have stopped. New runs no longer create accumulating hashed attempt directories.

The decimated test recording has a 6 Hz playback rate. Preparation disables
trajectory filtering for it because the default 6 Hz cutoff exceeds its 3 Hz
Nyquist limit. `--dataset sample` uses the 30 Hz recording and enables production
filtering defaults. Use sample data when testing temporal/trajectory behavior.

Validated locally on 2026-09-23: fresh calibration and real posthoc processing of
all 222 test frames completed, followed by Parquet validation. The runner uses
production workers in thread mode; this does not exercise process-mode transport.
Sample-data processing has not yet been run through this helper.
The stable-layout migration and a fresh 222-frame scratch run were also validated:
the original prepared Parquet hash stayed unchanged and scratch was removed after
successful processing and validation.

## Real-data consumer checks

Run the dedicated consumer group from the core repository:

```powershell
.\.venv\Scripts\python.exe -B -m pytest freemocap/tests/reference_recordings/test_prepared_consumers.py -q
```

These four `e2e` checks share one session preparation, using the home-folder test
dataset and stable prepared recording described above. Missing data is acquired
and prepared once; existing invalid data fails explicitly. They do not request
`--fresh`, and ordinary software revisions do not cause inference to rerun.

The checks cover the playback frame/camera timeline and human model mapping,
loading saved human reconstruction inputs with their matching scale fit,
calibration/alignment provenance, and the HTTP manifest/Parquet endpoints with
revision rejection. A fixture teardown verifies that calibration and Parquet
bytes have not changed. The HTTP test runs in-process, without a browser or
network server. These establish consumer compatibility, not pose accuracy.
The existing synthetic reader tests remain useful for malformed-input cases.

## Fresh posthoc pipeline test

```powershell
.\.venv\Scripts\python.exe -B -m pytest freemocap/tests/reference_recordings/test_fresh_posthoc.py -q
```

This `e2e`/`slow` test always runs real calibration and RTMPose mocap in clean
scratch space. It asserts successful task states, selection of the newly generated
calibration, matching isolated calibration copies, calibration solve quality,
fully decoded annotated videos, and all 222 frames of human landmarks and unit
quaternions in Parquet. Board output cannot substitute for missing human output.
Assertions execute before cleanup; a failed assertion retains scratch diagnostics.
Existing prepared recordings remain intact. Running the whole `reference_recordings`
directory runs both this fresh test and the four consumer tests.

This replaces the two old posthoc test modules and their unused NPY/CSV fixture.
Legacy calibration/cache/realtime fixtures remain separate pending their own
refactor. Old absolute CoM-height and anatomical CSV assertions are not claims
made by this replacement: anatomical accuracy needs a separately reviewed check
against current landmark definitions and alignment conventions.

## Remaining integration

Downstream tests reuse compatible completed results. Full-pipeline tests execute
into fresh outputs. Test data is the default; sample data serves trajectory,
filtering, timed replay, and sustained-load tests. Core owns integration across
Tracker, Forge, and recording adapters. Blender and secondary exports are deferred.
