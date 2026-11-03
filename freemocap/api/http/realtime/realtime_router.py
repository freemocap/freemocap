import logging
from typing import Literal

from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from skellycam.core.camera_group.camera_group import CameraConfigs
from skellycam.core.types.type_overloads import CameraGroupIdString, CameraIdString

from freemocap.app.freemocap_application import RealtimeStartupConfigurationError, RealtimeStartupStopped, get_freemocap_app
from freemocap.core.pipeline.realtime.realtime_aggregator_node import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.core.tasks.mocap.realtime_filtering.realtime_filter_config import RealtimeFilterConfig
from freemocap.pubsub.pubsub_topics import (
    SkeletonFitterResetMessage,
    SkeletonFitterResetTopic,
)

logger = logging.getLogger(__name__)

realtime_router = APIRouter(prefix="/realtime", tags=["Realtime processing"])


class RealtimeStartupResponse(BaseModel):
    status: Literal["idle", "running", "stopping", "ready", "failed", "stopped"]
    phase: str
    elapsed_seconds: float
    phase_elapsed_seconds: float
    pipeline_id: str | None = None
    message: str | None = None
    error: str | None = None
    delayed: bool = False
    preview_ready: bool = False


@realtime_router.get("/startup", operation_id="realtime_startup_status")
def realtime_startup_status() -> RealtimeStartupResponse:
    """Observe startup without waiting for camera or native inference operations."""
    app = get_freemocap_app()
    snapshot = app.startup_status.snapshot()
    if snapshot["pipeline_id"] and snapshot["status"] == "running":
        inference = app.inference_service.startup_status(snapshot["pipeline_id"])
        if inference is not None:
            app.startup_status.observe_inference(
                snapshot["pipeline_id"], **{key: inference[key] for key in (
                    "status", "phase", "phase_elapsed_seconds", "message", "error",
                )},
            )
            snapshot = app.startup_status.snapshot()
    snapshot["delayed"] = snapshot["status"] in ("running", "stopping") and snapshot["phase_elapsed_seconds"] >= 15
    return RealtimeStartupResponse(**snapshot)


@realtime_router.post("/startup/stop", operation_id="stop_realtime_startup")
async def stop_realtime_startup() -> RealtimeStartupResponse:
    """Request a safe stop; native work remains owned until its boundary/cleanup."""
    await get_freemocap_app().stop_realtime_startup()
    return realtime_startup_status()


class TemporalConfigStatus(BaseModel):
    defaults: RealtimeFilterConfig = Field(default_factory=RealtimeFilterConfig)
    requested: RealtimeFilterConfig | None = None
    applied: RealtimeFilterConfig | None = None


def _running_pipeline() -> RealtimePipeline | None:
    pipelines = [pipeline for pipeline in get_freemocap_app().realtime_pipeline_manager.pipelines.values() if pipeline.alive]
    if len(pipelines) > 1:
        raise HTTPException(status_code=409, detail="Multiple running pipelines require an explicit pipeline selection")
    return pipelines[0] if pipelines else None


@realtime_router.get("/filter-config")
def temporal_config_status() -> TemporalConfigStatus:
    pipeline = _running_pipeline()
    return TemporalConfigStatus(
        requested=pipeline.config.aggregator_config.realtime_filter_config if pipeline else None,
        applied=pipeline.applied_filter_config if pipeline else None,
    )


@realtime_router.put("/filter-config")
def update_temporal_config(config: RealtimeFilterConfig) -> TemporalConfigStatus:
    """Update numerical processing without reconnecting or configuring cameras.

    Applied values come from a completed worker frame, not the outgoing command.
    Clients can poll GET while awaiting the next processed frame.
    """
    pipeline = _running_pipeline()
    if pipeline is None:
        raise HTTPException(status_code=409, detail="No running realtime pipeline")
    updated = pipeline.config.model_copy(deep=True)
    updated.aggregator_config.realtime_filter_config = config
    try:
        pipeline.update_config(updated)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return temporal_config_status()


@realtime_router.get("/config", response_model_by_alias=False)
def running_pipeline_config() -> RealtimePipelineConfig | None:
    """Read the running configuration without applying client defaults."""
    pipelines = [pipeline for pipeline in get_freemocap_app().realtime_pipeline_manager.pipelines.values() if pipeline.alive]
    if len(pipelines) > 1:
        raise HTTPException(status_code=409, detail="Multiple running pipelines require an explicit pipeline selection")
    return pipelines[0].config if pipelines else None


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
    resolved_config: RealtimePipelineConfig
    camera_group_id: CameraGroupIdString = Field(
        description="ID of the camera group attached to the pipeline",
    )
    pipeline_id: str = Field(
        description="ID of the processing pipeline",
    )
    @classmethod
    def from_pipeline(cls, pipeline: RealtimePipeline) -> "RealtimePipelineCreateResponse":
        return cls(
            resolved_config=pipeline.config,
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
                                                                                camera_configs=camera_configs,
                                                                                realtime_camera_ids=request.realtime_camera_ids,)
        response = RealtimePipelineCreateResponse.from_pipeline(pipeline=pipeline)
        logger.api(f"`pipeline/connect` POST request handled successfully - \n {response.model_dump_json(indent=2)}")
        return response
    except RealtimeStartupConfigurationError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except RealtimeStartupStopped as error:
        raise HTTPException(status_code=409, detail={"code": "startup_stopped", "message": str(error)}) from error
    except Exception as e:
        logger.error(f"Error when processing `pipeline/connect` request: {type(e).__name__} - {e}")
        logger.exception(e)
        raise HTTPException(
            status_code=500,
            detail=f"Error when processing `pipeline/connect` request: {type(e).__name__} - {e}",
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
    re-anchors each bone's trust region on the captured length. Observe fitter state in WebSocket frames. The command returns 204 No Content.
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


# These commands stop the same realtime manager used by apply/config.
from freemocap.api.http.mocap.mocap_router import cancel_realtime_pipeline, cancel_realtime_pipelines

realtime_router.add_api_route('/pipelines/{pipeline_id}', cancel_realtime_pipeline, methods=['DELETE'],
                              operation_id='stop_realtime_pipeline')
realtime_router.add_api_route('/pipelines', cancel_realtime_pipelines, methods=['DELETE'],
                              operation_id='stop_realtime_pipelines')
