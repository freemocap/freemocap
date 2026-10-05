"""Export saved scientific results without running the processing pipeline."""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from filelock import Timeout
from pydantic import BaseModel

from freemocap.core.recording.exports.tall_csv import TallCsvRequest, TallCsvResult, export_tall_csv
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.system.recording_structure.recording_structure import RecordingStructure

exports_router = APIRouter(prefix='/exports', tags=['Recording exports'])


def structure_for(path: str) -> RecordingStructure:
    folder = Path(path).expanduser().resolve()
    structure = RecordingStructure(base_directory=folder.parent, recording_name=folder.name)
    if not structure.data_parquet_path.is_file():
        raise HTTPException(404, 'No saved Parquet result in this recording. Process the recording first.')
    return structure


class SavedTallCsvRequest(TallCsvRequest):
    recording_path: str


class ExportSelection(BaseModel):
    run_ids: list[int]
    selected_run_id: int
    revision: str


@exports_router.get('/tall-csv', response_model=ExportSelection)
def selection(recording_path: str) -> ExportSelection:
    with recording_view(structure_for(recording_path).data_parquet_path) as view:
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
