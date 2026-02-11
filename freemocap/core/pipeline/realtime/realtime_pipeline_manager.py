"""
RealtimePipelineManager: lifecycle manager for long-lived realtime pipelines.

Each realtime pipeline is bound to a CameraGroup and runs indefinitely,
processing live frames through detection and (optionally) triangulation.

Responsibilities:
  - Creating/finding pipelines by camera ID set
  - Pushing config updates to running pipelines
  - Streaming aggregated frontend payloads
  - Recording orchestration (start/stop across all pipelines)
  - Orderly shutdown
"""
import logging
import multiprocessing
from dataclasses import dataclass, field

from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.ipc.process_management.process_registry import ProcessRegistry
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.core.pipeline.shared.frontend_payload import FrontendPayload
from freemocap.core.pipeline.shared.pipeline_configs import RealtimePipelineConfig
from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt

logger = logging.getLogger(__name__)


@dataclass
class RealtimePipelineManager:
    """
    Manages the lifecycle of realtime (camera-bound) pipelines.

    Each pipeline is a singleton per camera ID set — creating a pipeline
    for an already-tracked camera group returns the existing one (with
    an updated config).
    """

    process_registry: ProcessRegistry
    lock: multiprocessing.Lock = field(default_factory=multiprocessing.Lock)
    pipelines: dict[PipelineIdString, RealtimePipeline] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Pipeline CRUD
    # ------------------------------------------------------------------

    def create_pipeline(
        self,
        *,
        camera_group: CameraGroup,
        pipeline_config: RealtimePipelineConfig,
    ) -> RealtimePipeline:
        with self.lock:
            # Return existing pipeline for this camera set (with updated config)
            for pipeline in self.pipelines.values():
                if set(pipeline.camera_ids) == set(pipeline_config.camera_ids):
                    logger.info(
                        f"Found existing RealtimePipeline [{pipeline.id}] "
                        f"for camera group [{pipeline.camera_group_id}]"
                    )
                    pipeline.update_config(new_config=pipeline_config)
                    return pipeline

            pipeline = RealtimePipeline.create(
                pipeline_config=pipeline_config,
                camera_group=camera_group,
                process_registry=self.process_registry,
            )
            pipeline.start()
            self.pipelines[pipeline.id] = pipeline
            logger.info(
                f"Created RealtimePipeline [{pipeline.id}] "
                f"for camera group [{pipeline.camera_group_id}]"
            )
            return pipeline

    def update_pipeline_config(
        self,
        *,
        pipeline_id: PipelineIdString,
        new_config: RealtimePipelineConfig,
    ) -> RealtimePipeline:
        with self.lock:
            pipeline = self.pipelines.get(pipeline_id)
            if pipeline is None:
                raise KeyError(f"No realtime pipeline with ID '{pipeline_id}'")
            pipeline.update_config(new_config=new_config)
            return pipeline

    def get_pipeline_by_camera_ids(
        self,
        camera_ids: list[CameraIdString],
    ) -> RealtimePipeline | None:
        with self.lock:
            for pipeline in self.pipelines.values():
                if set(pipeline.camera_ids) == set(camera_ids):
                    return pipeline
        return None

    # ------------------------------------------------------------------
    # Frontend payload streaming
    # ------------------------------------------------------------------

    def get_latest_frontend_payloads(
        self,
        if_newer_than: FrameNumberInt,
    ) -> dict[PipelineIdString, tuple[bytes | None, FrontendPayload | None]]:
        latest: dict[PipelineIdString, tuple[bytes | None, FrontendPayload | None]] = {}
        with self.lock:
            for pipeline_id, pipeline in self.pipelines.items():
                output = pipeline.get_latest_frontend_payload(if_newer_than=if_newer_than)
                if output is not None:
                    latest[pipeline_id] = output
        return latest

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def pause_unpause_all(self) -> None:
        with self.lock:
            for pipeline in self.pipelines.values():
                pipeline.camera_group.pause_unpause()

    def shutdown(self) -> None:
        with self.lock:
            for pipeline in self.pipelines.values():
                pipeline.shutdown()
            self.pipelines.clear()
        logger.info("RealtimePipelineManager: all pipelines shut down")
