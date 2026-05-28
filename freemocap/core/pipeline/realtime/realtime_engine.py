"""
RealtimeEngine — unified camera capture + real-time pipeline management.

Two implementations share this duck-typed interface:
- RealtimeEngine (this class) — wraps CameraGroupManager + RealtimePipelineManager
  as private implementation details; no external code accesses them directly.
- RustRealtimeEngine — wraps _freemocap_rust.RealtimeEngine (single PyO3 class).

Swap between them via USE_RUST_BACKEND in freemocap_application.py.
"""

import logging
from typing import TYPE_CHECKING

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.camera_group.camera_group_manager import (
    CameraGroupManager,
    get_or_create_camera_group_manager,
)
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.timestamps.recording_timestamp_stats import RecordingTimestampsStats
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.realtime.realtime_aggregator_node import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.core.pipeline.realtime.realtime_pipeline_manager import RealtimePipelineManager
from freemocap.core.types.type_overloads import FrameNumberInt
from freemocap.core.viz.frontend_payload import FrontendImagePacket, FrontendPayload

if TYPE_CHECKING:
    from freemocap.core.pipeline.realtime.rust_pipeline_adapter import RustRealtimePipeline

logger = logging.getLogger(__name__)


class RealtimeEngine:
    """Wraps CameraGroupManager + RealtimePipelineManager as private implementation details.

    All external code interacts through this engine, never through the managers
    directly. The managers are internal state, not accessible singletons.
    """

    def __init__(self, *, worker_registry: WorkerRegistry, fastapi_app) -> None:
        self._camera_mgr: CameraGroupManager = get_or_create_camera_group_manager(
            app=fastapi_app,
        )
        self._pipeline_mgr: RealtimePipelineManager = RealtimePipelineManager(
            worker_registry=worker_registry,
        )

    # ── Camera groups (for direct access by route handlers) ──────────────

    @property
    def camera_groups(self) -> dict:
        return self._camera_mgr.camera_groups

    # ── Camera group ──────────────────────────────────────────────────────

    async def create_or_update_camera_group(
        self, camera_configs: CameraConfigs
    ) -> CameraGroup:
        return await self._camera_mgr.create_or_update_camera_group(
            camera_configs=camera_configs,
        )

    # ── Pipeline ──────────────────────────────────────────────────────────

    def create_pipeline(
        self,
        *,
        camera_group: CameraGroup,
        pipeline_config: RealtimePipelineConfig,
        realtime_camera_ids: list[CameraIdString] | None = None,
    ) -> RealtimePipeline:
        return self._pipeline_mgr.create_pipeline(
            camera_group=camera_group,
            pipeline_config=pipeline_config,
            realtime_camera_ids=realtime_camera_ids,
        )

    @property
    def pipelines(self) -> dict[str, RealtimePipeline]:
        return self._pipeline_mgr.pipelines

    # ── Event-driven wake-up ──────────────────────────────────────────────

    async def wait_for_any_result_ready(self, timeout: float = 0.5) -> None:
        await self._pipeline_mgr.wait_for_any_result_ready(timeout=timeout)

    # ── Frame output ──────────────────────────────────────────────────────

    def get_latest_frontend_payloads(
        self, if_newer_than: FrameNumberInt
    ) -> list[FrontendImagePacket]:
        """Unified frame output -- pipelines if alive, else camera-only raw frames."""

        active_pipelines = [p for p in self._pipeline_mgr.pipelines.values() if p.alive]

        if not active_pipelines:
            # Camera-only path — wrap raw tuples in FrontendImagePacket
            results: list[FrontendImagePacket] = []
            for cg_id, payload in self._camera_mgr.get_latest_frontend_payloads(
                if_newer_than=if_newer_than
            ).items():
                frame_number, mf_timestamp, image_bytes = payload
                results.append(
                    FrontendImagePacket(
                        images_bytearray=image_bytes,
                        multiframe_timestamp=mf_timestamp,
                        frontend_payload=FrontendPayload(
                            camera_group_id=cg_id, frame_number=frame_number
                        ),
                    )
                )
            return results

        # Pipeline path — manager already returns list[FrontendImagePacket]
        return self._pipeline_mgr.get_latest_frontend_payloads(
            if_newer_than=if_newer_than
        )

    # ── Recording ─────────────────────────────────────────────────────────

    async def start_recording_all(self, recording_info: RecordingInfo) -> None:
        await self._camera_mgr.start_recording_all_groups(
            recording_info=recording_info,
        )

    async def stop_recording_all(
        self,
    ) -> list[tuple[RecordingInfo, RecordingTimestampsStats]]:
        return await self._camera_mgr.stop_recording_all_groups()

    # ── Pause ─────────────────────────────────────────────────────────────

    def pause_unpause_all(self) -> None:
        self._pipeline_mgr.pause_unpause_all()

    # ── Shutdown ──────────────────────────────────────────────────────────

    def shutdown(self) -> None:
        self._pipeline_mgr.shutdown()
