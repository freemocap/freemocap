"""Opt-in real-recording checks of all contiguous processing stage ranges.

Uses the reference-dataset worker and application pipeline manager. Never part of
ordinary pytest collection; run explicitly with python -m ...stage_matrix.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
from time import perf_counter

from .catalog import TEST_DATA, synchronized_video_directory
from .inspection import inspect_recording
from .preparation import execute_worker, file_digest, software_identity
from .storage import write_json
from .workflow import STARTS

STAGE_LABELS = dict(observations='2D tracking', triangulation='3D triangulation + alignment',
                    filtering='Gap filling + filtering', scale_fit='Skeleton scale fitting',
                    reconstruction='Skeleton reconstruction')

def stage_ranges():
    return [(start, stop) for index, start in enumerate(STARTS) for stop in STARTS[index:]]


def validate_stage_output(recording: Path, *, stop: str, expected_frames: int) -> dict:
    """Validate full saved sample grids and exact completed-stage coverage."""
    import pyarrow.parquet as pq
    from freemocap.core.pipeline.posthoc.saved_stage_processing import inspect_saved_stages
    from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata, recording_batches
    from freemocap.core.recording.sample_encoding.arrow_schema import SampleValidator

    path = recording / f'{recording.name}_data.parquet'
    metadata = read_metadata(path=path)
    if metadata.recording_id != recording.name:
        raise ValueError('Saved recording identity changed')
    run = metadata.runs[metadata.selected_run_id]
    if not run.sensor_groups or any(g.sample_count != expected_frames for g in run.sensor_groups.values()):
        raise ValueError('Saved frame coverage differs from the reference recording')
    validator = SampleValidator(metadata=metadata)
    rows = 0
    with pq.ParquetFile(path) as parquet:
        for batch in recording_batches(parquet):
            validator.accept(batch=batch.replace_schema_metadata(None))
            rows += batch.num_rows
    validator.finish()
    inventory = inspect_saved_stages(str(recording))
    groups = next(r for r in inventory['runs'] if r['run_id'] == metadata.selected_run_id)['groups']
    expected = {stage: index <= STARTS.index(stop) for index, stage in enumerate(STARTS)}
    if not groups or any(g['stages'] != expected for g in groups):
        raise ValueError(f'Wrong saved stage coverage: expected {expected}, got {groups}')
    if stop != 'observations':
        alignments = [r['alignment']['outcome'] for r in run.reference_frames.values() if r.get('alignment')]
        if not alignments or any(a not in ('foot_support', 'body_reference', 'preserved_reference') for a in alignments):
            raise ValueError(f'Requested coordinate alignment did not succeed: {alignments}')
    if stop in ('scale_fit', 'reconstruction'):
        from freemocap.core.pipeline.dataflow.saved_spatial_source import load_saved_spatial_source, load_saved_model_fits
        from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
        source = load_saved_spatial_source(path=recording, config=PosthocMocapPipelineConfig(start_stage='reconstruction'))
        load_saved_model_fits(source, source.numerical)
    if stop == 'reconstruction':
        from .validation import validate_outputs
        validate_outputs(recording, expected_frames=expected_frames, require_alignment=True,
                         require_provenance_stages=tuple(STARTS))
    from .inspection import inspect_video
    videos = sorted((recording / 'annotated_videos').glob('*.mp4'))
    if len(videos) != 3 or any(inspect_video(v).decoded_frames != expected_frames for v in videos):
        raise ValueError('Expected three complete annotated videos')
    return dict(rows=rows, frames=expected_frames, stages=expected, annotated_videos=3,
                parquet_sha256=file_digest(path))


def compare_reference_frame(expected: dict, actual: dict, *, tracking_only: bool) -> None:
    # Tracking-only results have not matched cameras to a calibration. Camera
    # identity, image dimensions and every other field must still agree.
    if tracking_only and 'calibration_camera_id' in actual and actual['calibration_camera_id'] is None:
        expected = dict(expected, calibration_camera_id=None)
    if expected != actual:
        raise ValueError(f'Coordinate frame changed: expected {expected}, got {actual}')


def compare_stage_channels(baseline: Path, recording: Path, *, stop: str) -> list[dict]:
    """Compare every produced channel to the full run, retaining sample identity."""
    import numpy as np
    from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
    from freemocap.core.recording.result_processing.saved_reconstruction import read_saved_channel
    from freemocap.system.recording_structure.recording_structure import RecordingStructure

    structures = [RecordingStructure(base_directory=p.parent, recording_name=p.name) for p in (baseline, recording)]
    metadata = [read_metadata(path=s.data_parquet_path) for s in structures]
    runs = [m.runs[m.selected_run_id] for m in metadata]
    key = lambda c: (c.sensor_group, c.source, c.reference_frame, c.kind)
    expected_channels = {key(c): c for c in runs[0].channels}
    allowed = {'BOXES_2D', 'OVERLAY_2D', 'TIMESTAMPS'}
    if stop != 'observations':
        allowed.update(('RAW_KEYPOINTS_3D', 'RECONSTRUCTION_COVERAGE', 'REPROJECTION_ERROR', 'TRIANGULATION_WEIGHTS'))
        if runs[0].camera_geometry != runs[1].camera_geometry:
            raise ValueError('Saved camera assignment or geometry changed')
    if STARTS.index(stop) >= STARTS.index('filtering'):
        allowed.add('KEYPOINTS_3D')
    if stop == 'reconstruction':
        allowed.update(c.kind for c in runs[0].channels)
    if {key(c) for c in runs[1].channels} != {k for k, c in expected_channels.items() if c.kind in allowed}:
        raise ValueError('Missing or unexpected saved channels for the requested finish stage')
    reports = []
    for channel in runs[1].channels:
        expected_channel = expected_channels[key(channel)]
        if channel != expected_channel:
            raise ValueError(f'Channel definition changed: {key(channel)}')
        reference = channel.reference_frame
        if reference is not None:
            compare_reference_frame(runs[0].reference_frames[reference], runs[1].reference_frames[reference],
                                    tracking_only=stop == 'observations')
        values = [read_saved_channel(structure=s, run_id=m.selected_run_id, metadata=m, channel=c)
                  for s, m, c in zip(structures, metadata, (expected_channel, channel), strict=True)]
        first, second = values
        if first.frames != second.frames or first.timestamps_s != second.timestamps_s:
            raise ValueError(f'Frame/timestamp identity changed: {key(channel)}')
        np.testing.assert_allclose(second.values, first.values, atol=1e-6, rtol=1e-8, equal_nan=True,
                                   err_msg=str(key(channel)))
        finite = np.isfinite(first.values)
        reports.append(dict(channel=list(key(channel)), values=int(first.values.size),
            maximum_absolute_error=float(np.max(np.abs(second.values[finite] - first.values[finite]), initial=0))))
    return reports


def validate_executed_operations(task: dict, *, start: str, stop: str) -> None:
    operations = {item['operation_id']: item for item in task['operations']}
    if task['status'] != 'complete' or any(o['status'] != 'complete' for o in operations.values()):
        raise ValueError('Requested work did not complete successfully')
    source = {'observations': 'load_and_track', 'triangulation': 'load_saved_observations'}.get(start)
    if ((source is not None and source not in operations)
            or (start != 'observations' and 'load_and_track' in operations)
            or (STARTS.index(start) > 1 and 'load_saved_observations' in operations)):
        raise ValueError('Wrong source operation: saved-stage restart must not repeat detection')
    selected = STARTS[STARTS.index(start):STARTS.index(stop) + 1]
    required = {'match_and_triangulate': 'triangulation' in selected,
                'align_reference': 'triangulation' in selected,
                'fit_model_dimensions': 'scale_fit' in selected,
                'reconstruct_skeletons': 'reconstruction' in selected}
    for operation, needed in required.items():
        if (operation in operations) != needed:
            raise ValueError(f'Unexpected execution of {operation}: expected present={needed}')


def render_report(report: dict) -> str:
    lines = ['STAGED PIPELINE REFERENCE TEST', '=' * 72,
             'Test data only; 222 motion-capture frames, three videos.',
             'Total times include copying, worker startup, processing, validation and shutdown.',
             'PASS requires saved sample validation and numerical parity with the full run.',
             'Rejected ranges and execution/validation errors are failures, never passes.', '']
    for row in report['ranges']:
        seconds = row.get('elapsed_s', 0)
        rate = f'{seconds / TEST_DATA.expected_frame_count * 1000:.2f} ms/mocap frame' if row['status'] == 'passed' else 'no successful throughput'
        lines.append(f"{STAGE_LABELS[row['start']]:28} -> {STAGE_LABELS[row['stop']]:28} {row['status']:8} {seconds:8.2f}s  {rate}")
        if row.get('application_timing'):
            timing = row['application_timing']
            lines.append(f"  Application: {timing['elapsed_seconds']:.2f}s; {timing['elapsed_seconds'] / TEST_DATA.expected_frame_count * 1000:.2f} ms/mocap frame (222 saved frames)")
        if row.get('error'):
            lines.append('  ' + row['error'])
    lines.append(f"\nPassed: {sum(r['status'] == 'passed' for r in report['ranges'])}/15")
    return '\n'.join(lines) + '\n'


def run_matrix(*, recordings_root: Path, calibration: Path, output: Path, timeout: float = 600.0) -> dict:
    roots = [p.expanduser().resolve() for p in (recordings_root, output)]
    recordings_root, output = roots
    if any(a.is_relative_to(b) for a, b in (roots, roots[::-1])):
        raise ValueError('Matrix output must be separate from source recordings')
    if output.exists():
        raise ValueError('Use a new output directory; previous reports are preserved')
    calibration = calibration.expanduser().resolve(strict=True)
    source = inspect_recording(TEST_DATA, recordings_root=recordings_root)
    if os.name == 'nt':
        for video in source['videos']:
            temporary = output / '1-5' / TEST_DATA.name / 'annotated_videos' / f".{video['filename']}.{'0' * 36}.partial.mp4"
            if len(str(temporary)) >= 260:
                raise ValueError('Video output path exceeds Windows limits; use a shorter --output')
    raw = recordings_root / TEST_DATA.name
    calibration_hash = file_digest(calibration)
    report = dict(dataset='test_data', implementation='graph', source=source,
                  software=software_identity(), calibration_sha256=calibration_hash,
                  ranges=[dict(start=a, stop=b, status='pending') for a, b in stage_ranges()])
    output.mkdir(parents=True)
    baseline = None
    completed = {}
    # A fresh full run provides the comparison, then fresh partial runs provide
    # minimal prerequisites for restarts. Each case has its own application process.
    ordered = sorted(report['ranges'], key=lambda r: (r['start'], r['stop']) == ('observations', 'reconstruction'), reverse=True)
    for row in ordered:
        start, stop = row['start'], row['stop']
        case = output / f'{STARTS.index(start)+1}-{STARTS.index(stop)+1}'
        recording = case / TEST_DATA.name
        case.mkdir()
        started = perf_counter()
        try:
            if start == 'observations':
                videos = recording / 'synchronized_videos'
                videos.mkdir(parents=True)
                for video in source['videos']:
                    destination = videos / video['filename']
                    shutil.copy2(synchronized_video_directory(raw) / video['filename'], destination)
                    if file_digest(destination) != video['sha256']:
                        raise ValueError('Video changed during copy')
                write_json(recording / 'charuco_board_info.json', source['board_metadata'])
            else:
                prerequisite = STARTS[STARTS.index(start)-1]
                seed = completed.get(('observations', prerequisite), baseline)
                if seed is None:
                    raise ValueError('No successful prerequisite run; cannot exercise restart')
                shutil.copytree(seed, recording)
            shutil.copy2(calibration, recording / f'{TEST_DATA.name}_camera_calibration.toml')
            request = dict(recording=str(recording), implementation='graph', stage_matrix=True,
                start_stage=start, stop_stage=stop, calibration_mode='existing', output_profile='numerical',
                alignment='auto', filtering_enabled=True, filter_cutoff=1.0, frames=TEST_DATA.expected_frame_count,
                fps=source['videos'][0]['nominal_fps'], timeout=timeout, run_id=0)
            write_json(case / 'request.json', request)
            execute_worker([sys.executable, '-B', '-m', 'freemocap.tools.datasets.preparation', '--worker', str(case / 'request.json')],
                environment=dict(os.environ, FREEMOCAP_BASE_FOLDER=str(case / 'app-data'), PYTHONUTF8='1'),
                log_path=case / 'processing.log', timeout=timeout + 120)
            result = json.loads((case / 'result.json').read_text())
            row['validation'] = result['validation']
            row['config'] = result['mocap_config']
            row['operations'] = result['mocap_task']['operations']
            row['application_timing'] = result['mocap_task']['timing']
            validate_executed_operations(result['mocap_task'], start=start, stop=stop)
            reference = recording if (start, stop) == ('observations', 'reconstruction') else baseline
            if reference is None:
                raise ValueError('Full baseline failed; numerical parity cannot be certified')
            row['channels'] = compare_stage_channels(reference, recording, stop=stop)
            if stop == 'reconstruction':
                from .full_recording_comparison import compare_saved_channels
                from freemocap.system.recording_structure.recording_structure import RecordingStructure
                compare_saved_channels(*(RecordingStructure(base_directory=p.parent, recording_name=p.name)
                                         for p in (reference, recording)))
            if (start, stop) == ('observations', 'reconstruction'):
                baseline = recording
            completed[start, stop] = recording
            row['status'] = 'passed'
        except Exception as error:
            row.update(status='failed', error=f'{type(error).__name__}: {error}')
            log = case / 'processing.log'
            if log.exists():
                row['log_tail'] = log.read_text(encoding='utf-8', errors='replace').splitlines()[-35:]
                reasons = [line for line in row['log_tail'] if line.startswith(('ValueError:', 'RuntimeError:', 'pydantic_core.'))]
                if reasons:
                    row['error'] = reasons[-1]
        row['elapsed_s'] = perf_counter() - started
        row['log'] = str(case / 'processing.log')
        write_json(output / 'matrix.json', report)
        (output / 'report.txt').write_text(render_report(report), encoding='utf-8')
        print(f"{start} -> {stop}: {row['status']} ({row['elapsed_s']:.2f}s)", flush=True)
    if file_digest(calibration) != calibration_hash or inspect_recording(TEST_DATA, recordings_root=recordings_root) != source:
        raise ValueError('Source recording or calibration changed during the matrix')
    print(render_report(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recordings-root', type=Path, default=Path.home() / 'freemocap_data/recordings')
    parser.add_argument('--calibration', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='New short output path, outside source recordings')
    parser.add_argument('--timeout', type=float, default=600.0)
    report = run_matrix(**vars(parser.parse_args()))
    raise SystemExit(0 if all(r['status'] == 'passed' for r in report['ranges']) else 1)


if __name__ == '__main__':
    main()
