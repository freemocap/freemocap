"""Inspect and import external videos before a recording exists."""
from fastapi import APIRouter
from pydantic import BaseModel

from freemocap.api.http.mocap import mocap_router as mocap

import_router = APIRouter(prefix='/recording-import', tags=['Recording import'])
import_router.add_api_route('', mocap.import_videos, methods=['POST'], operation_id='import_recording')
import_router.add_api_route('/check-sync', mocap.check_video_sync, methods=['POST'],
                            operation_id='check_import_frame_counts', summary='Check video frame-count compatibility')


class SynchronizationAccepted(BaseModel):
    task_id: str
    job_id: str
    status_url: str


@import_router.post('/synchronize', status_code=202)
async def synchronize(request: mocap.SynchronizeVideosRequest) -> SynchronizationAccepted:
    result = await mocap.synchronize_videos(request)
    task_id = f'sync:{result.job_id}'
    return SynchronizationAccepted(task_id=task_id, job_id=result.job_id, status_url=f'/freemocap/tasks/{task_id}')
