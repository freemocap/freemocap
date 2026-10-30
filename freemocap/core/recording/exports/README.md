# Scientific exports

In **Open Mocap Processing > Exports**, select data independently of formats.
**3D landmarks** is the default data selection; all export formats are optional.
Wide CSV, NPY, NPZ and Notebook Explorer reuse saved processing results without
rerunning detection, geometry or filtering. Model predictions are not independent
empirical measurements of every landmark.

## Recording runs and output paths

Normal processing overwrites the selected run, with run 0 as the default. Creating
a new run is an explicit processing choice owned by `RunSaveSession`; exporting
never allocates another run. Run 0 normally publishes under `exports/`. Nonzero
runs and explicit `keep=True` exports use `exports/run-<id>/` and run-qualified
filenames. Existing kept formats are not overwritten; adding formats requires the
same source revision.

```text
recording/
    recording_data.parquet
    recording_recording_info.json
    recording.explorer.ipynb                 # optional
    exports/
        csv/recording.3d_landmarks--standard_human.csv
        npy/dataset.json
        npy/channel_000000_values.npy
        npy/channel_000000_companion_000000.npy
        npy/timing_000000_sample_ids.npy
        npy/timing_000000_timestamps_s.npy
        recording.npz                       # optional
        recording_recording_info.json
        run-1/                              # an explicitly selected nonzero run
            npy/dataset.json
            recording.run-1.npz
            recording.run-1_recording_info.json
```

Normal NPY replacement uses the same run-local `npy/` directory. The recovery
journal removes only obsolete, previously managed NPY members whose hashes still
match. Edited or unrelated files are preserved and stop replacement when they
would make the dataset inventory ambiguous. Unselected formats remain unchanged.
CSV publication replaces selected table paths and updates its inventory; older
unselected CSV files may remain on disk. The inventory identifies active outputs.

## Scientific arrays and display tables

Parquet is the primary durable recording. SkellyForge owns the reusable
`RecordingDataset`, `TimeSeries`, `DataTensor`, `SampleTiming` and NumPy format.
See [the implemented NumPy contract](../../../../../skellyforge/skellyforge/core/data_tensors/NUMPY_FORMAT.md)
for the complete `skellyforge.numpy_dataset` version-1 schema.

NPY and NPZ preserve the selected tensor representation: dtype, logical values,
axes and their authored identities, component units, coordinate references,
provenance, explicit companions and definition documents. Component counts come
from layouts. A time series identifies its sample axis and its own timing entry;
channels may have different sample counts, IDs and timestamps. Static fits have
no fake frame axis. Declared independent clocks remain separate. The saved Core
adapter scopes clock IDs to recorded groups/runs without inventing hardware clock
identities or changing timestamps.

Selecting `SEGMENT_POSES` writes native `SEGMENT_ORIGINS` and `ROTATIONS_WORLD`
tensors to NumPy. NumPy keeps the saved `visibility` component label. CSV and
notebook display projections retain canonical spatial component order, the
`confidence` alias for visibility, and combined origins/world quaternions with
named `qw,qx,qy,qz` columns. These projections do not redefine runtime storage.

`entry_presence` from saved Parquet means a component row exists, including a
recorded null. Values may therefore be NaN while presence is true. It is not a
quality score or independent scientific-validity declaration. Explicit runtime
`value_validity`, confidence and evidence arrays are preserved when supplied;
the saved schema's absent quality information is not fabricated. Selected model
fits include static scales/lengths, measured/voting support, model definitions and
input signatures. Solver/hydration execution statuses and caches are excluded.

CSV uses UTF-8 with BOM and round-trip float64 precision. Dynamic tables begin
with `frame_number,timestamp_s`; static tables omit those columns. An empty field
means an absent entry, while `NaN` means a recorded null. Quoting handles names
containing commas, periods and quotes. Large tables split at 500,000 rows or 1,024
value columns; the inventory records their slices. No export interpolates,
resamples, pads coordinates or changes units.

## Dataset metadata and standalone loading

NPY consists of `dataset.json` and flat numeric `.npy` files, plus an optional
README. NPZ contains the same manifest and arrays as ZIP members. Neither uses
object arrays or pickle. Follow each channel's `values_file`, declared axes and
`timing_ref`; follow companion names and layouts independently. An NPZ dataset
contains `dataset.json`, not the former `recording_info.json`/shared-timestamp
format. Older unversioned NumPy exports are not accepted by the new loader.

The outer export inventory records artifact hashes, run and source revision.
Its snapshots contain separate `numpy_datasets['npy']` and `['npz']` descriptors,
including each format's path, selected contexts and value origin. A retained
unselected format can refer to an older selection or source hash. Its descriptor
is retained only while artifacts of that format/source remain. Embedded dataset
metadata is authoritative for its own contents.

```python
from pathlib import Path
from skellyforge.core.data_tensors import RecordingDataset

dataset = RecordingDataset.load_numpy(Path('exports/npy'))  # or an NPZ file
series = dataset.time_series[0]
values = series.data_tensor.data_values
sample_ids = series.sample_timing.sample_ids
timestamps_s = series.sample_timing.timestamps_s
# Standalone saves require a fresh destination.
dataset.save_numpy(Path('analysis_copy.npz'), format='npz')
```

The loader returns owned immutable objects with no open file lifetime. Standalone
save/load needs neither FreeMoCap nor the original Parquet. Plain NumPy users can
read `dataset.json` with `json` and arrays with `numpy.load(..., allow_pickle=False)`;
NPZ members are readable through `zipfile.ZipFile.open`. Generated guides contain
executable examples. Plain NPY consumers may explicitly choose memory mapping.

## Core export API and bounded memory

`export_scientific(structure=..., request=..., runtime_dataset=None)` uses the
existing selected-run, revision, cancellation and recoverable publication path.
Without runtime data, Core reads selected Parquet channels and admits one borrowed
scientific tensor at a time. If NPY and NPZ are both selected, both writers consume
that tensor before its reader storage is released. NumPy-only export does not
construct CSV projections or concatenate pose components.

The optional `runtime_dataset` is an already selected immutable Forge
`RecordingDataset`. Core checks recording/run identity, selected channels,
source identities, declared axes and units, then writes its NumPy arrays without
reading numerical Parquet rows. Metadata and source-hash reads still occur.
Runtime datasets support NPY/NPZ only; CSV/notebook must be exported separately
from saved results to avoid mixing potentially different values. The inventory
labels this origin explicitly: runtime values are round-trip validated, not
claimed numerically equal to Parquet. Core does not retain full recordings merely
to make runtime export possible.

Forge verifies each array immediately after writing, while the source is still
available, including dtype, shape, values, NaN positions and signed zeros. Its
writer retains metadata/timing rather than channel values. CSV remains a bounded
batch conversion. Timings report `npy_write_and_verify` and `npz_write_and_verify`
together, alongside array assembly and CSV write/validation. Publication failures
leave a recoverable journal; cancellation before publication preserves old output.

## Tall CSV diagnostics

In **Open Mocap Processing > Exports**, **Save tall CSV after processing** is
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

Static fields omit timestamp/frame number. Static fitted values include authored
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

2D CSV/notebook projections label the saved `visibility` score as `confidence`.
NumPy keeps the authored `visibility` label and its values/units. The detector
score is not a calibrated probability or spatial error. Reprojection errors and
landmark residuals are not appended as invented components.

## Student guides and Notebook Explorer

Scientific exports create static `README.md` tutorials in the export directory
and selected `csv/` and `npy/` folders. They explain provenance, coordinates,
array axes, missing values, metadata, and loading/plotting with Matplotlib.
Normal exports refresh only byte-identical recognized older generated guides.
Annotated or unknown READMEs are preserved. Kept exports preserve every existing
guide; missing guides can still be created. Tutorials are
published with the export transaction but are not scientific data artifacts.

The optional `<recording>.explorer.ipynb` is saved in the recording folder beside
the Parquet file, rather than under `exports/`. Kept exports and nonzero runs use
`<recording>.run-<id>.explorer.ipynb` in that same recording folder.
It recreates the V1 notebook workflow
for V2 Parquet. It uses the selected run and data products, with Polars column selection,
ordered NumPy arrays, interactive coordinate plots, and playable 3D points. It requires no CSV/NPY
export and does not rerun processing. Notebook generation requires no Jupyter
installation; execution in an analysis environment requires Python
3.11+, Jupyter (or VS Code notebooks), polars>=2,<3, numpy and plotly>=6,<7.
Polars and Plotly are direct core dependencies, so the notebook execution test
runs in the normal development environment. Numerical assembly uses NumPy arrays
in declared frame/name/component order, including a separate row-presence tensor.
Use Polars for tabular queries and reductions; retain NumPy tensors and Arrow
batches for their existing numerical and serialization roles.
Parquet filters and column selection use a lazy scan [@polarsParquetScan]; CSV
examples project selected columns and preserve null versus NaN [@polarsCsvScan].
There are no automatic installation cells.

The notebook uses a relative Parquet path and checks its SHA-256 before reading.
Manifest version 4 marks root notebooks with `location: recording`; other artifacts
remain relative to their export folder. The publication journal records the same
location so interrupted exports can recover. Existing notebooks under `exports/`
remain in place; requesting a new notebook publishes the new copy at the root.
Keep the recording layout intact; retained notebooks do not copy or archive
Parquet. Replaced source data produces an explicit error rather than silently
plotting a newer run. Save edited notebooks with another filename before
regenerating the exporter-owned file. Like other managed exports, externally
modified notebook artifacts are detected by manifest verification.

The walkthrough follows the generated v1.8.2 template: libraries, editable
variables, joint selection, coordinate plots, and animated 3D points
[@freemocapNotebookV182]. The export snapshot is stored in notebook metadata
instead of a large literal in the first code cell. Channel names, components,
units, frame numbers, and timestamps come from the saved run. The V1 center-of-mass
comparison is omitted because this export does not provide a center-of-mass channel.
The 3D view shows landmarks, keypoints, or segment origins according to the selected
channel; it does not interpret quaternion components as positions. For 2D channels,
the notebook plots XY and skips the 3D view. Playback uses the median saved interval;
the slider preserves exact frame IDs and elapsed timestamps.


### Previewing an unprocessed recording

The scientific and tall-CSV preview GET endpoints return HTTP 204 when the
recording folder exists but has no saved Parquet result. Both UI panels show
"No saved result yet" and keep saved-result export disabled; after-processing
export settings remain available. Finishing processing or reloading scientific
results refreshes the preview. Invalid folders, unreadable/corrupt results and
explicit export requests without Parquet remain errors.
