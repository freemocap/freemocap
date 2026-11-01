"""Bounded, session-local saved-export jobs with cooperative cancellation."""
from concurrent.futures import CancelledError
from contextlib import nullcontext
from dataclasses import dataclass, field
from threading import Event, Lock
from uuid import uuid4

from fastapi import HTTPException

from freemocap.core.recording.exports.wide_csv import export_recording
from freemocap.core.recording.exports.requests import ExportRequest
from freemocap.core.recording.exports.tall_csv import TallCsvRequest, export_tall_csv
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.core.blender.export_to_blender import export_to_blender
from filelock import FileLock
from freemocap.core.recording.exports.publication import artifact_path
from freemocap.core.tasks.background_task_state import BackgroundTaskState
from freemocap.core.pipeline.posthoc.task_snapshot import TaskProgress


@dataclass
class ExportJob:
    stop: Event = field(default_factory=Event)
    state: dict = field(default_factory=lambda: dict(status='queued', completed_channels=0, total_channels=0, detail='Queued'))


_jobs: dict[str, ExportJob] = {}
_lock = Lock()
task_state = BackgroundTaskState()


def create_job(*, structure=None, request=None):
    with _lock:
        if sum(j.state['status'] in ('queued', 'running') for j in _jobs.values()) >= 4:
            raise HTTPException(409, 'Four export jobs are already active; wait or cancel one')
        while len(_jobs) >= 100:
            oldest = next(key for key, job in _jobs.items() if job.state['status'] not in ('queued', 'running'))
            del _jobs[oldest]
        key = uuid4().hex
        _jobs[key] = ExportJob()
        task_state.register(f'export:{key}', 'export', recording=structure,
                            source_run_id=getattr(request, 'run_id', None),
                            source_revision=getattr(request, 'expected_revision', None))
        return key


def job_state(key):
    with _lock:
        if key not in _jobs:
            raise HTTPException(404, 'Export job no longer available; inspect the output folder or retry')
        return dict(_jobs[key].state, job_id=key)


def cancel_job(key):
    with _lock:
        if key not in _jobs:
            raise HTTPException(404, 'Export job not found')
        _jobs[key].stop.set()
        task_state.update(f'export:{key}', cancellation_requested=True)
    return job_state(key)


def run_job(key, structure, request, *, access=None):
    job = _jobs[key]
    def update(**values):
        with _lock:
            job.state.update(values)
            state = job.state
            total = state['total_channels']
            task_state.update(f'export:{key}', status=state['status'],
                recording=structure, source_run_id=request.run_id, source_revision=request.expected_revision,
                progress=TaskProgress(phase=state['status'],
                    progress_fraction=state['completed_channels'] / total if total else None,
                    detail=state['detail']), result=state.get('result'),
                error=state['detail'] if state['status'] == 'failed' else None)
    try:
        if job.stop.is_set():
            raise CancelledError()
        update(status='running')
        with access.read(path=structure.full_path, cancel=job.stop.set) if access is not None else nullcontext():
            kind = getattr(request, 'kind', 'channels')
            if kind == 'channels':
                result = export_recording(structure=structure,
                    request=ExportRequest(**request.model_dump(exclude={'kind'})), cancelled=job.stop.is_set,
                    progress=lambda done, total, detail: update(completed_channels=done, total_channels=total, detail=detail))
                result = result.model_dump(mode='json')
            elif kind == 'tall_csv':
                result = export_tall_csv(structure=structure,
                    request=TallCsvRequest(**request.model_dump(exclude={'kind'})), cancelled=job.stop.is_set,
                    progress=lambda rows: update(detail=f'Wrote {rows} rows'))
                result = result.model_dump(mode='json')
            elif kind == 'blender':
                if request.expected_revision is not None:
                    with recording_view(structure.data_parquet_path) as view:
                        if request.expected_revision != view.revision:
                            raise ValueError('Recording revision changed before Blender export')
                structure.exports_dir.mkdir(parents=True, exist_ok=True)
                with FileLock(artifact_path(structure.exports_dir, '.blender-export.lock'), timeout=0):
                    path = export_to_blender(recording_folder_path=str(structure.full_path),
                        blender_exe_path=request.blender_exe_path, open_file_on_completion=request.auto_open_blend_file,
                        route=request.route, package=request.package, trajectory_channel=request.trajectory_channel,
                        run_id=request.run_id, sensor_group=request.sensor_group,
                        development_build_hash=request.development_build_hash,
                        blender_export_config=request.blender_export_config.model_dump(),
                        cancelled=job.stop.is_set, progress=lambda detail: update(detail=detail))
                result = {'success': True, 'message': 'Export to Blender completed', 'blender_file_path': path}
            else:
                raise ValueError(f'Unknown export kind: {kind}')
        update(status='complete', result=result)
    except CancelledError:
        update(status='cancelled', detail='Export cancelled; previously published outputs are unchanged')
    except Exception as error:
        update(status='failed', detail=str(error))
