"""
FreemocapApplication with SettingsManager integration.

"""
import logging
import multiprocessing
import time
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
from freemocap.core.pipeline.realtime.realtime_aggregator_node import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.core.pipeline.realtime.realtime_pipeline_manager import RealtimePipelineManager
from freemocap.core.tasks.calibration.calibration_task_config import PosthocCalibrationPipelineConfig
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.types.type_overloads import FrameNumberInt
from freemocap.core.viz.frontend_payload import FrontendImagePacket, FrontendPayload
from freemocap.core.pipeline.posthoc.progress_messages import PipelineProgressMessage
from freemocap.core.pupil.pupil_labs_config import PupilLabsConfig
from freemocap.core.pupil.pupil_labs_manager import PupilLabsManager

logger = logging.getLogger(__name__)

# Maximum frame rate for pupil-only payloads when no cameras are connected.
_PUPIL_ONLY_MIN_INTERVAL: float = 1.0 / 60.0  # 60 fps max

# Dummy camera group id used for pupil-only frontend payloads.
_PUPIL_ONLY_CAMERA_GROUP_ID: str = "pupil_only"


@dataclass
class FreemocapApplication:
    global_kill_flag: Synchronized
    worker_registry: WorkerRegistry
    realtime_pipeline_manager: RealtimePipelineManager
    posthoc_pipeline_manager: PosthocPipelineManager
    camera_group_manager: CameraGroupManager
    pupil_labs_manager: PupilLabsManager

    # Pupil-only streaming state (used when no cameras are connected).
    _pupil_only_frame_number: int = 0
    _last_pupil_only_send_time: float = 0.0

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
            camera_group_manager=get_or_create_camera_group_manager(app=fastapi_app),
            pupil_labs_manager=PupilLabsManager(
                config=PupilLabsConfig(),
            ),
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
        if recording_info.full_recording_path is not None:
            self.pupil_labs_manager.trigger_recording_start(
                recording_info.full_recording_path
            )

    async def stop_recording_all(self) -> RecordingInfo | None:
        recording_infos = await self.camera_group_manager.stop_recording_all_groups()
        self.pupil_labs_manager.trigger_recording_stop()
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
    # Frontend payloads
    # ------------------------------------------------------------------

    async def wait_for_realtime_result(self, timeout: float = 0.5) -> None:
        """Yield until at least one realtime pipeline has a processed frame ready.

        Used by the websocket relay for an event-driven wake-up. Falls back immediately when no pipeline is alive (camera-only or idle mode).
        """
        await self.realtime_pipeline_manager.wait_for_any_result_ready(timeout=timeout)

    @property
    def pupil_data_available(self) -> bool:
        """True if the Pupil Labs bridge is connected and has streamed data."""
        return self.pupil_labs_manager.connected

    def get_latest_frontend_payloads(
            self,
            if_newer_than: FrameNumberInt,
    ) -> tuple[list[FrontendImagePacket], list[PipelineProgressMessage]]:
        # Drain BEFORE evicting so terminal COMPLETE/FAILED messages aren't lost
        posthoc_progress = self.posthoc_pipeline_manager.get_progress_updates()
        posthoc_progress.extend(self.posthoc_pipeline_manager.evict_completed())

        # Fetch median pupil data once per camera frame
        pupil_data = self.pupil_labs_manager.get_median_pupil_data()

        realtime_pipelines = self.realtime_pipeline_manager.pipelines
        active_pipelines = [p for p in realtime_pipelines.values() if p.alive]

        if not active_pipelines:
            # Camera-only / posthoc-only path
            results: list[FrontendImagePacket] = []
            for cg_id, payload in self.camera_group_manager.get_latest_frontend_payloads(
                    if_newer_than=if_newer_than
            ).items():
                frame_number, mf_timestamp, image_bytes = payload  # unpack the known tuple shape
                results.append(FrontendImagePacket(
                    images_bytearray=image_bytes,
                    multiframe_timestamp=mf_timestamp,
                    frontend_payload=FrontendPayload(
                        camera_group_id=cg_id,
                        frame_number=frame_number,
                        pupil_data=pupil_data,
                    ),
                ))

            # --- Pupil-only fallback: no cameras connected, but pupil data exists ---
            if not results and pupil_data is not None:
                now = time.perf_counter()
                if now - self._last_pupil_only_send_time >= _PUPIL_ONLY_MIN_INTERVAL:
                    self._last_pupil_only_send_time = now
                    self._pupil_only_frame_number += 1
                    results.append(FrontendImagePacket(
                        images_bytearray=bytearray(),  # no image
                        multiframe_timestamp=float(time.perf_counter_ns()),
                        frontend_payload=FrontendPayload(
                            camera_group_id=_PUPIL_ONLY_CAMERA_GROUP_ID,
                            frame_number=self._pupil_only_frame_number,
                            pupil_data=pupil_data,
                        ),
                    ))
                    logger.trace(
                        f"Pupil-only payload sent "
                        f"(frame={self._pupil_only_frame_number})"
                    )

            return results, posthoc_progress

        # Realtime pipeline path — delegate to manager, which also returns FrontendImagePacket
        realtime_pipeline_packets = self.realtime_pipeline_manager.get_latest_frontend_payloads(
            if_newer_than=if_newer_than
        )

        # Attach median pupil data to each frontend payload
        for packet in realtime_pipeline_packets:
            packet.frontend_payload.pupil_data = pupil_data

        return realtime_pipeline_packets, posthoc_progress

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close_pipelines(self) -> None:
        self.realtime_pipeline_manager.shutdown()
        self.posthoc_pipeline_manager.shutdown()
        self.pupil_labs_manager.stop_bridge()

    def pause_unpause_pipelines(self) -> None:
        self.realtime_pipeline_manager.pause_unpause_all()

    def close(self) -> None:
        self.global_kill_flag.value = True
        self.realtime_pipeline_manager.shutdown()
        self.posthoc_pipeline_manager.shutdown()
        self.pupil_labs_manager.stop_bridge()


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
