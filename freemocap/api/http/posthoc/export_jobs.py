"""Bounded, session-local saved-export jobs with cooperative cancellation."""
from concurrent.futures import CancelledError
from dataclasses import dataclass, field
from threading import Event, Lock
from uuid import uuid4

from fastapi import HTTPException

from freemocap.core.recording.exports.wide_csv import export_scientific


@dataclass
class ExportJob:
    stop: Event = field(default_factory=Event)
    state: dict = field(default_factory=lambda: dict(status='queued', completed_channels=0, total_channels=0, detail='Queued'))


_jobs: dict[str, ExportJob] = {}
_lock = Lock()


def create_job():
    with _lock:
        if sum(j.state['status'] in ('queued', 'running') for j in _jobs.values()) >= 4:
            raise HTTPException(409, 'Four export jobs are already active; wait or cancel one')
        while len(_jobs) >= 100:
            oldest = next(key for key, job in _jobs.items() if job.state['status'] not in ('queued', 'running'))
            del _jobs[oldest]
        key = uuid4().hex
        _jobs[key] = ExportJob()
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
    return job_state(key)


def run_job(key, structure, request):
    job = _jobs[key]
    def update(**values):
        with _lock:
            job.state.update(values)
    try:
        update(status='running')
        result = export_scientific(structure=structure, request=request, cancelled=job.stop.is_set,
            progress=lambda done, total, detail: update(completed_channels=done, total_channels=total, detail=detail))
        update(status='complete', result=result.model_dump(mode='json'))
    except CancelledError:
        update(status='cancelled', detail='Export cancelled; previously published outputs are unchanged')
    except Exception as error:
        update(status='failed', detail=str(error))
