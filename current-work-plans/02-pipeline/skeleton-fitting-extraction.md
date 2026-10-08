# Connected skeleton fitting extraction — 2026-10-08

`development-streaming` uses the ordinary reconstruction pipeline. The experimental
Ceres optimizer is preserved on `development-skelly-fit` in both repositories:

- FreeMoCap: `7334c5f0` pairs the exploration branch with SkellyForge's exploration branch.
- SkellyForge: `8a28aab7f57a6d7e268e5e67baca026bccaf6bcd` preserves the optimizer.
- SkellyForge streaming cleanup: `03f0159f17adf4cc26fcab19e735e4a2c50da9a5`, now consumed by this lockfile.

The FreeMoCap cleanup removes the posthoc optimizer stage, configuration, CLI
options, saved solver channels, playback renderer, prototype target adapter and
their exclusive tests. Existing fitted-recording compatibility is intentionally
out of scope. Ordinary scale fitting (including the older realtime setting named
`skeleton_fitting_enabled`), reconstruction, biomechanical outputs, mapping
snapshots, trajectory gap handling and tall CSV export remain.

## Validation and reproducibility

Core's dependency was refreshed with `uv lock --upgrade-package skellyforge` and
`uv sync --locked --group dev`. The installed Forge revision matches the lockfile;
no native solver module is installed. Other package versions were unchanged. The
resolver reordered platform markers and made SkellyLogs' existing `main` branch
explicit without changing its commit.

Both reference recordings were processed from copied videos and board definitions
through fresh calibration, detection, triangulation, filtering policy, scale
fitting, reconstruction, Parquet publication and tall CSV export. The small
recording has 222 frames and filtering disabled; the sample has 1,108 frames and
filtering enabled. Both production validations passed. All eight original input
file hashes remained unchanged. Output metadata contains no optimizer stage or
solver source.

All six reference consumer tests passed: filter restart/provenance/cancellation,
complete CSV scalar comparisons, and reconstructed trajectory/geometry checks
for each recording. These tests also preserve the producer output hashes.

Use a short temporary directory on Windows to avoid video/path-length limits:

```powershell
# $scratch contains raw/<recording_name>/synchronized_videos/*.mp4 and
# raw/<recording_name>/charuco_board_info.json, copied from the reference inputs.
python -B -m freemocap.tools.datasets process-all --recordings-root "$scratch/raw" --prepared-root "$scratch/prep" --timeout 1800
$env:FREEMOCAP_PROVENANCE_PREPARED_ROOT = "$scratch/prep"
python -B -m pytest freemocap/tests/reference_recordings/test_provenance_reprocessing.py freemocap/tests/reference_recordings/test_tall_csv_acceptance.py freemocap/tests/test_trajectory_recording_acceptance.py --basetemp="$scratch/accept" -p no:cacheprovider
```

Local reports and input-hash/path manifests are ignored under
`.test-artifacts/extraction/`. Actual validation outputs are in the external
temporary directory recorded by `validation-paths.json`; they are not fixtures
to commit. Acceptance consumers copy the produced Parquet before reprocessing.

Focused backend checks: 80 passed. Playback data checks: 5 passed. TypeScript
checking passed. The staged-processing browser test passed with installed Edge;
its HTTP teardown now closes persistent browser connections. All 633 core tests
collect successfully; this is not a claim that the whole suite was executed.

Additional scale/model checks: 12 passed, one existing expectation failed:
`test_a_subject_at_a_desk_still_gets_correctly_sized_feet` computes seated scale
1584.2657 versus standing 1684.1504, outside its 5% tolerance. The test, tracker
mapping adapter and Forge scale/geometry implementation are unchanged relative
to the preserved branches. This extraction does not adjust the tolerance or
change geometry. Forge's earlier validation also retains the independently
baseline-confirmed pure-pronation test failure documented in its handoff.

## Remaining work

The CSV size issue remains: these fresh outputs are 8,459,424 and 39,345,020 bytes
of Parquet, versus 360,369,163 and 1,813,055,892 bytes of dynamic tall CSV.
Removing the optimizer is not a data-model redesign. Audit scalar-row repetition
and export representation separately. Wide CSV, NPZ and Blender integration remain
subsequent milestones. Do not reintroduce solver compatibility as part of them.

The human reviews, commits and pushes FreeMoCap's cleanup on
`development-streaming`; agents do not mutate Git state.
