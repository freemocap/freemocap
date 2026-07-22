import logging

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from skellycam.core.camera_group.camera_group import CameraConfigs
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString

from freemocap.app.freemocap_application import get_freemocap_app
from freemocap.core.pipeline.realtime.realtime_aggregator_node import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.pubsub.pubsub_topics import (
    SkeletonFitterResetMessage,
    SkeletonFitterResetTopic,
    SkeletonFitStateMessage,
)

logger = logging.getLogger(__name__)

realtime_router = APIRouter(prefix="/realtime", tags=["Realtime Processing Pipeline"])


class RealtimePipelineConnectRequest(BaseModel):
    camera_configs: CameraConfigs|None = Field(default=None,
                                               alias="cameraConfigs",
                                               description="Camera configurations for the CameraGroup we're attaching a pipeline to. If None, use existing camera group (or throw if no camera group connected)")
    realtime_camera_ids: list[CameraIdString] | None = Field(
        default=None,
        alias="realtimeCameraIds",
        description="Subset of camera IDs to attach to pipeline nodes. If None, all cameras in the group are used.",
    )
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

class SkeletonFitStateResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    state: str = Field(description="Ritual state: idle | countdown | capturing | fitted")
    countdown_remaining_s: float = Field(alias="countdownRemainingS")
    capture_good_streak: int = Field(alias="captureGoodStreak")
    capture_required_good_frames: int = Field(alias="captureRequiredGoodFrames")
    visible_fraction: float = Field(alias="visibleFraction")
    mean_error_px: float | None = Field(alias="meanErrorPx")
    n_fitted_body_bones: int = Field(alias="nFittedBodyBones")
    median_seed_deviation: float | None = Field(alias="medianSeedDeviation")

    @classmethod
    def from_message(cls, msg: SkeletonFitStateMessage) -> "SkeletonFitStateResponse":
        return cls(
            state=msg.state,
            countdown_remaining_s=msg.countdown_remaining_s,
            capture_good_streak=msg.capture_good_streak,
            capture_required_good_frames=msg.capture_required_good_frames,
            visible_fraction=msg.visible_fraction,
            mean_error_px=msg.mean_error_px,
            n_fitted_body_bones=msg.n_fitted_body_bones,
            median_seed_deviation=msg.median_seed_deviation,
        )


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
                                                                                camera_configs=camera_configs,
                                                                                realtime_camera_ids=request.realtime_camera_ids,)
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


@realtime_router.post(
    "/reset-skeleton-fitter",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Arm the skeleton refit ritual — countdown, quality-gated capture, freeze",
)
async def reset_skeleton_fitter_endpoint() -> None:
    """Arm the segment-fit calibration ritual on every live pipeline.

    Each pipeline's fitter clears its learned bone lengths and enters the ritual:
    a countdown (so the subject can get into view and hold still), a quality-gated
    capture window (only consecutive good frames count), then a freeze that
    re-anchors each bone's trust region on the captured length. Poll
    `GET /realtime/skeleton-fitter-state` for progress. Fire-and-forget: 204 No Content.
    """
    logger.api("Received `realtime/reset-skeleton-fitter` POST request")
    try:
        app = get_freemocap_app()
        reset_count = 0
        for pipeline in app.realtime_pipeline_manager.pipelines.values():
            if pipeline.alive:
                pipeline.pubsub.publish(
                    SkeletonFitterResetTopic,
                    SkeletonFitterResetMessage(),
                )
                reset_count += 1
        logger.api(f"Skeleton fitter reset signal sent to {reset_count} pipeline(s)")
    except Exception as e:
        logger.error(f"Error resetting skeleton fitter: {type(e).__name__} - {e}")
        logger.exception(e)
        raise HTTPException(
            status_code=500,
            detail=f"Error resetting skeleton fitter: {type(e).__name__} - {e}",
        )


@realtime_router.get(
    "/skeleton-fitter-state",
    summary="Current segment-fit ritual state per pipeline (idle/countdown/capturing/fitted)",
)
async def skeleton_fitter_state_endpoint() -> dict[str, SkeletonFitStateResponse | None]:
    """Latest segment-fit ritual state for every live pipeline.

    Values are None for pipelines whose fitter hasn't published a state yet
    (skeleton fitting disabled, or no frames processed since startup).
    """
    logger.api("Received `realtime/skeleton-fitter-state` GET request")
    try:
        app = get_freemocap_app()
        result: dict[str, SkeletonFitStateResponse | None] = {}
        for pipeline in app.realtime_pipeline_manager.pipelines.values():
            state = pipeline.get_latest_skeleton_fit_state()
            result[pipeline.id] = (
                SkeletonFitStateResponse.from_message(state)
                if state is not None
                else None
            )
        return result
    except Exception as e:
        logger.error(f"Error reading skeleton fitter state: {type(e).__name__} - {e}")
        logger.exception(e)
        raise HTTPException(
            status_code=500,
            detail=f"Error reading skeleton fitter state: {type(e).__name__} - {e}",
        )
