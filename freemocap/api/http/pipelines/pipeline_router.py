import logging

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString

from freemocap.core.pipeline.pipeline_configs import PipelineConfig
from freemocap.freemocap_app.freemocap_application import get_freemocap_app

logger = logging.getLogger(__name__)

pipeline_router = APIRouter(prefix=f"/pipeline",
                            tags=["Processing Pipelines"], )


class PipelineConnectRequest(BaseModel):
    camera_ids: list[CameraIdString] = Field(default=list,
                                             description="List of camera IDs comprising the CameraGroup we're attaching a pipeline to")
    pipeline_config: PipelineConfig|None = None

class PipelineCreateResponse(BaseModel):
    camera_group_id: CameraGroupIdString = Field(..., description="ID of the camera group attached to the pipeline")
    pipeline_id: str = Field(..., description="ID of the processing pipeline to which the camera group is attached")


@pipeline_router.post("/connect",
                      summary="Create a processing pipeline and attach it to a camera group"
                      )
def pipeline_connect_post_endpoint(
        request: PipelineConnectRequest = Body(...,
                                               description="Request body containing desired camera configuration",
                                               examples=[
                                                   PipelineConnectRequest(
                                                       camera_ids=['0'])]), ) -> PipelineCreateResponse:
    logger.api(f"Received `pipeline/connect` POST request - \n {request.model_dump_json(indent=2)}")
    try:
        cgm = get_freemocap_app().skellycam_app.camera_group_manager
        if request.camera_ids is None or len(request.camera_ids) == 0:
            cg = list(cgm.camera_groups.values())[0] if len(cgm.camera_groups) > 0 else None
            camera_ids = cg.camera_ids
            logger.api(
                f"No camera IDs specified in request; defaulting to first available camera group (id:{cg.id}) with camera IDs: {camera_ids}")
        else:
            cg = get_freemocap_app().skellycam_app.camera_group_manager.find_camera_group_by_camera_ids(
                camera_ids=request.camera_ids)
        if not cg:
            raise HTTPException(status_code=400,
                                detail=f"No camera group found with specified camera IDs: {request.camera_ids}. Create a camera group first.")
        else:
            pipeline_config = request.pipeline_config or PipelineConfig.from_camera_configs(camera_configs=cg.configs)
            camera_group_id, pipeline_id = get_freemocap_app().connect_pipeline(camera_group=cg,
                                                                                pipeline_config=pipeline_config)
            response = PipelineCreateResponse(camera_group_id=camera_group_id,
                                              pipeline_id=pipeline_id)
            logger.api(
                f"`pipeline/connect` POST request handled successfully - \n {response.model_dump_json(indent=2)}")
            return response
    except Exception as e:
        logger.error(f"Error when processing `pipeline/connect` request: {type(e).__name__} - {e}")
        logger.exception(e)
        raise HTTPException(status_code=500,
                            detail=f"Error when processing `pipeline/connect` request: {type(e).__name__} - {e}")


@pipeline_router.get("/disconnect/all",
                     summary="Disconnect/shutdown all processing pipelines"
                     )
def pipeline_disconnect_post_endpoint():
    logger.api(f"Received `pipeline/disconnect` GET request")
    try:

        get_freemocap_app().disconnect_pipeline()
        logger.api(
            f"`pipeline/disconnect` GET request handled successfully ")
    except Exception as e:
        logger.error(f"Error when processing `pipeline/disconnect` request: {type(e).__name__} - {e}")
        logger.exception(e)
        raise HTTPException(status_code=500,
                            detail=f"Error when processing `pipeline/disconnect` request: {type(e).__name__} - {e}")
