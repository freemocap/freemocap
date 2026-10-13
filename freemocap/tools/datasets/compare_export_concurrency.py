"""Compare one versus two export workers using isolated copies and prepared Blender.

Run with python -m freemocap.tools.datasets.compare_export_concurrency --help.
This never installs a Blender package and never changes the source recording.
"""
import argparse
import importlib
import hashlib
import zipfile
import json
from pathlib import Path
import shutil
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import patch

from freemocap.core.blender.preparation import PreparedBlender, ready_package
from freemocap.core.blender.runtime import inspect_blender
from freemocap.core.pipeline.performance_report import PerformanceReport
from freemocap.core.pipeline.posthoc.export_completion import complete_recording_exports
from freemocap.core.recording.exports.publication import digest
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parquet', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New ignored benchmark directory')
    parser.add_argument('--blender', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True, help='Existing prepared Blender profile; never installed')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Use a fresh output directory to preserve prior measurements')
    report = inspect_blender(args.blender, profile=args.profile)
    package = ready_package(report)
    if package is None:
        raise RuntimeError('Existing Blender profile is not ready; benchmark refuses to install packages')
    prepared = PreparedBlender(package, args.profile.resolve())
    source_hash = digest(args.parquet)
    with recording_view(args.parquet) as view:
        run_id = view.metadata.selected_run_id
    args.output.mkdir(parents=True)
    measurements = []
    for workers in (1, 2):
        folder = args.output / f'workers-{workers}' / args.parquet.stem.removesuffix('_data')
        folder.mkdir(parents=True)
        parquet = folder / f'{folder.name}_data.parquet'
        shutil.copy2(args.parquet, parquet)
        events = []
        started = perf_counter()
        def progress(*values):
            events.append(dict(elapsed_s=perf_counter()-started, values=values))
        performance = PerformanceReport()
        config = PosthocMocapPipelineConfig(baseRunId=run_id, exportTallCsv=False,
            exportToBlender=True, autoOpenBlendFile=False, blenderExePath=str(args.blender),
            blenderImportRoute='parquet_segments', blenderPackage=package,
            blenderExportConfig=dict(formats=['fbx', 'bvh']),
            scientificExports=dict(formats=['wide_csv', 'npy', 'npz'],
                data=['LANDMARKS_3D', 'KEYPOINTS_3D', 'RAW_KEYPOINTS_3D', 'OVERLAY_2D', 'SEGMENT_POSES']))
        assert set(config.blender_export.formats) == {'fbx', 'bvh'}
        request = SimpleNamespace(recording=SimpleNamespace(full_recording_path=folder), config=config,
            ipc=SimpleNamespace(should_continue=True), performance=performance,
            report=progress, report_export=progress)
        module = importlib.import_module('freemocap.core.blender.export_to_blender')
        # Both trials use the same preflight-verified package. No installation or
        # profile setup occurs inside the measured export destination work.
        with patch.object(module, 'prepare_blender', return_value=prepared):
            complete_recording_exports(request, worker_count=workers)
        elapsed = perf_counter()-started
        assert digest(parquet) == source_hash, 'Benchmark changed its saved source'
        files = {str(path.relative_to(folder)): dict(bytes=path.stat().st_size, sha256=digest(path))
            for path in folder.rglob('*') if path.is_file() and path != parquet}
        for suffix in ('.blend', '.fbx', '.bvh'):
            assert any(name.endswith(suffix) and info['bytes'] > 0 for name, info in files.items()), suffix
        npz_members = {}
        for archive_path in folder.rglob('*.npz'):
            with zipfile.ZipFile(archive_path) as archive:
                npz_members[str(archive_path.relative_to(folder))] = {
                    name: hashlib.sha256(archive.read(name)).hexdigest() for name in archive.namelist() if name.endswith('.npy')}
        measurement = dict(workers=workers, wall_s=elapsed, npz_members=npz_members, timings=performance.snapshot(),
            events=events, files=files)
        measurements.append(measurement)
        (args.output / f'workers-{workers}.json').write_text(json.dumps(measurement, indent=2), encoding='utf-8')
        print(f'{workers} export workers: {elapsed:.3f}s', flush=True)
    # CSV and NPY bytes must agree. ZIP containers, manifests and Blender files
    # include timestamps/output paths, so byte parity is not claimed for those.
    left, right = (measurement['files'] for measurement in measurements)
    comparable = {name for name in left if name.endswith(('.csv', '.npy'))}
    assert comparable
    assert comparable == {name for name in right if name.endswith(('.csv', '.npy'))}
    mismatches = [name for name in sorted(comparable) if left[name]['sha256'] != right[name]['sha256']]
    if mismatches:
        raise AssertionError(f'Scientific output mismatch: {mismatches}')
    assert measurements[0]['npz_members'] == measurements[1]['npz_members'], 'NPZ arrays differ'
    result = dict(source=str(args.parquet.resolve()), source_sha256=source_hash,
        sequential_s=measurements[0]['wall_s'], concurrent_s=measurements[1]['wall_s'],
        equal_csv_npy_files=len(comparable), measurements=measurements)
    (args.output / 'comparison.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    assert digest(args.parquet) == source_hash, 'Source recording changed during benchmark'
    print(json.dumps({key: value for key, value in result.items() if key != 'measurements'}, indent=2))


if __name__ == '__main__':
    main()
