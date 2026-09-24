# Refresh prepared skeleton outputs

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
reconstruction and biomechanics checkpoints are removed; this helper does not
claim a full pipeline rerun. The preparation checksum is updated after validation,
with a separate `reconstruction_refresh` provenance entry. Original preparation
identity is retained. A failure between Parquet publication and marker replacement
leaves a checksum mismatch that blocks automatic reuse; inspect it before recovery.

Then regenerate the real-data viewer from the SkellyForge repository:

```powershell
.\.venv\Scripts\python.exe -B scripts/generate_real_skeleton_viewer.py
```

Refresh `http://127.0.0.1:8771/real_skeleton_viewer.html` if its server is already
running. Otherwise add `--serve` to the generator command.
