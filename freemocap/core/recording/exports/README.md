# Tall CSV exports

In **Open Mocap Processing → Exports**, **Save tall CSV after processing** is
checked by default. Uncheck it to skip CSV output. It applies to full processing
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
    recording-id.tall.csv
    recording-id.static.tall.csv
    recording-id.metadata.json
    run-0/                           # only with --keep
        recording-id.run-0.tall.csv
        recording-id.run-0.static.tall.csv
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
raise separately from mocap processing. Automatic export outcomes remain visible
on the completed processing card; a CSV failure leaves processing successful and
can be retried from Exports. Wide CSV and NPZ remain pending.

Validation uses focused publication/format tests and
`freemocap/tests/reference_recordings/test_tall_csv_acceptance.py`. Set
`FREEMOCAP_PROVENANCE_PREPARED_ROOT` to the existing production dataset workflow's
verified prepared root. Acceptance copies each Parquet, exports it, compares every
dynamic scalar and static value, and verifies unchanged source hashes. It does not
re-run detection just to export. Re-run the producer workflow when changing
upstream processing; see [reference acceptance](../../../tests/reference_recordings/README.md).
