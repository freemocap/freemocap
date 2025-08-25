
import logging
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field
from skellycam.core.camera.config.camera_config import CameraConfigs, CameraConfig
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString

from freemocap.freemocap_app.freemocap_application import get_freemocap_app

logger = logging.getLogger(__name__)

pipeline_router = APIRouter(prefix=f"/pipeline",
                             tags=["Processing Pipelines"],)


class PipelineConnectRequest(BaseModel):
    camera_ids: list[CameraIdString] = Field(..., description="List of camera IDs comprising the CameraGroup we're attaching a pipeline to")


class PipelineCreateResponse(BaseModel):
    camera_group_id: CameraGroupIdString = Field(..., description="ID of the camera group attached to the pipeline")
    pipeline_id: str = Field(..., description="ID of the processing pipeline to which the camera group is attached")

@pipeline_router.post("/connect",
                    summary="Create a processing pipeline and attach it to a camera group"
                    )
def pipeline_create_post_endpoint(
        request: PipelineConnectRequest = Body(...,
                                               description="Request body containing desired camera configuration",
                                               examples=[
                                                     PipelineConnectRequest(camera_ids=['0'])]), ) -> PipelineCreateResponse:
    logger.api(f"Received `pipeline/create` POST request - \n {request.model_dump_json(indent=2)}")
    try:

        camera_group = get_freemocap_app().skellycam_app.camera_group_manager.camera_group_from_camera_ids(camera_ids=request.camera_ids)
        camera_group_id, pipeline_id = get_freemocap_app().create_pipeline(camera_group=camera_group)
        response = PipelineCreateResponse(camera_group_id=camera_group_id,
                                           pipeline_id=pipeline_id)
        logger.api(
            f"`pipeline/create` POST request handled successfully - \n {response.model_dump_json(indent=2)}")
        return response
    except Exception as e:
        logger.error(f"Error when processing `pipeline/create` request: {type(e).__name__} - {e}")
        logger.exception(e)
        raise HTTPException(status_code=500,
                            detail=f"Error when processing `pipeline/create` request: {type(e).__name__} - {e}")