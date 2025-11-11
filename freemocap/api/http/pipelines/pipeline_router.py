import logging
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Request
from pydantic import BaseModel, Field
from skellycam.core.camera.config.camera_config import CameraConfig
from skellycam.core.camera_group.camera_group import CameraConfigs
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString

from freemocap.app.freemocap_application import get_freemocap_app
from freemocap.core.pipeline.pipeline_configs import RealtimePipelineConfig
from freemocap.system.default_paths import default_recording_name, get_default_recording_folder_path

logger = logging.getLogger(__name__)

pipeline_router = APIRouter(prefix=f"/pipeline",
                            tags=["Processing Pipelines"], )


class PipelineConnectRequest(BaseModel):
    camera_configs: CameraConfigs = Field(...,
                                          description="List of camera IDs comprising the CameraGroup we're attaching a pipeline to")
    pipeline_config: RealtimePipelineConfig | None = None

    @property
    def camera_ids(self) -> list[CameraIdString] | None:
        if self.camera_configs:
            return list(self.camera_configs.keys())
        return None


class PipelineCreateResponse(BaseModel):
    camera_group_id: CameraGroupIdString = Field(..., description="ID of the camera group attached to the pipeline")
    pipeline_id: str = Field(..., description="ID of the processing pipeline to which the camera group is attached")
    camera_configs: CameraConfigs = Field(..., description="Camera configurations for the cameras in the camera group")

    @classmethod
    def from_pipeline(cls, pipeline) -> "PipelineCreateResponse":
        return cls(
            camera_group_id=pipeline.camera_group.id,
            pipeline_id=pipeline.id,
            camera_configs=pipeline.camera_configs,
        )


class StartRecordingRequest(BaseModel):
    recording_name: str = Field(
        default_factory=default_recording_name,
        description="Name of the recording"
    )
    recording_directory: str = Field(
        default_factory=get_default_recording_folder_path,
        description="Path to save the recording"
    )
    mic_device_index: int = Field(
        default=-1,
        description="Index of the microphone device"
    )

    def recording_full_path(self) -> str:
        return str(Path(self.recording_directory) / self.recording_name)


@pipeline_router.post("/connect",
                      summary="Create a processing pipeline and attach it to a camera group"
                      )
async def pipeline_connect_endpoint(
        request: PipelineConnectRequest = Body(...,
                                               description="Request body containing desired camera configuration",
                                               examples=[
                                                   PipelineConnectRequest(camera_configs={
                                                       '0': CameraConfig(camera_id='0')})])) -> PipelineCreateResponse:
    logger.api(f"Received `pipeline/connect` POST request - \n {request.model_dump_json(indent=2)}")
    try:
        pipeline_config = request.pipeline_config or RealtimePipelineConfig.from_camera_configs(
            camera_configs=request.camera_configs)
        pipeline = await get_freemocap_app().create_or_update_realtime_pipeline(pipeline_config=pipeline_config)
        # response = PipelineCreateResponse.from_pipeline(pipeline=pipeline)
        response = PipelineCreateResponse(pipeline_id='nononone',
                                            camera_group_id='nononone',
                                            camera_configs=request.camera_configs)
        logger.api(
            f"`pipeline/connect` POST request handled successfully - \n {response.model_dump_json(indent=2)}")
        return response
    except Exception as e:
        logger.error(f"Error when processing `pipeline/connect` request: {type(e).__name__} - {e}")
        logger.exception(e)
        raise HTTPException(status_code=500,
                            detail=f"Error when processing `pipeline/connect` request: {type(e).__name__} - {e}")


@pipeline_router.delete("/all/close",
                        summary="Disconnect/shutdown all processing pipelines"
                        )
async def pipeline_close_endpoint():
    logger.api(f"Received `pipeline/close` DELETE request")
    try:

        get_freemocap_app().close_pipelines()
        logger.api(
            f"`pipeline/disconnect` DELETE request handled successfully ")
    except Exception as e:
        logger.error(f"Error when processing `pipeline/disconnect` request: {type(e).__name__} - {e}")
        logger.exception(e)
        raise HTTPException(status_code=500,
                            detail=f"Error when processing `pipeline/disconnect` request: {type(e).__name__} - {e}")


@pipeline_router.get("/all/pause_unpause", summary="Pause/unpause cameras")
def pause_camera_groups(request: Request) -> bool:
    try:
        get_freemocap_app().pause_unpause_pipelines()
        return True
    except Exception as e:
        logger.error(f"Error in {request.url}: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@pipeline_router.post("/all/record/start", summary="Start recording")
def start_recording(
        request: Request,
        request_body: StartRecordingRequest = Body(..., examples=[StartRecordingRequest()])
) -> bool:
    try:
        if request_body.recording_directory.startswith("~"):
            request_body.recording_directory = str(
                Path(request_body.recording_directory.replace("~", str(Path.home()), 1))
            )

        Path(request_body.recording_directory).mkdir(parents=True, exist_ok=True)
        get_freemocap_app().start_recording_all(RecordingInfo(**request_body.model_dump()))

        return True
    except Exception as e:
        logger.error(f"Error in {request.url}: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@pipeline_router.get("/all/record/stop", summary="Stop recording")
def stop_recording(request: Request) -> bool:
    try:
        get_freemocap_app().stop_recording_all()
        return True
    except Exception as e:
        logger.error(f"Error in {request.url}: {type(e).__name__} - {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
