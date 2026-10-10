"""Export saved scientific results without running the processing pipeline."""
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks, Response
from filelock import Timeout
from pydantic import BaseModel

from freemocap.core.recording.exports.tall_csv import TallCsvRequest, TallCsvResult, export_tall_csv
from freemocap.core.recording.exports.requests import ScientificExportRequest
from freemocap.core.recording.exports.arrays import scientific_channels, resolve_selection
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from .export_jobs import create_job, run_job, job_state, cancel_job

exports_router = APIRouter(prefix='/exports', tags=['Recording exports'])

class SavedScientificRequest(ScientificExportRequest):
    recording_path: str


@exports_router.get('/scientific')
def scientific_selection(recording_path: str):
    structure = structure_for(recording_path, require_result=False)
    if not structure.data_parquet_path.is_file():
        return Response(status_code=204)
    with recording_view(structure.data_parquet_path) as view:
        return dict(revision=view.revision, selected_run_id=view.metadata.selected_run_id,
            formats=['wide_csv', 'npy', 'npz', 'notebook'], runs=[dict(run_id=rid, channels=[dict(selection=context.model_dump(mode='json'),
                names=len(channel.names), components=list(channel.components), units=channel.components)
                for context, channel, _ in scientific_channels(run)]) for rid, run in view.metadata.runs.items()])


@exports_router.post('/scientific', status_code=202)
def save_scientific(request: SavedScientificRequest, background: BackgroundTasks):
    structure = structure_for(request.recording_path)
    options = ScientificExportRequest(**request.model_dump(exclude={'recording_path'}))
    try:
        with recording_view(structure.data_parquet_path) as view:
            run_id, _ = resolve_selection(view, options)
            options = options.model_copy(update=dict(run_id=run_id, expected_revision=view.revision))
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    key = create_job()
    background.add_task(run_job, key, structure, options)
    return dict(job_id=key)


@exports_router.get('/jobs/{job_id}')
def get_export_job(job_id: str):
    return job_state(job_id)


@exports_router.post('/jobs/{job_id}/cancel')
def stop_export_job(job_id: str):
    return cancel_job(job_id)


def structure_for(path: str, *, require_result: bool = True) -> RecordingStructure:
    folder = Path(path).expanduser().resolve()
    if not folder.is_dir():
        raise HTTPException(404, 'Recording folder does not exist.')
    structure = RecordingStructure(base_directory=folder.parent, recording_name=folder.name)
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
def save_tall_csv(request: SavedTallCsvRequest) -> TallCsvResult:
    # A synchronous route runs in FastAPI's thread pool; large exports do not
    # block the event loop or rerun detection/reconstruction.
    try:
        return export_tall_csv(structure=structure_for(request.recording_path),
            request=TallCsvRequest(**request.model_dump(exclude={'recording_path'})))
    except (ValueError, FileExistsError, Timeout) as error:
        raise HTTPException(409, str(error)) from error
    except OSError as error:
        raise HTTPException(500, f'Could not save tall CSV: {error}') from error
