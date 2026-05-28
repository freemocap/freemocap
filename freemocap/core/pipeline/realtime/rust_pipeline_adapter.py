"""
RustRealtimeEngine + RustRealtimePipeline: thin adapters around _freemocap_rust.

RustRealtimeEngine wraps _freemocap_rust.RealtimeEngine (a single PyO3 class
bundling camera management + pipeline management). It matches the duck-typed
interface of RealtimeEngine, so FreemocapApplication can swap between them
via USE_RUST_BACKEND.

RustRealtimePipeline wraps a single pipeline ID within the Rust engine, matching
the interface of RealtimePipeline for duck-typed interchangeability.
"""
import asyncio
import logging
import os
import uuid
from dataclasses import dataclass
from typing import Optional

from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.realtime.realtime_aggregator_node import RealtimePipelineConfig
from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt
from freemocap.core.viz.frontend_payload import FrontendImagePacket, FrontendPayload

logger = logging.getLogger(__name__)

_native = None


def _get_native():
    """Lazy-import _freemocap_rust with OpenCV DLL discovery."""
    global _native
    if _native is not None:
        return _native

    opencv_bin = "C:/tools/opencv/build/x64/vc16/bin"
    if os.path.isdir(opencv_bin):
        os.add_dll_directory(opencv_bin)

    import _freemocap_rust

    _native = _freemocap_rust
    return _native


# ── CameraGroup handle ───────────────────────────────────────────────────────

@dataclass
class RustCameraGroupHandle:
    """Thin wrapper around a Rust-managed camera group ID.

    Returned by RustRealtimeEngine.create_or_update_camera_group().
    Mimics the subset of CameraGroup's interface that the pipeline flow uses.
    """

    _id: str
    _configs: CameraConfigs
    _engine: "freemocap.core.pipeline.realtime.rust_pipeline_adapter.RustRealtimeEngine"

    @property
    def id(self) -> str:
        return self._id

    @property
    def configs(self) -> CameraConfigs:
        return self._configs

    @property
    def camera_ids(self) -> list[str]:
        return list(self._configs.keys())


# ── RealtimeEngine ───────────────────────────────────────────────────────────

class RustRealtimeEngine:
    """Wraps _freemocap_rust.RealtimeEngine — matches RealtimeEngine interface.

    Interface:
      - create_or_update_camera_group(camera_configs) → RustCameraGroupHandle (async)
      - create_pipeline(*, camera_group, pipeline_config, realtime_camera_ids) → RustRealtimePipeline
      - pipelines → dict[str, RustRealtimePipeline] (property)
      - wait_for_any_result_ready(timeout) → None (async)
      - get_latest_frontend_payloads(if_newer_than) → list[FrontendImagePacket]
      - start_recording_all(recording_info) → None (async)
      - stop_recording_all() → list (async)
      - pause_unpause_all() → None
      - shutdown() → None
      - camera_groups → dict (property)
    """

    def __init__(self) -> None:
        native = _get_native()
        self._native = native.RealtimeEngine()
        self._pipelines: dict[PipelineIdString, RustRealtimePipeline] = {}
        self._camera_groups: dict[str, RustCameraGroupHandle] = {}

    # ── Camera group ──────────────────────────────────────────────────────

    async def create_or_update_camera_group(
        self, camera_configs: CameraConfigs
    ) -> RustCameraGroupHandle:
        # Convert CameraConfigs to plain dict the Rust side can parse
        configs_dict = {
            cam_id: cfg.model_dump() if hasattr(cfg, "model_dump") else cfg
            for cam_id, cfg in camera_configs.items()
        }
        group_id = self._native.create_or_update_camera_group(configs_dict)

        handle = RustCameraGroupHandle(
            _id=group_id,
            _configs=camera_configs,
            _engine=self,
        )
        self._camera_groups[group_id] = handle
        logger.info("RustRealtimeEngine: created camera group [%s]", group_id)
        return handle

    @property
    def camera_groups(self) -> dict[str, RustCameraGroupHandle]:
        return self._camera_groups

    # ── Pipeline ──────────────────────────────────────────────────────────

    def create_pipeline(
        self,
        *,
        camera_group: RustCameraGroupHandle,
        pipeline_config: RealtimePipelineConfig,
        realtime_camera_ids: list[CameraIdString] | None = None,
    ) -> "freemocap.core.pipeline.realtime.rust_pipeline_adapter.RustRealtimePipeline":
        cam_ids = realtime_camera_ids or list(camera_group.configs.keys())
        config_json = pipeline_config.model_dump_json()

        calibration_toml_path = getattr(
            pipeline_config.aggregator_config, "calibration_toml_path", None
        )

        pipeline_id = self._native.create_pipeline(
            camera_group.id,
            config_json,
            cam_ids,
            calibration_toml_path=calibration_toml_path,
        )

        pipeline = RustRealtimePipeline(
            engine=self,
            pipeline_id=pipeline_id,
            camera_group=camera_group,
            camera_ids=cam_ids,
        )
        self._pipelines[pipeline_id] = pipeline
        logger.info(
            "RustRealtimeEngine: created pipeline [%s] for group [%s]",
            pipeline_id, camera_group.id,
        )
        return pipeline

    @property
    def pipelines(self) -> dict[PipelineIdString, "freemocap.core.pipeline.realtime.rust_pipeline_adapter.RustRealtimePipeline"]:
        return self._pipelines

    # ── Event-driven wake-up ──────────────────────────────────────────────

    async def wait_for_any_result_ready(self, timeout: float = 0.5) -> None:
        if not self._pipelines:
            await asyncio.sleep(0.01)
            return
        await asyncio.to_thread(
            self._native.wait_for_any_result_ready, timeout
        )

    # ── Frame output ──────────────────────────────────────────────────────

    def get_latest_frontend_payloads(
        self, if_newer_than: FrameNumberInt
    ) -> list[FrontendImagePacket]:
        raw_list = self._native.get_latest_frontend_payloads(if_newer_than)

        results: list[FrontendImagePacket] = []
        for output in raw_list:
            frame_number = output["frame_number"]

            pkt = FrontendImagePacket(
                images_bytearray=bytearray(output.get("images_bytearray", b"")),
                multiframe_timestamp=output.get("multiframe_timestamp", 0.0),
                frontend_payload=FrontendPayload(
                    frame_number=frame_number,
                    camera_group_id=output.get("camera_group_id", "unknown"),
                    pipeline_id=output.get("pipeline_id"),
                ),
            )
            # Attach keypoints if present
            if output.get("keypoints_raw"):
                pkt.frontend_payload.keypoints_raw = output["keypoints_raw"]
            if output.get("keypoints_filtered"):
                pkt.frontend_payload.keypoints_filtered = output["keypoints_filtered"]

            results.append(pkt)

        return results

    # ── Recording ─────────────────────────────────────────────────────────

    async def start_recording_all(self, recording_info: RecordingInfo) -> None:
        output_dir = str(recording_info.full_recording_path)
        label = recording_info.recording_name
        self._native.start_recording_all(output_dir, label=label)

    async def stop_recording_all(self) -> list:
        result = self._native.stop_recording_all()
        summaries: list = []
        for group_id, summary_dict in result.items():
            output_dir = summary_dict.get("output_dir", "")
            recording_info = RecordingInfo(
                recording_name=summary_dict.get("output_dir", group_id),
                recording_directory=os.path.dirname(output_dir) if output_dir else ".",
            )
            summaries.append((recording_info, {}))
        return summaries

    # ── Pause ─────────────────────────────────────────────────────────────

    def pause_unpause_all(self) -> None:
        self._native.pause_unpause_all()

    # ── Shutdown ──────────────────────────────────────────────────────────

    def shutdown(self) -> None:
        self._native.shutdown()
        self._pipelines.clear()
        self._camera_groups.clear()
        logger.info("RustRealtimeEngine: shutdown complete")


# ── Per-pipeline adapter ─────────────────────────────────────────────────────

class RustRealtimePipeline:
    """Wraps a single pipeline inside RustRealtimeEngine.

    Matches the interface of RealtimePipeline so it can be stored in the
    same pipelines dict and called by the manager identically.
    """

    def __init__(
        self,
        *,
        engine: RustRealtimeEngine,
        pipeline_id: str,
        camera_group: RustCameraGroupHandle,
        camera_ids: list[str],
    ) -> None:
        self._engine = engine
        self._id: PipelineIdString = pipeline_id
        self._camera_group = camera_group
        self._camera_ids = camera_ids

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def id(self) -> PipelineIdString:
        return self._id

    @property
    def camera_group(self) -> RustCameraGroupHandle:
        return self._camera_group

    @property
    def camera_ids(self) -> list[str]:
        return self._camera_ids

    @property
    def camera_group_id(self) -> str:
        return self._camera_group.id

    @property
    def alive(self) -> bool:
        return self._engine._native.pipeline_alive(self._id)

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> None:
        pass  # Pipeline is started during create_pipeline in Rust

    def shutdown(self) -> None:
        logger.info("RustRealtimePipeline [%s]: shutting down", self._id)
        self._engine._native.shutdown_pipeline(self._id)
        self._engine._pipelines.pop(self._id, None)

    # ── Config ────────────────────────────────────────────────────────────

    def update_config(self, new_config: RealtimePipelineConfig) -> None:
        self._engine._native.update_pipeline_config(
            self._id, new_config.model_dump_json()
        )

    # ── Frontend payload ──────────────────────────────────────────────────

    def get_latest_frontend_payload(
        self, if_newer_than: FrameNumberInt
    ) -> Optional[FrontendImagePacket]:
        output = self._engine._native.get_pipeline_output(self._id, if_newer_than)
        if output is None:
            return None

        frame_number = output["frame_number"]

        pkt = FrontendImagePacket(
            images_bytearray=bytearray(output.get("images_bytearray", b"")),
            multiframe_timestamp=output.get("multiframe_timestamp", 0.0),
            frontend_payload=FrontendPayload(
                frame_number=frame_number,
                camera_group_id=output.get("camera_group_id", self.camera_group_id),
                pipeline_id=output.get("pipeline_id", self._id),
            ),
        )
        if output.get("keypoints_raw"):
            pkt.frontend_payload.keypoints_raw = output["keypoints_raw"]
        if output.get("keypoints_filtered"):
            pkt.frontend_payload.keypoints_filtered = output["keypoints_filtered"]
        return pkt

    # ── Event wait ────────────────────────────────────────────────────────

    async def wait_for_result_ready(self, timeout: float) -> bool:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self._engine._native.wait_for_any_result_ready(timeout),
        )

    # ── Camera configs ────────────────────────────────────────────────────

    async def update_camera_configs(
        self, camera_configs: CameraConfigs
    ) -> CameraConfigs:
        # Camera settings are managed by the engine's camera group.
        # For now, return the existing configs since the Rust engine
        # doesn't support per-camera config updates via this path.
        return self._camera_group.configs
