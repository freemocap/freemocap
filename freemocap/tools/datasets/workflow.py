"""Explicit reference-data operations with saved results and separate calibration."""

import json
import logging
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

from filelock import FileLock

from .catalog import TEST_DATA, SAMPLE_DATA, acquire_recording, synchronized_video_directory
from .inspection import inspect_recording
from .preparation import PREPARATION_VERSION, execute_worker, file_digest, software_identity, reuse_recording
from .storage import recover, save_current, write_json
from .validation import validate_outputs

DATASETS = {'test_data': TEST_DATA, 'sample_data': SAMPLE_DATA}
STARTS = ('observations', 'triangulation', 'filtering', 'scale_fit', 'reconstruction', 'skeleton_fit')
logger = logging.getLogger(__name__)


def checked_ready(root: Path, *, calibration_only: bool = False) -> dict | None:
    if (root / 'replacement.json').exists():
        raise ValueError(f'Interrupted save in {root}; run datasets recover for this dataset')
    marker = root / 'ready.json'
    if not marker.exists():
        if (root / 'current').exists():
            raise ValueError(f'Current folder has no ready.json: {root}')
        return None
    ready = json.loads(marker.read_text(encoding='utf-8'))
    recording = Path(ready['recording']).resolve()
    if not recording.is_relative_to((root / 'current').resolve()):
        raise ValueError(f'Prepared recording escapes current directory: {recording}')
    if not calibration_only:
        reuse_recording(root, ready['identity'])
    path = recording / ready['result']['calibration_filename']
    if not path.resolve().is_relative_to(recording) or file_digest(path) != ready['result']['calibration_sha256']:
        raise ValueError(f'Saved calibration no longer matches ready.json: {path}')
    return ready


def selected_calibration(root: Path, raw: Path, choice: str, ready: dict | None) -> Path:
    from freemocap.core.tasks.calibration.shared.calibration_paths import find_recording_calibration
    if choice != 'existing':
        path = Path(choice).expanduser().resolve()
        if not path.is_file():
            raise ValueError(f'Calibration file does not exist: {path}')
        return path
    calibration = checked_ready(root / 'calibration', calibration_only=True)
    if calibration is not None:
        return Path(calibration['recording']) / calibration['result']['calibration_filename']
    if ready is not None:
        return Path(ready['recording']) / ready['result']['calibration_filename']
    path = find_recording_calibration(recording_folder=raw) if raw.exists() else None
    if path is None:
        raise ValueError('No existing dataset calibration. Run calibrate or process with --calibration fresh.')
    return path


def preflight(name: str, *, recordings_root: Path, prepared_root: Path, operation: str = 'process',
              start: str = 'observations', calibration: str | None = None, alignment: str | None = None,
              skeleton_fit: bool = True, run_id: int | None = None, sensor_group: str | None = None,
              timeout: float = 1800.0) -> dict:
    dataset = DATASETS[name]
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('Timeout must be finite and positive')
    if start not in STARTS or operation not in ('process', 'calibrate'):
        raise ValueError('Unsupported operation or starting stage')
    if start == 'skeleton_fit' and not skeleton_fit:
        raise ValueError('--no-skeleton-fit conflicts with --from skeleton_fit')
    later = start not in ('observations', 'triangulation')
    if later and (calibration is not None or alignment is not None):
        raise ValueError('Changing calibration/alignment requires restarting from triangulation or observations')
    raw = recordings_root.expanduser().resolve() / dataset.name
    root = prepared_root.expanduser().resolve() / dataset.name
    source_root = recordings_root.expanduser().resolve()
    output_root = prepared_root.expanduser().resolve()
    if output_root.is_relative_to(source_root) or source_root.is_relative_to(output_root):
        raise ValueError('Prepared output must be separate from source recordings')
    ready = checked_ready(root)
    choice = calibration or ('fresh' if start == 'observations' else 'existing')
    if operation == 'calibrate':
        choice = 'fresh'
    plan = dict(dataset=name, operation=operation, start_stage=start, calibration_mode=choice,
                alignment=alignment or 'auto', skeleton_fit=skeleton_fit, timeout=timeout,
                raw=str(raw), root=str(root), run_id=run_id, sensor_group=sensor_group,
                current=ready['recording'] if ready else None)
    if operation == 'process' and start != 'observations':
        if ready is None:
            raise ValueError('No prepared recording. Run the complete dataset workflow first.')
        from freemocap.core.pipeline.posthoc.saved_stage_processing import inspect_saved_stages, select_group
        from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
        recording = Path(ready['recording'])
        meta = read_metadata(path=recording / f'{dataset.name}_data.parquet')
        selected_run = meta.selected_run_id if run_id is None else run_id
        if selected_run not in meta.runs:
            raise ValueError(f'Run {selected_run} is not present')
        group = select_group(meta.runs[selected_run], sensor_group)
        available = inspect_saved_stages(str(recording))
        entry = next(g for r in available['runs'] if r['run_id'] == selected_run
                     for g in r['groups'] if g['sensor_group'] == group)
        required = {'triangulation': 'observations', 'filtering': 'triangulation',
                    'scale_fit': 'filtering', 'reconstruction': 'scale_fit', 'skeleton_fit': 'reconstruction'}[start]
        if not entry['stages'][required]:
            raise ValueError(f'Missing saved {required}; restart at that stage first')
        plan.update(run_id=selected_run, sensor_group=group)
    elif run_id is not None or sensor_group is not None:
        raise ValueError('Run/group selection applies only to saved-stage processing')
    if choice != 'fresh':
        # Later numerical stages retain the exact calibration associated with their saved inputs.
        path = (Path(ready['recording']) / ready['result']['calibration_filename'] if later and ready
                else selected_calibration(root, raw, choice, ready))
        from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
        loaded = CalibrationResult.load_toml(path)
        if len(loaded.cameras) != 3 or not math.isfinite(loaded.reprojection_error_px):
            raise ValueError('Reference data requires a valid three-camera calibration')
        plan.update(calibration_path=str(path), calibration_sha256=file_digest(path),
                    calibration_aligned=loaded.aligned)
    plan['output'] = str(root / ('calibration/current' if operation == 'calibrate' else 'current') / 'recordings' / dataset.name)
    return plan


def process(name: str, **options) -> Path:
    """Always execute requested work; previous accepted results survive any failure."""
    dataset = DATASETS[name]
    root = options['prepared_root'].expanduser().resolve() / dataset.name
    # Validate root separation and intent before creating any output folders.
    preflight(name, **options)
    root.mkdir(parents=True, exist_ok=True)
    with FileLock(str(root / 'prepare.lock'), timeout=0):
        plan = preflight(name, **options)
        logger.info('Processing plan:\n%s', json.dumps(plan, indent=2))
        ready = checked_ready(root)
        full = plan['start_stage'] == 'observations' or plan['operation'] == 'calibrate'
        if full:
            raw = acquire_recording(dataset, recordings_root=options['recordings_root'])
            source = inspect_recording(dataset, recordings_root=options['recordings_root'])
        else:
            raw = Path(plan['raw'])
            source = ready['identity']['source']
        # Keep native video paths below Windows MAX_PATH (the writer adds a UUID).
        attempt = root / 'attempts' / uuid4().hex[:8]
        candidate = attempt / 'current'
        recording = candidate / 'recordings' / dataset.name
        if os.name == 'nt':
            for video in source['videos']:
                temporary = recording / 'annotated_videos' / f".{video['filename']}.{'0' * 36}.partial.mp4"
                if len(str(temporary)) >= 260:
                    raise ValueError('Video output path exceeds Windows limits; use a shorter --prepared-root')
        attempt.mkdir(parents=True, exist_ok=False)
        if full:
            videos = recording / 'synchronized_videos'
            videos.mkdir(parents=True)
            for video in source['videos']:
                destination = videos / video['filename']
                shutil.copy2(synchronized_video_directory(raw) / video['filename'], destination)
                if file_digest(destination) != video['sha256']:
                    raise ValueError('Source video changed during copying')
            shutil.copy2(raw / 'charuco_board_info.json', recording / 'charuco_board_info.json')
        else:
            shutil.copytree(Path(ready['recording']), recording)
        if 'calibration_path' in plan:
            path = Path(plan['calibration_path'])
            # Remove copied calibration alternatives only inside this newly created candidate.
            for old in recording.glob('*calibration*.toml'):
                old.unlink()
            destination = recording / f'{dataset.name}_camera_calibration.toml'
            shutil.copy2(path, destination)
            if file_digest(destination) != plan['calibration_sha256']:
                raise ValueError('Calibration changed during copying')
        request = dict(plan, recording=str(recording), frames=dataset.expected_frame_count,
                       fps=source['videos'][0]['nominal_fps'], filtering_enabled=name == 'sample_data',
                       validate_workflow=True, run_id=plan['run_id'] or 0)
        request_path = attempt / 'request.json'
        write_json(request_path, request)
        environment = dict(os.environ, FREEMOCAP_BASE_FOLDER=str(attempt / 'app-data'), PYTHONUTF8='1')
        log_path = attempt / 'processing.log'
        logger.info('Working folder: %s; log: %s', attempt, log_path)
        try:
            execute_worker([sys.executable, '-B', '-m', 'freemocap.tools.datasets.preparation', '--worker', str(request_path)],
                           environment=environment, log_path=log_path, timeout=plan['timeout'] * 2 + 120)
        except (OSError, subprocess.SubprocessError) as error:
            raise RuntimeError(f'Processing failed; previous results retained. Log: {log_path}') from error
        result = json.loads((attempt / 'result.json').read_text(encoding='utf-8'))
        target = root / 'calibration' if plan['operation'] == 'calibrate' else root
        target.mkdir(exist_ok=True)
        output = target / 'current' / 'recordings' / dataset.name
        identity = dict(preparation_version=PREPARATION_VERSION, source=source, software=software_identity(),
                        preparer_sha256=file_digest(Path(__file__)))
        saved = dict(identity=identity, recording=str(output), result=result, workflow=plan,
                     log=str(log_path), previous_recording=ready['recording'] if ready else None)
        # Preserve exact executed config in request.json; saved paths identify the final location.
        saved['result']['mocap_config']['calibration_toml_path'] = str(output / result['calibration_filename'])
        shutil.copy2(log_path, candidate / 'processing.log')
        if target != root:
            # Keep candidate inside the calibration root for guarded directory replacement.
            destination = target / 'attempts' / attempt.name / 'current'
            destination.parent.mkdir(parents=True)
            candidate.rename(destination)
            candidate = destination
        save_current(target, candidate, saved)
        logger.info('Saved %s results: %s', name, output)
        return output


def status(name: str, *, recordings_root: Path, prepared_root: Path) -> dict:
    dataset = DATASETS[name]
    root = prepared_root.expanduser().resolve() / dataset.name
    raw = recordings_root.expanduser().resolve() / dataset.name
    report = dict(dataset=name, source=str(raw), source_exists=raw.exists(), prepared_root=str(root))
    for key, target, calibration_only in (('prepared', root, False), ('calibration', root / 'calibration', True)):
        try:
            ready = checked_ready(target, calibration_only=calibration_only)
            software = ready['identity'].get('software', {}) if ready else {}
            report[key] = None if ready is None else dict(recording=ready['recording'], log=ready.get('log'),
                calibration_sha256=ready['result']['calibration_sha256'],
                calibration_aligned=ready['result'].get('calibration', {}).get('aligned'),
                workflow=ready.get('workflow'), software=dict(core_sha256=software.get('core_sha256'),
                    packages={name: value for name, value in software.get('packages', {}).items()
                              if name.lower() in ('skellyforge', 'skellytracker', 'skellycam')}))
            if ready is not None and not calibration_only:
                from freemocap.core.pipeline.posthoc.saved_stage_processing import inspect_saved_stages
                report['saved_stages'] = inspect_saved_stages(ready['recording'])
        except (ValueError, OSError, KeyError) as error:
            report[key] = dict(error=str(error))
    if report.get('prepared') and report.get('calibration'):
        report['separate_calibration_matches_mocap'] = (
            report['prepared'].get('calibration_sha256') == report['calibration'].get('calibration_sha256'))
    return report


def validate(name: str, *, prepared_root: Path) -> dict:
    root = prepared_root.expanduser().resolve() / DATASETS[name].name
    with FileLock(str(root / 'prepare.lock'), timeout=0):
        ready = checked_ready(root)
        if ready is None:
            calibration = checked_ready(root / 'calibration', calibration_only=True)
            if calibration is None:
                raise ValueError('No saved results to validate')
            from freemocap.core.tasks.calibration.shared.calibration_result import CalibrationResult
            result = CalibrationResult.load_toml(Path(calibration['recording']) / calibration['result']['calibration_filename'])
            if len(result.cameras) != 3 or not math.isfinite(result.reprojection_error_px):
                raise ValueError('Invalid reference calibration')
            return dict(dataset=name, calibration_valid=True, recording=calibration['recording'])
        config = ready['result'].get('mocap_config', {})
        return validate_outputs(Path(ready['recording']), expected_frames=DATASETS[name].expected_frame_count,
                                require_fit=config.get('skeleton_fit_enabled', False))


def recover_dataset(name: str, *, prepared_root: Path) -> dict:
    root = prepared_root.expanduser().resolve() / DATASETS[name].name
    if not root.exists():
        raise ValueError('Dataset has no prepared directory')
    with FileLock(str(root / 'prepare.lock'), timeout=0):
        return dict(prepared=recover(root), calibration=recover(root / 'calibration'))
