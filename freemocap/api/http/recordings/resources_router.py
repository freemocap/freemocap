"""Recording resource routes share readers with the legacy playback endpoints."""
from urllib.parse import quote, urlencode

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from freemocap.api.http.playback import playback_router as readers
from freemocap.api.http.recordings.recording_access import RecordingReadRoute
from freemocap.api.http.recordings.recording_location import recording_location
from freemocap.core.recording.recording_queries import (
    RunInventory, RunChannels, recording_runs, recording_channels,
)

recordings_router = APIRouter(prefix='/recordings', route_class=RecordingReadRoute,
                             responses={400: {'description': 'Invalid recording identity'},
                                        404: {'description': 'Recording or resource not found'},
                                        409: {'description': 'Recording busy or revision changed'}})

# Reuse the existing readers and their concrete response annotations. These are
# aliases at the transport boundary, not a second implementation of file access.
for path, handler, tag, summary in (
    ('', readers.list_recordings, 'Recordings', 'List recordings'),
    ('/{recording_id}/status', readers.get_recording_status, 'Recordings', 'Inspect recording readiness'),
    ('/{recording_id}/media', readers.read_unprocessed_media, 'Recording media', 'Read media timelines'),
    ('/{recording_id}/videos', readers.list_videos, 'Recording media', 'List recording videos'),
    ('/{recording_id}/videos/{video_id}', readers.stream_video, 'Recording media', 'Read video bytes'),
    ('/{recording_id}/videos/{video_id}/browser', readers.browser_video_stream, 'Recording media', 'Read browser-compatible video'),
    ('/{recording_id}/parquet', readers.get_recording_parquet, 'Recording results', 'Read recording Parquet'),
    ('/{recording_id}/calibration', readers.get_recording_calibration, 'Recording calibration', 'Read recording calibration'),
    ('/{recording_id}/playback/manifest', readers.get_playback_manifest, 'Playback', 'Read playback manifest'),
    ('/{recording_id}/playback/bundle', readers.get_recording_bundle, 'Playback', 'Read playback resources'),
    ('/{recording_id}/playback/tracker-schema', readers.get_tracker_schema, 'Playback', 'Read playback tracker schema'),
):
    recordings_router.add_api_route(path, handler, methods=['GET'], tags=[tag], summary=summary,
                                    operation_id=f'recordings_{handler.__name__}')


class RecordingResources(BaseModel):
    recording_id: str
    recording_parent_directory: str
    path: str
    resources: dict[str, bool]
    links: dict[str, str]


@recordings_router.get('/{recording_id}', tags=['Recordings'], summary='Describe recording resources')
def describe_recording(recording_id: str, recording_parent_directory: str | None = None) -> RecordingResources:
    structure = recording_location(recording_id, recording_parent_directory)
    base = f'/freemocap/recordings/{quote(recording_id, safe="")}'
    query = '?' + urlencode({'recording_parent_directory': str(structure.base_directory)})
    return RecordingResources(recording_id=structure.recording_name,
        recording_parent_directory=str(structure.base_directory), path=str(structure.full_path),
        resources={'saved_results': structure.data_parquet_path.is_file(), 'exports': structure.exports_dir.is_dir()},
        links={name: base + suffix + query for name, suffix in {
            'self': '', 'status': '/status', 'runs': '/runs', 'videos': '/videos',
            'calibration': '/calibration', 'parquet': '/parquet', 'playback': '/playback/bundle',
            'exports': '/exports', 'export_options': '/export-options',
        }.items()})


@recordings_router.get('/{recording_id}/runs', tags=['Recording results'], summary='List saved recording runs')
def list_recording_runs(recording_id: str, recording_parent_directory: str | None = None) -> RunInventory:
    try:
        return recording_runs(recording_location(recording_id, recording_parent_directory))
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@recordings_router.get('/{recording_id}/runs/{run_id}/channels', tags=['Recording results'], summary='Read saved channel definitions')
def list_run_channels(recording_id: str, run_id: int, recording_parent_directory: str | None = None) -> RunChannels:
    try:
        return recording_channels(recording_location(recording_id, recording_parent_directory), run_id)
    except (FileNotFoundError, KeyError) as error:
        raise HTTPException(404, str(error)) from error
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
