"""
FreemocapApplication with RealtimeEngine integration.

The realtime engine bundles camera management + real-time pipeline management
behind a single interface. Swap between Python and Rust implementations by
flipping USE_RUST_BACKEND.
"""
import logging
from dataclasses import dataclass
from multiprocessing.sharedctypes import Synchronized

from fastapi import FastAPI
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.posthoc.posthoc_pipeline import PosthocPipeline
from freemocap.core.pipeline.posthoc.posthoc_pipeline_manager import PosthocPipelineManager
from freemocap.core.pipeline.realtime.realtime_aggregator_node import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.core.pipeline.realtime.realtime_engine import RealtimeEngine
from freemocap.core.pipeline.realtime.rust_pipeline_adapter import RustRealtimeEngine, RustRealtimePipeline
from freemocap.core.tasks.calibration.calibration_task_config import PosthocCalibrationPipelineConfig
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.types.type_overloads import FrameNumberInt
from freemocap.core.viz.frontend_payload import FrontendImagePacket
from freemocap.core.pipeline.posthoc.progress_messages import PipelineProgressMessage

logger = logging.getLogger(__name__)

# ── Backend selection ─────────────────────────────────────────────────────
# Flip to True to use the Rust real-time engine (_freemocap_rust.RealtimeEngine).
# Requires: maturin develop (builds _freemocap_rust.pyd)
#           _skellycam_rust (for camera capture via PyO3CameraGroupManager)
USE_RUST_BACKEND: bool = True


@dataclass
class FreemocapApplication:
    global_kill_flag: Synchronized
    worker_registry: WorkerRegistry
    realtime_engine: RealtimeEngine | RustRealtimeEngine  # cameras + realtime pipeline (bundled)
    posthoc_pipeline_manager: PosthocPipelineManager  # unchanged — disk-based, fire-and-forget

    @classmethod
    def create(cls, fastapi_app: FastAPI) -> "FreemocapApplication":
        global_kill_flag = fastapi_app.state.global_kill_flag
        worker_registry = fastapi_app.state.worker_registry

        if USE_RUST_BACKEND:
            logger.info("Using RUST real-time engine backend.")
            engine = RustRealtimeEngine()
        else:
            logger.info("Using PYTHON real-time engine backend.")
            engine = RealtimeEngine(
                worker_registry=worker_registry,
                fastapi_app=fastapi_app,
            )

        return cls(
            global_kill_flag=global_kill_flag,
            worker_registry=worker_registry,
            realtime_engine=engine,
            posthoc_pipeline_manager=PosthocPipelineManager(
                global_kill_flag=global_kill_flag,
                worker_registry=worker_registry,
            ),
        )

    @property
    def should_continue(self) -> bool:
        return not self.global_kill_flag.value

    # ------------------------------------------------------------------
    # Recording orchestration
    # ------------------------------------------------------------------

    async def start_recording_all(self, recording_info: RecordingInfo) -> None:
        await self.realtime_engine.start_recording_all(recording_info=recording_info)

    async def stop_recording_all(self) -> RecordingInfo | None:
        recording_infos = await self.realtime_engine.stop_recording_all()
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
    ) -> "RealtimePipeline | RustRealtimePipeline":
        for pipeline in self.realtime_engine.pipelines.values():
            pipeline.update_config(new_config=pipeline_config)
            return pipeline

        camera_group = await self.realtime_engine.create_or_update_camera_group(
            camera_configs=camera_configs,
        )
        pipeline = self.realtime_engine.create_pipeline(
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
        return self.posthoc_pipeline_manager.create_calibration_pipeline(
            recording_info=recording_info,
            calibration_config=calibration_config,
        )

    async def create_posthoc_mocap_pipeline(
        self,
        recording_info: RecordingInfo,
        mocap_config: PosthocMocapPipelineConfig,
    ) -> PosthocPipeline:
        return self.posthoc_pipeline_manager.create_mocap_pipeline(
            recording_info=recording_info,
            mocap_config=mocap_config,
        )

    def stop_posthoc_pipeline(self, pipeline_id: str) -> bool:
        return self.posthoc_pipeline_manager.stop_pipeline(pipeline_id)

    def stop_all_posthoc_pipelines(self) -> None:
        self.posthoc_pipeline_manager.stop_all_pipelines()

    # ------------------------------------------------------------------
    # Frontend payloads
    # ------------------------------------------------------------------

    async def wait_for_realtime_result(self, timeout: float = 0.5) -> None:
        await self.realtime_engine.wait_for_any_result_ready(timeout=timeout)

    def get_latest_frontend_payloads(
        self,
        if_newer_than: FrameNumberInt,
    ) -> tuple[list[FrontendImagePacket], list[PipelineProgressMessage]]:
        posthoc_progress = self.posthoc_pipeline_manager.get_progress_updates()
        posthoc_progress.extend(self.posthoc_pipeline_manager.evict_completed())

        realtime_packets = self.realtime_engine.get_latest_frontend_payloads(
            if_newer_than=if_newer_than,
        )
        return realtime_packets, posthoc_progress

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close_pipelines(self) -> None:
        self.realtime_engine.shutdown()
        self.posthoc_pipeline_manager.shutdown()

    def pause_unpause_pipelines(self) -> None:
        self.realtime_engine.pause_unpause_all()

    def close(self) -> None:
        self.global_kill_flag.value = True
        self.realtime_engine.shutdown()
        self.posthoc_pipeline_manager.shutdown()


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
