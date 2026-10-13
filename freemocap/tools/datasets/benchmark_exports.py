"""Measure scientific exports from an untouched saved recording.

Example (output must be a new directory, outside the source recording)::

    python -B -m freemocap.tools.datasets.benchmark_exports \
        --recording PATH_TO_RECORDING --output .test-artifacts/export-benchmark

Repeat on the same saved Parquet before/after a change; pass the earlier exports
folder with --compare-exports to check CSV/NPY bytes and NPZ measurement members.
Recording copying and parity checks are excluded from the reported export time.
"""
import argparse
import hashlib
import json
import os
import platform

import numpy as np
import pyarrow as pa
from pathlib import Path
import shutil
from time import perf_counter
from zipfile import ZipFile

from freemocap.core.recording.exports.arrays import scientific_channels
from freemocap.core.recording.exports.publication import digest, verified_manifest
from freemocap.core.recording.exports.requests import ScientificExportRequest
from freemocap.core.recording.exports.wide_csv import export_scientific
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.system.recording_structure.recording_structure import RecordingStructure


def compare_exports(actual: Path, expected: Path, recording_name: str) -> dict:
    manifests = [verified_manifest(directory / f'{recording_name}_recording_info.json')
                 for directory in (actual, expected)]
    if set(manifests[0].artifacts) != set(manifests[1].artifacts):
        raise AssertionError('Export artifact inventory differs')
    checked_files, checked_members = 0, 0
    for name in manifests[0].artifacts:
        if name.endswith('.npz'):
            with ZipFile(actual / name) as left, ZipFile(expected / name) as right:
                if set(left.namelist()) != set(right.namelist()):
                    raise AssertionError('NPZ member inventory differs')
                for member in left.namelist():
                    if member == 'recording_info.json':
                        continue  # Export date and source revision are intentionally different.
                    if hashlib.sha256(left.read(member)).digest() != hashlib.sha256(right.read(member)).digest():
                        raise AssertionError(f'NPZ measurement changed: {member}')
                    checked_members += 1
        else:
            if digest(actual / name) != digest(expected / name):
                raise AssertionError(f'Export bytes changed: {name}')
            checked_files += 1
    return dict(exact_file_payloads=checked_files, exact_npz_measurement_members=checked_members)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recording', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--compare-exports', type=Path)
    args = parser.parse_args()
    recording = args.recording.resolve()
    output = args.output.resolve()
    if output.is_relative_to(recording):
        raise ValueError('Benchmark output must be outside the original recording')
    source = recording / f'{recording.name}_data.parquet'
    source_hash = digest(source)
    output.mkdir(parents=True, exist_ok=False)
    structure = RecordingStructure(base_directory=output, recording_name=recording.name)
    structure.full_path.mkdir()
    shutil.copy2(source, structure.data_parquet_path)
    with recording_view(structure.data_parquet_path) as view:
        run_id = view.metadata.selected_run_id
        data = tuple(dict.fromkeys(context.channel for context, _, _ in scientific_channels(view.metadata.runs[run_id])))
        rows = view.parquet.metadata.num_rows
    started = perf_counter()
    result = export_scientific(structure=structure,
        request=ScientificExportRequest(formats=('wide_csv', 'npy', 'npz'), data=data))
    elapsed = perf_counter() - started
    if digest(source) != source_hash:
        raise AssertionError('Source recording changed during benchmark')
    report = dict(source=str(source), source_sha256=source_hash, source_rows=rows,
        environment=dict(python=platform.python_version(), numpy=np.__version__, pyarrow=pa.__version__,
            processor=platform.processor(), logical_cpu_count=os.cpu_count(),
            arrow_cpu_pool_capacity=pa.cpu_count(), arrow_io_pool_capacity=pa.io_thread_count()),
        total_export_s=elapsed, component_timings_s=result.timings_s,
        artifact_count=len(result.files), artifact_bytes=sum(p.stat().st_size for p in result.files),
        exports_directory=str(structure.exports_dir))
    if args.compare_exports:
        report['parity'] = compare_exports(structure.exports_dir, args.compare_exports, recording.name)
    (output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
