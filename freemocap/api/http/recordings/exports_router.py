"""Saved export choices, published files and asynchronous recording exports."""
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from freemocap.api.http.posthoc import export_jobs
from freemocap.api.http.recordings.recording_access import RecordingReadRoute
from freemocap.api.http.recordings.recording_location import recording_location
from freemocap.core.recording.exports.arrays import resolve_selection
from freemocap.core.recording.exports.catalog import (
    RecordingExportOptions, ExportInventory, export_options, export_inventory,
)
from freemocap.core.recording.exports.recording_export_request import RecordingExportRequest
from freemocap.core.recording.parquet_storage.recording_view import recording_view
from freemocap.core.recording.recording_access import RecordingBusyError

recording_exports_router = APIRouter(prefix='/recordings', tags=['Recording exports'])
export_reads = APIRouter(route_class=RecordingReadRoute)


@export_reads.get('/{recording_id}/export-options')
def get_export_options(recording_id: str, recording_parent_directory: str | None = None) -> RecordingExportOptions:
    return export_options(recording_location(recording_id, recording_parent_directory))


@export_reads.get('/{recording_id}/exports')
def list_exports(recording_id: str, recording_parent_directory: str | None = None,
                 verify: bool = False) -> ExportInventory:
    return export_inventory(recording_location(recording_id, recording_parent_directory), verify=verify)


recording_exports_router.include_router(export_reads)


class ExportTaskAccepted(BaseModel):
    task_id: str
    status_url: str


@recording_exports_router.post('/{recording_id}/exports', status_code=202)
def create_export(recording_id: str, options: RecordingExportRequest, background: BackgroundTasks,
                  http_request: Request, recording_parent_directory: str | None = None) -> ExportTaskAccepted:
    structure = recording_location(recording_id, recording_parent_directory)
    access = http_request.app.state.recording_access
    try:
        # Inspect the source now; the worker takes its own cancellable lease later.
        with access.read(path=structure.full_path, cancel=lambda: None):
            legacy_blender = options.kind == 'blender' and (options.route == 'legacy_npy'
                or (options.route == 'auto' and not structure.data_parquet_path.is_file()))
            if legacy_blender:
                if options.expected_revision is not None or options.run_id not in (None, 0):
                    raise ValueError('Legacy NumPy export has no saved Parquet run or revision')
            else:
                if not structure.data_parquet_path.is_file():
                    raise HTTPException(404, 'No saved Parquet result in this recording')
                with recording_view(structure.data_parquet_path) as view:
                    if options.expected_revision is not None and options.expected_revision != view.revision:
                        raise ValueError('Recording revision changed; reload export options')
                    run_id = view.metadata.selected_run_id if options.run_id is None else options.run_id
                    if run_id not in view.metadata.runs:
                        raise ValueError(f'Unknown recording run: {run_id}')
                    if options.kind == 'channels':
                        resolve_selection(view, options)
                    options = options.model_copy(update={'run_id': run_id, 'expected_revision': view.revision})
        key = export_jobs.create_job(structure=structure, request=options)
    except RecordingBusyError as error:
        raise HTTPException(409, {'code': 'recording_busy', 'owner': error.owner.model_dump(mode='json')}) from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    background.add_task(export_jobs.run_job, key, structure, options, access=access)
    task_id = f'export:{key}'
    return ExportTaskAccepted(task_id=task_id, status_url=f'/freemocap/tasks/{task_id}')
