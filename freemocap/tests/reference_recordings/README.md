# Reference recordings

For full runs, calibration-only processing, and saved-stage reprocessing, see the
[dataset commands](../../tools/datasets/README.md). Start with
`poe process-test-data`, `poe process-sample-data`, or `poe process-all-data` from
the FreeMoCap repository. These save newly processed results on disk.

## Recording-contract and provenance acceptance

Use the production dataset workflow as the producer, then test its saved files.
The full command runs real calibration, detection, scale fitting and reconstruction;
the consumer test copies the resulting Parquet and reruns filtering/reconstruction
without videos. It checks saved settings against execution-time defaults, unchanged
upstream rows/provenance, updated downstream settings, cancellation and producer hashes.

```powershell
# Use your existing downloads as inputs; choose a separate output root.
python -B -m freemocap.tools.datasets process-all --recordings-root C:/data/recordings --prepared-root C:/data/contract-check
$env:FREEMOCAP_PROVENANCE_PREPARED_ROOT = 'C:/data/contract-check'
python -B -m pytest freemocap/tests/reference_recordings/test_provenance_reprocessing.py -q -p no:cacheprovider
```

The consumer test explicitly skips without that environment variable. Supplying a
root requires both complete, freshly processed datasets and valid ready markers;
missing or stale outputs fail acceptance. Use external temporary storage or verify
repository output paths are ignored before generating logs/JUnit reports.

Extend this fixture chain for export and Blender acceptance instead of adding an
independent sample-data generator. See the [recording contract](../../../RECORDING_CONTRACT.md).

Tall CSV now uses this same prepared root:

```powershell
python -B -m pytest freemocap/tests/reference_recordings/test_tall_csv_acceptance.py -q -p no:cacheprovider
```

It streams comparisons of every dynamic row and checks static measurements and
unchanged Parquet hashes on copies of both recordings. The full sample tall CSV
is approximately 1.9 GB; use an ignored or external temporary directory with room
for those generated files. [Export usage](../../core/recording/exports/README.md)
describes default/retained output and interrupted-publication recovery.

## Refresh prepared skeleton outputs

After changing a tracker mapping or Forge skeleton calculation, reuse saved 3D
keypoints instead of detecting, calibrating or triangulating the videos again:

```powershell
.\.venv\Scripts\python.exe -B -m freemocap.tests.refresh_recording_reconstruction --dataset test
```

Run from the FreeMoCap repository. The default dataset root is
`~/freemocap_data/testing/prepared`; `--prepared-root PATH` overrides it.
`--dataset sample` is explicit; the command never refreshes sample data by default.

This replaces the selected run's standard-human model, fixed scale fit, landmarks,
rotations, joint angles and any existing center-of-mass output together. It uses
current installed Tracker and Forge definitions and the original saved raw/filtered
3D input selection. It does not filter those points again. Other model and input
rows, retained runs, videos and calibration files are preserved. The command
currently requires the human model to belong to exactly one sensor group.

Publication validates and atomically replaces the Parquet file. Old scale-fit,
reconstruction and biomechanics checkpoints/provenance are removed
for stages depending on the replaced model; this helper does not
claim a full pipeline rerun. The preparation checksum is updated after validation,
with a separate `reconstruction_refresh` provenance entry. Original preparation
identity is retained. A failure between Parquet publication and marker replacement
leaves a checksum mismatch that blocks automatic reuse; inspect it before recovery.

Connected-fitting viewers are preserved on `development-skelly-fit`. Use the current
recording playback UI to inspect ordinary reconstructed outputs.
