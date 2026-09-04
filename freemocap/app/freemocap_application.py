"""
Top-level FreemocapApplication: owns the camera group manager, the realtime and
posthoc pipeline managers, and the worker registry, and orchestrates recording and
calibration/mocap pipeline operations.
"""
import logging
import multiprocessing
from dataclasses import dataclass, field
from multiprocessing.sharedctypes import Synchronized

from fastapi import FastAPI
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group_manager import CameraGroupManager, get_or_create_camera_group_manager
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.posthoc.posthoc_pipeline import PosthocPipeline
from freemocap.core.pipeline.posthoc.posthoc_pipeline_manager import PosthocPipelineManager
from freemocap.core.pipeline.posthoc.sync_job import SyncJob
from freemocap.core.pipeline.posthoc.sync_job_manager import SyncJobManager
from freemocap.core.pipeline.realtime.realtime_aggregator_node import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.core.pipeline.realtime.realtime_pipeline_manager import RealtimePipelineManager
from freemocap.core.tasks.calibration.calibration_task_config import PosthocCalibrationPipelineConfig
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.types.type_overloads import FrameNumberInt
from freemocap.core.pipeline.posthoc.progress_messages import PipelineProgressMessage
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage  # noqa: TC001 — beartype resolves the get_latest_aggregator_outputs return annotation at runtime
from skelly_synchronize.core.models import SyncRequest

logger = logging.getLogger(__name__)


@dataclass
class FreemocapApplication:
    global_kill_flag: Synchronized
    worker_registry: WorkerRegistry
    realtime_pipeline_manager: RealtimePipelineManager
    posthoc_pipeline_manager: PosthocPipelineManager
    sync_job_manager: SyncJobManager
    camera_group_manager: CameraGroupManager

    @classmethod
    def create(cls, fastapi_app: FastAPI) -> "FreemocapApplication":
        global_kill_flag = fastapi_app.state.global_kill_flag
        worker_registry = fastapi_app.state.worker_registry

        return cls(
            global_kill_flag=global_kill_flag,
            worker_registry=worker_registry,
            realtime_pipeline_manager=RealtimePipelineManager(
                worker_registry=worker_registry,
            ),
            posthoc_pipeline_manager=PosthocPipelineManager(
                global_kill_flag=global_kill_flag,
                worker_registry=worker_registry,
            ),
            sync_job_manager=SyncJobManager(
                global_kill_flag=global_kill_flag,
                worker_registry=worker_registry,
            ),
            camera_group_manager=get_or_create_camera_group_manager(app=fastapi_app),
        )

    @property
    def should_continue(self) -> bool:
        return not self.global_kill_flag.value
    # ------------------------------------------------------------------
    # Recording orchestration
    # ------------------------------------------------------------------

    async def start_recording_all(self, recording_info: RecordingInfo) -> None:
        await self.camera_group_manager.start_recording_all_groups(
            recording_info=recording_info,
        )

    async def stop_recording_all(self) -> RecordingInfo | None:
        recording_infos = await self.camera_group_manager.stop_recording_all_groups()
        if len(recording_infos) == 0:
            logger.warning("No recordings were stopped.")
            return None
        if len(recording_infos) > 1:
            raise NotImplementedError(
                "Stopping multiple recordings at once is not supported yet."
            )
        return recording_infos[0][0]

    # ------------------------------------------------------------------
    # Realtime pipeline operations
    # ------------------------------------------------------------------

    async def create_or_update_realtime_pipeline(
            self,
            camera_configs: CameraConfigs,
            pipeline_config: RealtimePipelineConfig,
            realtime_camera_ids: list[CameraIdString] | None = None,
    ) -> RealtimePipeline:

        for pipeline in self.realtime_pipeline_manager.pipelines.values():
            pipeline.update_config(new_config=pipeline_config)
            return pipeline

        camera_group = await self.camera_group_manager.create_or_update_camera_group(
            camera_configs=camera_configs,
        )
        pipeline = self.realtime_pipeline_manager.create_pipeline(
            camera_group=camera_group,
            pipeline_config=pipeline_config,
            realtime_camera_ids=realtime_camera_ids,
        )
        return pipeline

    # ------------------------------------------------------------------
    # Posthoc pipeline operations
    # ------------------------------------------------------------------

    async def create_posthoc_calibration_pipeline(
            self,
            recording_info: RecordingInfo,
            calibration_config: PosthocCalibrationPipelineConfig,
    ) -> PosthocPipeline:
        pipeline = self.posthoc_pipeline_manager.create_calibration_pipeline(
            recording_info=recording_info,
            calibration_config=calibration_config,
        )
        return pipeline

    async def create_posthoc_mocap_pipeline(
            self,
            recording_info: RecordingInfo,
            mocap_config: PosthocMocapPipelineConfig,
    ) -> PosthocPipeline:
        pipeline = self.posthoc_pipeline_manager.create_mocap_pipeline(
            recording_info=recording_info,
            mocap_config=mocap_config,
        )
        return pipeline

    def stop_posthoc_pipeline(self, pipeline_id: str) -> bool:
        return self.posthoc_pipeline_manager.stop_pipeline(pipeline_id)

    def stop_all_posthoc_pipelines(self) -> None:
        self.posthoc_pipeline_manager.stop_all_pipelines()

    # ------------------------------------------------------------------
    # Video synchronization jobs
    # ------------------------------------------------------------------

    def create_sync_job(self, request: SyncRequest) -> SyncJob:
        return self.sync_job_manager.create_job(request=request)

    # ------------------------------------------------------------------
    # Frontend payloads
    # ------------------------------------------------------------------

    async def wait_for_realtime_result(self, timeout: float = 0.5) -> None:
        """Yield until at least one realtime pipeline has a processed frame ready.

        Used by the websocket relay for an event-driven wake-up. Falls back immediately when no pipeline is alive (camera-only or idle mode).
        """
        await self.realtime_pipeline_manager.wait_for_any_result_ready(timeout=timeout)

    def get_latest_aggregator_outputs(
            self,
            if_newer_than: FrameNumberInt,
    ) -> list["AggregationNodeOutputMessage"]:
        """The newest aggregator output per live pipeline (standard-stream frame source)."""
        return self.realtime_pipeline_manager.get_latest_aggregator_outputs(
            if_newer_than=if_newer_than,
        )

    # ------------------------------------------------------------------
    # State projection (websocket APP_STATE snapshot)
    # ------------------------------------------------------------------

    def to_state_dict(self) -> dict:
        """Serializable snapshot of observed server state for the websocket APP_STATE message.

        Superset of skellycam's camera-group state plus the realtime pipelines this app
        owns. The websocket relay adds `server_pid` to the envelope.
        """
        return {
            **self.camera_group_manager.to_state_dict(),
            "realtime_pipelines": [
                {
                    "id": pipeline.id,
                    "camera_group_id": pipeline.camera_group_id,
                    "camera_ids": list(pipeline.camera_ids),
                    "alive": pipeline.alive,
                }
                for pipeline in self.realtime_pipeline_manager.pipelines.values()
            ],
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close_pipelines(self) -> None:
        self.realtime_pipeline_manager.shutdown()
        self.posthoc_pipeline_manager.shutdown()
        self.sync_job_manager.shutdown()

    def pause_unpause_pipelines(self) -> None:
        self.realtime_pipeline_manager.pause_unpause_all()

    def close(self) -> None:
        self.global_kill_flag.value = True
        self.realtime_pipeline_manager.shutdown()
        self.posthoc_pipeline_manager.shutdown()
        self.sync_job_manager.shutdown()


FREEMOCAP_APP: FreemocapApplication | None = None


def create_freemocap_app(fastapi_app: FastAPI) -> FreemocapApplication:
    global FREEMOCAP_APP
    if FREEMOCAP_APP is not None:
        raise RuntimeError("FreemocapApplication already exists!")
    FREEMOCAP_APP = FreemocapApplication.create(fastapi_app=fastapi_app)
    return FREEMOCAP_APP


def get_freemocap_app() -> FreemocapApplication:
    global FREEMOCAP_APP
    if FREEMOCAP_APP is None:
        raise RuntimeError("FreemocapApplication does not exist!")
    return FREEMOCAP_APP
