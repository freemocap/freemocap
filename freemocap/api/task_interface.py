"""One status/cancellation surface over independently owned task executors."""
import asyncio
from typing import Literal

from fastapi import HTTPException

from freemocap.api.http.posthoc import export_jobs
from freemocap.core.pipeline.posthoc.task_snapshot import TaskRegistrySnapshot, TaskSnapshot, BackgroundTaskSnapshot
from freemocap.core.pipeline.realtime.startup_status import realtime_startup_snapshot

TaskKind = Literal['mocap', 'calibration', 'export', 'sync', 'realtime_startup', 'onnx_preparation']


def task_snapshot(app) -> TaskRegistrySnapshot:
    processing = app.posthoc_pipeline_manager.task_snapshot()
    sync_revision, sync = app.sync_job_manager.task_state.snapshot()
    export_revision, exports = export_jobs.task_state.snapshot()
    startup_revision, startups = 0, ()
    preparation_revision, preparations = 0, ()
    # Partial app facades used by standalone task consumers need no realtime owner.
    if getattr(app, 'startup_status', None) is not None:
        realtime_startup_snapshot(app)
        startup_revision, startups = app.startup_status.tasks_snapshot()
    preparation_snapshot = getattr(getattr(app, 'inference_service', None), 'preparation_tasks_snapshot', None)
    if preparation_snapshot is not None:
        preparation_revision, preparations = preparation_snapshot()
    return processing.model_copy(update={
        'revision': processing.revision + sync_revision + export_revision + startup_revision + preparation_revision,
        'tasks': (*processing.tasks, *sync, *exports, *startups, *preparations),
    })


def find_task(app, task_id: str) -> TaskSnapshot | BackgroundTaskSnapshot:
    for task in task_snapshot(app).tasks:
        if task.task_id == task_id:
            return task
    raise HTTPException(404, 'Task is not retained in this server session')


def cancel_task(app, task_id: str) -> TaskSnapshot | BackgroundTaskSnapshot:
    task = find_task(app, task_id)
    if task.status not in ('queued', 'running'):
        return task
    if task.task_type == 'export':
        export_jobs.cancel_job(task_id.removeprefix('export:'))
    elif task.task_type == 'sync':
        app.sync_job_manager.stop_job(job_id=task_id.removeprefix('sync:'))
    elif task.task_type == 'onnx_preparation':
        if not app.inference_service.cancel_preparation_task(task_id):
            raise HTTPException(409, 'Preparation task is no longer current')
    elif task.task_type == 'realtime_startup':
        raise HTTPException(409, 'Startup cancellation requires the asynchronous task endpoint')
    else:
        app.posthoc_pipeline_manager.stop_pipeline(pipeline_id=task_id, pipeline_type=task.task_type)
    return find_task(app, task_id)


async def cancel_task_async(app, task_id: str) -> TaskSnapshot | BackgroundTaskSnapshot:
    task = find_task(app, task_id)
    if task.task_type != 'realtime_startup':
        return await asyncio.to_thread(cancel_task, app, task_id)
    if task.status in ('queued', 'running') and app.startup_status.task_id == task_id:
        await app.stop_realtime_startup()
    return find_task(app, task_id)
