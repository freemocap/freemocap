"""Application-facing DLC import jobs; Tracker owns conversion and model semantics."""
from dataclasses import asdict
from pathlib import Path
from threading import Lock
from time import monotonic
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, ConfigDict
from skellytracker.core.config.dlc_conversion import (
    DlcConversionRequest, prepare_dlc_model, dlc_conversion_readiness,
)
from skellytracker.core.sessions.model_registry import DEFAULT_CACHE_DIR
from skellytracker.core.sidecar.errors import SidecarError
from skellytracker.core.tracker.tracker_presets import dlc_tracker_metadata

dlc_router = APIRouter(prefix="/dlc", tags=["DeepLabCut"])


class DlcInspectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sidecar_path: Path


def model_information(path: Path) -> dict:
    metadata = dlc_tracker_metadata(sidecar_path=path)
    return {**asdict(metadata), "sidecar_path": metadata.model_name,
            "execution_providers": ["cpu", "cuda"], "precision": "fp32"}


@dlc_router.get("/readiness")
def conversion_readiness() -> dict:
    return dlc_conversion_readiness()


@dlc_router.post("/inspect")
def inspect_model(request: DlcInspectRequest) -> dict:
    try:
        return model_information(request.sidecar_path)
    except (ValueError, OSError, SidecarError) as error:
        raise HTTPException(422, str(error)) from error


# Same bounded session-local job model as saved exports. Conversion runs in a
# background worker, never the event loop or realtime inference thread. Tracker
# bounds its CPU subprocess lifetime and retains useful error text on failure.
_jobs: dict[str, dict] = {}
_lock = Lock()


def _snapshot(job: dict) -> dict:
    """Return public job state; process-local clock values never leave the server."""
    result = {key: value for key, value in job.items() if not key.startswith('_')}
    if job['status'] == 'running':
        now = monotonic()
        result['elapsed_seconds'] = max(0.0, now - job['_started_at'])
        if job.get('estimated_remaining_seconds') is not None:
            result['estimated_remaining_seconds'] = max(
                0.0, job['estimated_remaining_seconds'] - (now - job['_estimate_at']))
    return result


def _run_import(job_id: str, request: DlcConversionRequest) -> None:
    with _lock:
        _jobs[job_id].update(status="running", stage="checking", detail="Checking the model and saved conversions",
                             _started_at=monotonic())

    def progress(update: dict) -> None:
        with _lock:
            _jobs[job_id].update({key: value for key, value in update.items()
                                  if key in ('stage', 'detail', 'estimated_remaining_seconds', 'cache_hit', 'required_fields', 'resolved_checkpoint_path')})
            if 'estimated_remaining_seconds' in update:
                _jobs[job_id]['_estimate_at'] = monotonic()

    try:
        path = prepare_dlc_model(request, DEFAULT_CACHE_DIR / "dlc", on_progress=progress)
        result = model_information(path)
        with _lock:
            job = _jobs[job_id]
            job.update(status="complete", stage="ready", detail="DLC model is ready", result=result,
                       elapsed_seconds=max(0.0, monotonic() - job['_started_at']), estimated_remaining_seconds=0.0)
    except Exception as error:
        with _lock:
            job = _jobs[job_id]
            job.update(status="failed", stage="needs_input" if job.get('required_fields') else "failed", detail=str(error),
                       elapsed_seconds=max(0.0, monotonic() - job['_started_at']), estimated_remaining_seconds=None)


@dlc_router.post("/import", status_code=202)
def import_model(request: DlcConversionRequest, background_tasks: BackgroundTasks) -> dict:
    with _lock:
        if any(job["status"] in ("queued", "running") for job in _jobs.values()):
            raise HTTPException(409, "A DLC model conversion is already active; wait for it to finish")
        while len(_jobs) >= 100:
            del _jobs[next(iter(_jobs))]
        job_id = uuid4().hex
        _jobs[job_id] = dict(job_id=job_id, status="queued", stage="queued", detail="Queued model preparation",
                            result=None, elapsed_seconds=0.0, estimated_remaining_seconds=None, cache_hit=False)
        response = _snapshot(_jobs[job_id])
    background_tasks.add_task(_run_import, job_id, request)
    return response


@dlc_router.get("/import/{job_id}")
def import_status(job_id: str) -> dict:
    with _lock:
        if job_id not in _jobs:
            raise HTTPException(404, "DLC import job is no longer available; inspect the exported sidecar or retry")
        return _snapshot(_jobs[job_id])
