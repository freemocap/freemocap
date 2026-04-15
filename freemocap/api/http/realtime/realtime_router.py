import logging

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field
from skellycam.core.camera_group.camera_group import CameraConfigs
from skellycam.core.types.type_overloads import CameraGroupIdString

from freemocap.app.freemocap_application import get_freemocap_app
from freemocap.core.pipeline.realtime.realtime_aggregator_node import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline

logger = logging.getLogger(__name__)

realtime_router = APIRouter(prefix="/realtime", tags=["Realtime Processing Pipeline"])


class RealtimePipelineConnectRequest(BaseModel):
    camera_configs: CameraConfigs|None = Field(default=None,
                                               alias="cameraConfigs",
                                               description="Camera configurations for the CameraGroup we're attaching a pipeline to. If None, use existing camera group (or throw if no camera group connected)")
    realtime_config: RealtimePipelineConfig = Field(
        default_factory=RealtimePipelineConfig,
        description="Configuration for the realtime processing pipeline",
        alias="realtimeConfig",
        examples=[RealtimePipelineConfig()],
    )

class RealtimePipelineCreateResponse(BaseModel):
    camera_group_id: CameraGroupIdString = Field(
        description="ID of the camera group attached to the pipeline",
    )
    pipeline_id: str = Field(
        description="ID of the processing pipeline",
    )
    @classmethod
    def from_pipeline(cls, pipeline: RealtimePipeline) -> "RealtimePipelineCreateResponse":
        return cls(
            camera_group_id=pipeline.camera_group.id,
            pipeline_id=pipeline.id,
        )

class RealtimePipelineCloseResponse(BaseModel):
    success: bool
    message: str | None = None

class RealtimePipelineUpdateRequest(BaseModel):
    config: RealtimePipelineConfig = Field(default_factory=RealtimePipelineConfig, examples=[RealtimePipelineConfig()])


@realtime_router.post(
    "/apply",
    summary="Create/update a processing pipeline and attach it to a camera group",
)
async def pipeline_apply_endpoint(
    request: RealtimePipelineConnectRequest = Body(
        description="Configuration for the realtime processing pipeline",
        examples=[
            RealtimePipelineConnectRequest(),
        ],
    ),
) -> RealtimePipelineCreateResponse:
    logger.api(f"Received `realtime/apply` POST request - \n {request.model_dump_json(indent=2)}")
    try:
        app = get_freemocap_app()
        if request.camera_configs is None:
            camera_groups = app.camera_group_manager.camera_groups
            if len(camera_groups) == 0:
                raise RuntimeError("No camera groups currently connected - must provide camera configs to create a new camera group and attach a pipeline")
            elif len(camera_groups) > 1:
                raise NotImplementedError("Multiple camera groups not yet supported")
            camera_configs = next(iter(camera_groups.values())).configs
        else:
            camera_configs = request.camera_configs

        if camera_configs is None or len(camera_configs) == 0:
            raise RuntimeError("No valid camera configs found in request or current server state")

        pipeline = await app.create_or_update_realtime_pipeline(pipeline_config=request.realtime_config,
                                                                                camera_configs=camera_configs,)
        response = RealtimePipelineCreateResponse.from_pipeline(pipeline=pipeline)
        logger.api(f"`pipeline/connect` POST request handled successfully - \n {response.model_dump_json(indent=2)}")
        return response
    except Exception as e:
        logger.error(f"Error when processing `pipeline/connect` request: {type(e).__name__} - {e}")
        logger.exception(e)
        raise HTTPException(
            status_code=500,
            detail=f"Error when processing `pipeline/connect` request: {type(e).__name__} - {e}",
        )


@realtime_router.delete(
    "/all/close",
    summary="Disconnect/shutdown all processing pipelines",
)
async def pipeline_close_endpoint() -> None:
    logger.api("Received `pipeline/close` DELETE request")
    try:
        get_freemocap_app().close_pipelines()
        logger.api("`pipeline/close` DELETE request handled successfully")
    except Exception as e:
        logger.error(f"Error when processing `pipeline/close` request: {type(e).__name__} - {e}")
        logger.exception(e)
        raise HTTPException(
            status_code=500,
            detail=f"Error when processing `pipeline/close` request: {type(e).__name__} - {e}",
        )
