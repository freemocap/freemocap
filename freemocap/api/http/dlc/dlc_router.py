"""Application-facing DLC import jobs; Tracker owns conversion and model semantics."""
from dataclasses import asdict
from pathlib import Path
from threading import Lock
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, ConfigDict
from skellytracker.core.config.dlc_conversion import (
    DlcConversionRequest, convert_dlc_model, dlc_conversion_readiness,
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


def _run_import(job_id: str, request: DlcConversionRequest) -> None:
    with _lock:
        _jobs[job_id].update(status="running", detail="Converting DLC model on CPU")
    try:
        path = convert_dlc_model(request, DEFAULT_CACHE_DIR / "dlc" / job_id)
        result = model_information(path)
        with _lock:
            _jobs[job_id].update(status="complete", detail="DLC model is ready", result=result)
    except Exception as error:
        with _lock:
            _jobs[job_id].update(status="failed", detail=str(error))


@dlc_router.post("/import", status_code=202)
def import_model(request: DlcConversionRequest, background_tasks: BackgroundTasks) -> dict:
    readiness = dlc_conversion_readiness()
    if not readiness["available"]:
        raise HTTPException(503, readiness["detail"])
    with _lock:
        if any(job["status"] in ("queued", "running") for job in _jobs.values()):
            raise HTTPException(409, "A DLC model conversion is already active; wait for it to finish")
        while len(_jobs) >= 100:
            del _jobs[next(iter(_jobs))]
        job_id = uuid4().hex
        _jobs[job_id] = dict(job_id=job_id, status="queued", detail="Queued DLC conversion", result=None)
        response = dict(_jobs[job_id])
    background_tasks.add_task(_run_import, job_id, request)
    return response


@dlc_router.get("/import/{job_id}")
def import_status(job_id: str) -> dict:
    with _lock:
        if job_id not in _jobs:
            raise HTTPException(404, "DLC import job is no longer available; inspect the exported sidecar or retry")
        return dict(_jobs[job_id])
