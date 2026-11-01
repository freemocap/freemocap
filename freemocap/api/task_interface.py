"""One status/cancellation surface over independently owned task executors."""
from typing import Literal

from fastapi import HTTPException

from freemocap.api.http.posthoc import export_jobs
from freemocap.core.pipeline.posthoc.task_snapshot import TaskRegistrySnapshot, TaskSnapshot, BackgroundTaskSnapshot

TaskKind = Literal['mocap', 'calibration', 'export', 'sync']


def task_snapshot(app) -> TaskRegistrySnapshot:
    processing = app.posthoc_pipeline_manager.task_snapshot()
    sync_revision, sync = app.sync_job_manager.task_state.snapshot()
    export_revision, exports = export_jobs.task_state.snapshot()
    return processing.model_copy(update={
        'revision': processing.revision + sync_revision + export_revision,
        'tasks': (*processing.tasks, *sync, *exports),
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
    else:
        app.posthoc_pipeline_manager.stop_pipeline(pipeline_id=task_id, pipeline_type=task.task_type)
    return find_task(app, task_id)
