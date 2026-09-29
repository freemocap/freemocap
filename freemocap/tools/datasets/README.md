# Reference dataset processing

Run commands from **the FreeMoCap repository**, `project/repos/freemocap`,
with its environment activated. Without activation, use
`uv run --no-sync poe ...` after setting up that environment.

```powershell
poe process-test-data
poe process-sample-data
poe process-all-data
```

These commands run the standard production pipelines: fresh calibration, RTMPose
tracking, triangulation, trajectory preparation, automatic coordinate alignment,
skeleton reconstruction, and the accepted SkellyForge skeleton fit. They rerun
processing even if old results exist. `process-all-data` runs **test_data first,
then sample_data**, stopping at the first failure. It does not run pytest.

The datasets show the same event with three cameras: `test_data` has 222 frames at
6 fps, and `sample_data` has 1,108 frames at 30 fps. Test data is for fast checks;
sample data is for full runs. Low-pass filtering remains disabled for test data
and enabled for sample data; both use production gap filling. Blender export is
disabled. Videos are acquired from the existing released archives, not regenerated.

## Choose work explicitly

```powershell
poe process-all-data --dry-run
poe process-test-data --calibration existing
poe process-sample-data --calibration "C:\calibrations\my_calibration.toml"
poe datasets status test_data
poe datasets acquire sample_data
poe datasets calibrate test_data
poe datasets process test_data --from triangulation --calibration existing
poe datasets process test_data --from filtering
poe datasets process test_data --from scale_fit
poe datasets process test_data --from reconstruction
poe datasets process test_data --from skeleton_fit
poe datasets validate test_data
```

The complete commands are aliases for `poe datasets process test_data`,
`poe datasets process sample_data`, and `poe datasets process-all`.
`--no-skeleton-fit` omits the final fit. `--timeout SECONDS` sets the limit for each
pipeline. `--run-id` and `--sensor-group` select saved inputs when restarting;
the default is the selected saved run and its sole eligible sensor group.

Automatic alignment preserves a calibration marked aligned; otherwise it estimates
alignment from the person. `--alignment calibration` preserves the calibration's
frame and `--alignment person` forces a new estimate. A full run or retriangulation
must produce an acceptable alignment outcome before its results become current,
unless preserving calibration was explicitly requested.

`--calibration existing` selects the separately generated dataset calibration,
then the current prepared recording's calibration, then a recording-local source
calibration. The application-wide last calibration is never selected implicitly.
The chosen path is printed before work. Starts after triangulation reuse saved
3D coordinates and their calibration provenance; calibration and alignment
overrides are rejected there. Missing inputs cause an error, not a hidden full run.

Saved-stage processing retains the saved scientific model definitions. To update
tracker mappings or skeleton definitions, use a full run or the existing explicit
reconstruction-refresh helper; merely rerunning the fit is a different operation.

## Files on disk

Default locations:

- Original downloads: `~/freemocap_data/recordings/freemocap_{test,sample}_data/`.
- Prepared results: `~/freemocap_data/testing/prepared/freemocap_{test,sample}_data/current/recordings/`.
- Separate calibration-only results: the dataset's `calibration/current/recordings/`.
- Previous accepted results: the dataset's `history/` directories.
- Working files, requests, and logs: the dataset's `attempts/` directories.

`--recordings-root PATH` and `--prepared-root PATH` override the first two roots.
They must not overlap. Original downloads are never overwritten. Generated results
are local files; these commands do not upload them or change Git state.

New work happens in a separate folder. The workflow checks the results before
replacing `current`, and saves the previous recording under `history`. Failed runs
leave current results intact and keep their log. `ready.json` identifies the saved
results and their hashes, configuration, source identity, and software provenance.
Calibration-only processing does not replace mocap data or claim to recalibrate
previous outputs. `status` reports the calibration hashes separately.

Directory and marker replacement is recoverable, not one atomic filesystem
operation. If interrupted during replacement, readers reject the pending save.
Run `poe datasets recover test_data` (or `sample_data`) to finish a completed save
or restore the previous results. Recovery preserves interrupted output separately.
Do not manually edit `ready.json` to bypass a checksum mismatch.

Old prepared outputs and logs are not automatically pruned. Keep them while
reviewing a change. Consumers should not hold open prepared files during replacement.

## Tests versus processing

The old `freemocap.tests.prepare_recording_dataset` entry point remains compatible:
it reuses existing preparation, and `--fresh` checks a fresh run without replacing
an existing accepted recording. Use the commands above when the intention is to
**save newly processed data**. The old reconstruction-refresh command remains
available for replacing model outputs from saved 3D points.

Focused workflow checks:

```powershell
python -B -m pytest freemocap/tests/test_dataset_workflow.py freemocap/tests/test_recording_preparation.py
```

Acceptance validates recording structure, frame grids, calibration/alignment,
and fitted channel completeness, finite values, and unit rotations. It does not
claim anatomical accuracy or enforce experimental fit-quality thresholds.

## Current integration blocker (2026-09-29)

A fresh `test_data` run completed calibration, tracking, triangulation, person
alignment (`foot_support`), and reconstruction, then failed in SkellyForge
revision `31cdfda4` with `KeyError: pelvis_origin`. Production gap filling now
retains missing observations at the recording's tail. The fitter's position
priors require spine landmarks on every frame; `pelvis_origin` is absent from
the final six frames. Supporting missing position-prior observations needs a
SkellyForge change before the default full run can pass.

The failed attempt retained the previous accepted recording. The runner does
not fill those observations, drop frames, or disable fitting automatically.
The sample-data full run and real saved-stage restart checks remain pending
that dependency fix. The explicit `--no-skeleton-fit` option is not evidence
that the default full workflow passes.
