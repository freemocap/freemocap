"""Read complete calibration and mocap task snapshots without consuming updates."""

from fastapi import APIRouter

from freemocap.app.freemocap_application import get_freemocap_app
from freemocap.core.pipeline.posthoc.task_snapshot import TaskRegistrySnapshot

tasks_router = APIRouter(prefix="/posthoc/tasks", tags=["Posthoc tasks"])


@tasks_router.get("")
def task_snapshot() -> TaskRegistrySnapshot:
    return get_freemocap_app().posthoc_pipeline_manager.task_snapshot()
