"""Export saved results without running the processing pipeline."""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Response, Request
from concurrent.futures import CancelledError
from threading import Event
from filelock import Timeout
from pydantic import BaseModel

from freemocap.core.recording.exports.tall_csv import TallCsvRequest, TallCsvResult, export_tall_csv
from freemocap.core.recording.exports.requests import ExportRequest
from freemocap.core.recording.exports.arrays import resolve_selection
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.api.http.recordings.recording_location import recording_path_location
from freemocap.api.http.recordings.recording_access import RecordingReadRoute
from freemocap.core.recording.exports.catalog import export_options
from freemocap.core.recording.recording_access import RecordingBusyError
from .export_jobs import create_job, run_job, job_state, cancel_job

exports_router = APIRouter(prefix='/exports', tags=['Recording exports'],
                          include_in_schema=False, deprecated=True, route_class=RecordingReadRoute)

class SavedExportRequest(ExportRequest):
    recording_path: str


@exports_router.get('/scientific')
def export_selection(recording_path: str):
    structure = structure_for(recording_path, require_result=False)
    if not structure.data_parquet_path.is_file():
        return Response(status_code=204)
    return export_options(structure).model_dump(mode='json', exclude={'kinds'})


@exports_router.post('/scientific', status_code=202)
def save_channel_exports(request: SavedExportRequest, background: BackgroundTasks, http_request: Request):
    structure = structure_for(request.recording_path)
    options = ExportRequest(**request.model_dump(exclude={'recording_path'}))
    try:
        with http_request.app.state.recording_access.read(path=structure.full_path, cancel=lambda: None), recording_view(structure.data_parquet_path) as view:
            run_id, _ = resolve_selection(view, options)
            options = options.model_copy(update=dict(run_id=run_id, expected_revision=view.revision))
    except (ValueError, RecordingBusyError) as error:
        raise HTTPException(409, str(error)) from error
    key = create_job(structure=structure, request=options)
    background.add_task(run_job, key, structure, options, access=http_request.app.state.recording_access)
    return dict(job_id=key)


@exports_router.get('/jobs/{job_id}')
def get_export_job(job_id: str):
    return job_state(job_id)


@exports_router.post('/jobs/{job_id}/cancel')
def stop_export_job(job_id: str):
    return cancel_job(job_id)


def structure_for(path: str, *, require_result: bool = True) -> RecordingStructure:
    structure = recording_path_location(path)
    if require_result and not structure.data_parquet_path.is_file():
        raise HTTPException(404, 'No saved Parquet result in this recording. Process the recording first.')
    return structure


class SavedTallCsvRequest(TallCsvRequest):
    recording_path: str


class ExportSelection(BaseModel):
    run_ids: list[int]
    selected_run_id: int
    revision: str


@exports_router.get('/tall-csv', response_model=ExportSelection)
def selection(recording_path: str) -> ExportSelection | Response:
    structure = structure_for(recording_path, require_result=False)
    if not structure.data_parquet_path.is_file():
        return Response(status_code=204)
    with recording_view(structure.data_parquet_path) as view:
        return ExportSelection(run_ids=list(view.metadata.runs),
            selected_run_id=view.metadata.selected_run_id, revision=view.revision)


@exports_router.post('/tall-csv', response_model=TallCsvResult)
def save_tall_csv(request: SavedTallCsvRequest, http_request: Request) -> TallCsvResult:
    # A synchronous route runs in FastAPI's thread pool; large exports do not
    # block the event loop or rerun detection/reconstruction.
    try:
        structure = structure_for(request.recording_path)
        cancelled = Event()
        with http_request.app.state.recording_access.read(path=structure.full_path, cancel=cancelled.set):
            return export_tall_csv(structure=structure,
                request=TallCsvRequest(**request.model_dump(exclude={'recording_path'})), cancelled=cancelled.is_set)
    except (RecordingBusyError, CancelledError) as error:
        raise HTTPException(409, str(error)) from error
    except (ValueError, FileExistsError, Timeout) as error:
        raise HTTPException(409, str(error)) from error
    except OSError as error:
        raise HTTPException(500, f'Could not save tall CSV: {error}') from error
