"""Read complete calibration and mocap task snapshots without consuming updates."""

from fastapi import APIRouter
from pydantic import BaseModel

from freemocap.app.freemocap_application import get_freemocap_app
from freemocap.core.pipeline.posthoc.task_snapshot import TaskRegistrySnapshot
from freemocap.core.pipeline.posthoc.task_snapshot import TaskSnapshot, BackgroundTaskSnapshot
from freemocap.api import task_interface

tasks_router = APIRouter(tags=["Tasks"])


@tasks_router.get("/posthoc/tasks", include_in_schema=False, deprecated=True)
def task_snapshot() -> TaskRegistrySnapshot:
    return get_freemocap_app().posthoc_pipeline_manager.task_snapshot()


@tasks_router.get('/tasks')
def all_tasks() -> TaskRegistrySnapshot:
    """The complete retained snapshot, also delivered over WebSocket."""
    return task_interface.task_snapshot(get_freemocap_app())


@tasks_router.get('/tasks/{task_id}')
def get_task(task_id: str) -> TaskSnapshot | BackgroundTaskSnapshot:
    return task_interface.find_task(get_freemocap_app(), task_id)


@tasks_router.post('/tasks/{task_id}/cancel')
async def cancel_task(task_id: str) -> TaskSnapshot | BackgroundTaskSnapshot:
    return await task_interface.cancel_task_async(get_freemocap_app(), task_id)


class CancelTasksRequest(BaseModel):
    kind: task_interface.TaskKind


@tasks_router.post('/tasks/cancel')
async def cancel_tasks(request: CancelTasksRequest) -> TaskRegistrySnapshot:
    app = get_freemocap_app()
    for task in task_interface.task_snapshot(app).tasks:
        if task.task_type == request.kind and task.status in ('queued', 'running'):
            await task_interface.cancel_task_async(app, task.task_id)
    return task_interface.task_snapshot(app)
