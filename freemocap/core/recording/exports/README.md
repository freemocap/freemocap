# Scientific exports

In **Open Mocap Processing → Exports**, choose data separately from formats.
All exports are optional. **3D landmarks** is the sole default data selection.
Raw triangulated 3D keypoints, filtered 3D keypoints, per-camera 2D keypoints and
rigid-body segment poses start unchecked. Joint-angle export is deferred.
Formats are independent **Wide CSV**, **NPY**, **NPZ**, and **Jupyter Notebook Explorer** checkboxes, initially
off. Export saved results or enable export after processing with the same choices.
The UI shows the expected minimum file count before writing.

Both raw and filtered keypoints use existing saved channels. Segment poses combine
saved segment origins and world WXYZ quaternions, on an identical frame grid and
name order, into `(frames, segments, 7)` with components `x,y,z,qw,qx,qy,qz`.
No new joint-angle calculations, geometry processing or resampling are introduced.
Data is separated by model/source and coordinate reference. The calibration board
and human model therefore have separate landmark tables when both are recorded.

## Layout and metadata

Default exports replace selected CSV files in `exports/csv/` and NPY arrays in
`exports/npy/`. NPZ and the compact inventory remain directly in `exports/`. Other formats retain
their original source identity. Explicit retention writes into `exports/run-<id>/`
and adds `.run-<id>` to filenames. Existing retained formats are not overwritten;
additional formats must use the same source revision. No export allocates a run.

```text
recording/
    recording_data.parquet
    recording_recording_info.json
    exports/
        csv/recording.3d_landmarks--standard_human.csv
        npy/recording.3d_landmarks--standard_human.npy
        npy/recording.frames.npy
        npy/recording.timestamps.npy
        recording_recording_info.json
        recording.npz                         # when selected
        run-0/
            csv/recording.run-0.3d_landmarks--standard_human.csv
            npy/recording.run-0.3d_landmarks--standard_human.npy
            recording.run-0_recording_info.json
```

Filenames use readable data/source labels. Camera exports include the tracker source followed by the existing video
basename. Scientific labels put dimensionality first: `2d_overlay`,
`3d_keypoints_raw`, `3d_keypoints_filtered`, `3d_landmarks`, and
`3d_segment_poses`. CSV/NPY filenames and NPZ member keys use the same labels.
These names do not change canonical Parquet channel identifiers or retention rules. Only filesystem-invalid characters are replaced; collisions get a
stable numeric suffix. Exact source/reference identities remain in metadata.
Hashes are internal provenance fields, never filename identifiers.

Root recording-info JSON preserves existing capture/unknown fields and adds a
compact `processed` section: source Parquet hash, selected run, per-run clocks,
camera names, reference frames, ordered names/components/units and links to export
inventories. Parquet still owns full scientific definitions and measurements.
Publication and saved-result export refresh this companion. A failure is reported;
previously published Parquet remains usable. No diagnostic YAML is generated.

Each export set has a compact `*_recording_info.json` inventory with per-file hash,
source revision/run, ordering, array shapes, timing bounds, units and reference
frames. It does not copy the complete Parquet descriptor or repeat a dictionary
for every scalar column. Existing version-1/2 inventories remain readable; replacing
an older wide export retires only its verified, exporter-owned obsolete files.
Unknown files are preserved. Existing user recordings are not bulk migrated.

## CSV and NumPy values

CSV has one row per recorded frame, with `frame_number,timestamp_s` then named
values. Headers preserve readable names, for example `body.nose.x`, without
URL escaping. The final period separates the component for current scientific
products. Exact axis identity and order remain in metadata; CSV quoting handles
commas and quotes. Units correspond to
the ordered component list in metadata. Files split at 500,000 rows or 1,024 value
columns, with part suffixes only when splitting is necessary.

CSV uses UTF-8 with BOM and float64 round-trip precision. `NaN` is a recorded null;
an empty field is an absent scalar row. Frames are sorted; timestamps are saved
values. No invented frames, interpolation, filtering or unit conversion occurs.

NPY writes one values array per selected data context, plus one shared
`<recording>.frames.npy` and `<recording>.timestamps.npy` for the export set.
Retained sets use the run-qualified prefix. Every measurement array must have the
same frame count, frame numbers and timestamps (allowing only four float64
representable steps of arithmetic roundoff). The shared timestamps come from the
first selected context; metadata records the maximum difference from that vector. The writer checks all three before
publication and rejects incompatible selections without changing previous exports.
It does not pad, truncate, interpolate or resample to make arrays match.

Names, components and units live in the compact export inventory. Spatial arrays
have shape `(frames, names, 3)`; segment poses have seven components. Unavailable
values are NaN, whether the original Parquet entry was absent or explicitly null.
Use `np.isfinite(values)` to test usable values; no presence mask is exported.
Read with `numpy.load(path, allow_pickle=False)`.

NPZ packages those same values arrays and one shared timing pair into one archive,
plus `recording_info.json` inside it. Keys are `<readable-data-source>.values`,
`frames` and `timestamps`. Metadata's `numpy_timeline` identifies the shared files,
archive keys, frame count and completeness check. Read arrays with
`numpy.load(path, allow_pickle=False)` and embedded JSON with
`zipfile.ZipFile(path).read('recording_info.json')`. No object arrays or pickle.

The archive embeds its actual source hash/run and interpretation metadata.

Every written table/array is reloaded and checked for exact saved values, dtype,
shape and missingness before publication. One context is processed at a time;
large source arrays use temporary disk storage. NPZ members are streamed, avoiding
an in-memory collection of all selected arrays.

Jobs return progress, cancellation, retry and paths. Session-local job status does
not survive server restart; publication inventories/journals do. Failed exports
preserve numerical results but fail completion of the requested pipeline outputs.
The shared journal/recovery commands below apply to all three scientific formats.

## Tall CSV diagnostics

In **Open Mocap Processing → Exports**, **Save tall CSV after processing** is
off by default for new preferences. It applies to full processing
and saved-stage reprocessing. **Export tall CSV now** exports the selected saved
run without reprocessing and displays the saved file paths. Reload saved results
if the source revision changed. Files are written to the recording's `exports/`
folder; existing default exports are replaced.

From the FreeMoCap repository with its installed environment:

```powershell
.\.venv\Scripts\python.exe -B -m freemocap.tools.export_tall_csv 'C:/data/recording-id'
.\.venv\Scripts\python.exe -B -m freemocap.tools.export_tall_csv 'C:/data/recording-id' --run-id 0 --keep
```

The first command exports the selected saved run. `--run-id` selects another
retained run. `--expected-revision` accepts the saved-result revision returned by
playback and refuses an outdated selection. No videos, calibration operation,
detection, reconstruction or fitting are required. The source Parquet is unchanged.

```text
recording-id/exports/
    csv/recording-id.tall.csv
    csv/recording-id.static.tall.csv
    recording-id.metadata.json
    run-0/                           # only with --keep
        csv/recording-id.run-0.tall.csv
        csv/recording-id.run-0.static.tall.csv
        recording-id.run-0.metadata.json
```

Default exports replace the two CSVs and update their metadata. Retained exports
refuse overwriting existing files or mixing a different source revision into the
same retained set. No new processing run is created. Empty datasets/static views
produce headers, so a previous default table cannot remain silently stale.

Dynamic fields exactly match Parquet, in its saved row order:

```text
timestamp_s,sensor_group,frame_number,source,reference_frame,channel,name,component,value,units,run_id
```

Static fields omit timestamp/frame number. Static measurements include authored
static channels and views of the frozen scale fit. CSV uses UTF-8 with BOM, normal
quoting, round-trip float64 precision, and empty fields for nulls. Text labels are
literal recorded strings; import identity columns as text in spreadsheet software.
Large tall files can exceed Excel's row limit; no rows are truncated.

Metadata contains the exact embedded recording descriptor, static definitions,
source SHA-256/revision, selected run per artifact, file hashes, row counts, column
names and CSV conventions. The recording descriptor supplies scientific names,
units, coordinate references and processing provenance. Reading with
`verified_manifest(path)` checks pending publication and artifact hashes first.

An export lock serializes writers. Each export stages its own files; cancellation
or writer failure before publication preserves existing exports and removes that
staging directory. Publication replaces files individually and metadata last. An
interruption leaves `.publication.json` and staging files so consumers can detect
an incomplete set. Finish that exact publication before exporting again:

```powershell
python -B -m freemocap.tools.export_tall_csv 'C:/data/recording-id' --recover
python -B -m freemocap.tools.export_tall_csv 'C:/data/recording-id' --recover --keep --run-id 0
```

Recovery verifies hashes and preserves conflicts for inspection. Do not delete
the journal or manually edit metadata to declare an incomplete export successful.
The backend returns paths and source identity through `TallCsvResult`; failures
preserve numerical processing results but fail overall requested-output completion.
The recovery commands above also recover wide CSV journals in the same export folder.

Validation uses focused publication/format tests and
`freemocap/tests/reference_recordings/test_tall_csv_acceptance.py` and
`test_wide_csv_acceptance.py`. Set
`FREEMOCAP_PROVENANCE_PREPARED_ROOT` to the existing production dataset workflow's
verified prepared root. Acceptance copies each Parquet, exports it, compares every
dynamic scalar and static value, and verifies unchanged source hashes. It does not
re-run detection just to export. Re-run the producer workflow when changing
upstream processing; see [reference acceptance](../../../tests/reference_recordings/README.md).

### Quality components

2D overlays export the saved `visibility` component as `confidence`, in CSV
headers and the component labels for NPY/NPZ. Its saved values and dimensionless
units are unchanged. `source_components` records the original Parquet labels.
This is the detector score, not a calibrated probability or spatial error.
Reprojection-error aggregation and landmark-position residuals remain separate
follow-up work; neither is currently appended to 3D export arrays.

## Student guides and Notebook Explorer

Scientific exports create static `README.md` tutorials in the export directory
and selected `csv/` and `npy/` folders. They explain provenance, coordinates,
array axes, missing values, metadata, and loading/plotting with Matplotlib.
Existing READMEs are preserved, including student annotations. Tutorials are
published with the export transaction but are not scientific data artifacts.

The optional `<recording>.explorer.ipynb` recreates the V1 notebook workflow
for V2 Parquet. It uses the selected run and data products, with Pandas tables,
ordered NumPy arrays and a Matplotlib coordinate plot. It requires no CSV/NPY
export and does not rerun processing. Notebook generation requires no Jupyter
or Pandas installation; execution in an analysis environment requires Python
3.11+, Jupyter (or VS Code notebooks), pandas, pyarrow, numpy and matplotlib.
There are no automatic installation cells.

The notebook uses a relative Parquet path and checks its SHA-256 before reading.
Keep the recording layout intact; retained notebooks do not copy or archive
Parquet. Replaced source data produces an explicit error rather than silently
plotting a newer run. Save edited notebooks with another filename before
regenerating the exporter-owned file. Like other managed exports, externally
modified notebook artifacts are detected by manifest verification.

Historical reference: local tag `v1.8.2`,
`freemocap/core_processes/export_data/generate_jupyter_notebook/`, plus
`ipython_jupyter_notebooks/export_freemocap_npy_as_pandas_data_frame_csv.ipynb`.


### Previewing an unprocessed recording

The scientific and tall-CSV preview GET endpoints return HTTP 204 when the
recording folder exists but has no saved Parquet result. Both UI panels show
"No saved result yet" and keep saved-result export disabled; after-processing
export settings remain available. Finishing processing or reloading scientific
results refreshes the preview. Invalid folders, unreadable/corrupt results and
explicit export requests without Parquet remain errors.
