
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


class PipelineCreateRequest(BaseModel):
    camera_configs: CameraConfigs

    @classmethod
    def example(cls):
        return cls(
            camera_configs={CameraIdString(0): CameraConfig(
                camera_id=CameraIdString(0),)}
        )

class PipelineCreateResponse(BaseModel):
    camera_group_id: CameraGroupIdString = Field(..., description="ID of the created camera group")
    camera_configs: CameraConfigs = Field(..., description="Camera configurations extracted from the created camera group")
    pipeline_id: str = Field(..., description="ID of the processing pipeline to which the camera group is attached")

@pipeline_router.post("/create",
                    summary="Create camera group with provided configuration settings and attach to a Dummy Processing Pipeline",
                    )
def pipeline_create_post_endpoint(
        request: PipelineCreateRequest = Body(...,
                                                 description="Request body containing desired camera configuration",
                                                 examples=[
                                                     PipelineCreateRequest.example()]), ) -> PipelineCreateResponse:
    logger.api(f"Received `pipeline/create` POST request - \n {request.model_dump_json(indent=2)}")
    try:
        configs = request.camera_configs
        get_freemocap_app().create_pipeline(camera_configs=configs)
        response = CreateCameraGroupResponse(group_id=camera_group.id,
                                             camera_configs=camera_group.configs)
        logger.api(
            f"`skellycam/cameras/group/create` POST request handled successfully - \n {response.model_dump_json(indent=2)}")
        return response
    except Exception as e:
        logger.error(f"Error when processing `skellycam/cameras/group/create` request: {type(e).__name__} - {e}")
        logger.exception(e)
        raise HTTPException(status_code=500,
                            detail=f"Error when processing `skellycam/cameras/group/create` request: {type(e).__name__} - {e}")


@camera_router.post("/group/all/record/sta