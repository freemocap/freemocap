import logging

from fastapi import APIRouter, HTTPException

from freemocap.app.freemocap_application import get_freemocap_app

logger = logging.getLogger(__name__)

posthoc_router = APIRouter(prefix="/posthoc", tags=["Posthoc"])


@posthoc_router.delete("/pipeline/{pipeline_id}")
async def stop_pipeline(pipeline_id: str) -> dict:
    """Stop a single posthoc pipeline by ID."""
    found = get_freemocap_app().stop_posthoc_pipeline(pipeline_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Pipeline '{pipeline_id}' not found")
    return {"success": True, "pipeline_id": pipeline_id}


@posthoc_router.delete("/pipeline")
async def stop_all_pipelines() -> dict:
    """Stop all active posthoc pipelines."""
    get_freemocap_app().stop_all_posthoc_pipelines()
    return {"success": True}
