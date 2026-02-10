"""
PipelineManager: unified manager for realtime and posthoc pipelines.

Replaces RealtimePipelineManager and PosthocPipelineManager.

Provides:
  - Factory methods for creating pipelines of each type
  - A background reaper thread that detects dead posthoc pipelines and
    cleans them up (with warnings if they died dirty)
  - Shutdown methods for orderly teardown
"""
import functools
import logging
import multiprocessing
import threading
from copy import deepcopy
from dataclasses import dataclass, field

from fastapi import FastAPI
from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.pipeline_configs import (
    CalibrationPipelineConfig,
    MocapPipelineConfig,
    RealtimePipelineConfig,
)
from freemocap.core.pipeline.frontend_payload import FrontendPayload
from freemocap.core.pipeline.posthoc_pipeline import PosthocPipeline
from freemocap.core.pipeline.posthoc_tasks.calibration_task.calibration_task import run_calibration_task
from freemocap.core.pipeline.posthoc_tasks.mocap_task.mocap_task import run_mocap_task
from freemocap.core.pipeline.realtime_pipeline import RealtimePipeline
from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt
from skellycam.core.ipc.process_management.process_registry import ProcessRegistry

logger = logging.getLogger(__name__)

# How often the reaper thread checks for dead posthoc pipelines (seconds)
_REAPER_INTERVAL_SECONDS: float = 10.0


@dataclass
class PipelineManager:
    """
    Unified pipeline lifecycle manager.

    Owns all realtime and posthoc pipelines. Creates them, tracks them,
    and cleans up dead ones.
    """
    global_kill_flag: multiprocessing.Value
    process_registry: ProcessRegistry
    lock: multiprocessing.Lock = field(default_factory=multiprocessing.Lock)
    realtime_pipelines: dict[PipelineIdString, RealtimePipeline] = field(default_factory=dict)
    posthoc_pipelines: dict[PipelineIdString, PosthocPipeline] = field(default_factory=dict)
    _reaper_thread: threading.Thread | None = field(default=None, repr=False)
    _reaper_stop: threading.Event = field(default_factory=threading.Event, repr=False)

    @classmethod
    def from_fastapi_app(cls, fastapi_app: FastAPI) -> "PipelineManager":
        manager = cls(
            global_kill_flag=fastapi_app.state.global_kill_flag,
            process_registry=fastapi_app.state.process_registry,
        )
        manager.start_reaper()
        return manager

    # ------------------------------------------------------------------
    # Reaper thread: auto-cleanup for posthoc pipelines
    # ------------------------------------------------------------------

    def start_reaper(self) -> None:
        """Start the background reaper thread that cleans up dead posthoc pipelines."""
        if self._reaper_thread is not None:
            raise RuntimeError("Reaper thread already started")
        self._reaper_stop.clear()
        self._reaper_thread = threading.Thread(
            target=self._reaper_loop,
            name="PipelineManager-Reaper",
            daemon=True,
        )
        self._reaper_thread.start()
        logger.debug("Pipeline reaper thread started")

    def _reaper_loop(self) -> None:
        while not self._reaper_stop.is_set() and not self.global_kill_flag.value:
            self._reaper_stop.wait(timeout=_REAPER_INTERVAL_SECONDS)
            if self._reaper_stop.is_set():
                break
            self._reap_dead_posthoc_pipelines()
        self._reap_dead_posthoc_pipelines()

    def _reap_dead_posthoc_pipelines(self) -> None:
        with self.lock:
            dead_ids: list[PipelineIdString] = []
            for pipeline_id, pipeline in self.posthoc_pipelines.items():
                if pipeline.started and not pipeline.alive:
                    dead_ids.append(pipeline_id)

            for pipeline_id in dead_ids:
                pipeline = self.posthoc_pipelines.pop(pipeline_id)
                # Check if it died cleanly (all processes exited with code 0)
                dirty = False
                for node in pipeline.video_nodes.values():
                    if node.worker.exitcode not in (None, 0):
                        logger.warning(
                            f"PosthocPipeline [{pipeline_id}] video node "
                            f"'{node.worker.name}' exited with code {node.worker.exitcode}"
                        )
                        dirty = True
                if pipeline.aggregation_node.worker.exitcode not in (None, 0):
                    logger.warning(
                        f"PosthocPipeline [{pipeline_id}] aggregation node "
                        f"exited with code {pipeline.aggregation_node.worker.exitcode}"
                    )
                    dirty = True

                if dirty:
                    logger.warning(
                        f"PosthocPipeline [{pipeline_id}] for "
                        f"'{pipeline.recording_info.recording_name}' "
                        f"died without clean shutdown — reaped by manager"
                    )
                else:
                    logger.info(
                        f"PosthocPipeline [{pipeline_id}] for "
                        f"'{pipeline.recording_info.recording_name}' "
                        f"completed and cleaned up"
                    )

    def _stop_reaper(self) -> None:
        self._reaper_stop.set()
        if self._reaper_thread is not None:
            self._reaper_thread.join(timeout=5.0)
            self._reaper_thread = None

    # ------------------------------------------------------------------
    # Realtime pipeline operations
    # ------------------------------------------------------------------

    def create_realtime_pipeline(
        self,
        *,
        camera_group: CameraGroup,
        pipeline_config: RealtimePipelineConfig,
    ) -> RealtimePipeline:
        with self.lock:
            # Check for existing pipeline with same camera set
            for pipeline in self.realtime_pipelines.values():
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
            self.realtime_pipelines[pipeline.id] = pipeline
            logger.info(
                f"Created RealtimePipeline [{pipeline.id}] "
                f"for camera group [{pipeline.camera_group_id}]"
            )
            return pipeline

    def update_realtime_pipeline_config(
        self,
        *,
        pipeline_id: PipelineIdString,
        new_config: RealtimePipelineConfig,
    ) -> RealtimePipeline:
        with self.lock:
            pipeline = self.realtime_pipelines.get(pipeline_id)
            if pipeline is None:
                raise KeyError(f"No realtime pipeline with ID '{pipeline_id}'")
            pipeline.update_config(new_config=new_config)
            return pipeline

    def get_realtime_pipeline_by_camera_ids(
        self,
        camera_ids: list[CameraIdString],
    ) -> RealtimePipeline | None:
        with self.lock:
            for pipeline in self.realtime_pipelines.values():
                if set(pipeline.camera_ids) == set(camera_ids):
                    return pipeline
        return None

    def get_latest_frontend_payloads(
        self,
        if_newer_than: FrameNumberInt,
    ) -> dict[PipelineIdString, tuple[bytes | None, FrontendPayload | None]]:
        latest: dict[PipelineIdString, tuple[bytes | None, FrontendPayload | None]] = {}
        with self.lock:
            for pipeline_id, pipeline in self.realtime_pipelines.items():
                output = pipeline.get_latest_frontend_payload(if_newer_than=if_newer_than)
                if output is not None:
                    latest[pipeline_id] = output
        return latest

    # ------------------------------------------------------------------
    # Posthoc pipeline operations
    # ------------------------------------------------------------------

    def create_posthoc_calibration_pipeline(
        self,
        *,
        recording_info: RecordingInfo,
        calibration_config: CalibrationPipelineConfig,
    ) -> PosthocPipeline:
        task_fn = functools.partial(
            run_calibration_task,
            task_config=calibration_config,
        )
        pipeline = PosthocPipeline.create(
            recording_info=recording_info,
            detector_spec=calibration_config.detector_spec,
            task_fn=task_fn,
            process_registry=self.process_registry,
            global_kill_flag=self.global_kill_flag,
        )
        pipeline.start()
        with self.lock:
            self.posthoc_pipelines[pipeline.id] = pipeline
        logger.info(
            f"Created posthoc calibration pipeline [{pipeline.id}] "
            f"for '{recording_info.recording_name}'"
        )
        return pipeline

    def create_posthoc_mocap_pipeline(
        self,
        *,
        recording_info: RecordingInfo,
        mocap_config: MocapPipelineConfig,
    ) -> PosthocPipeline:
        task_fn = functools.partial(
            run_mocap_task,
            task_config=mocap_config,
        )
        pipeline = PosthocPipeline.create(
            recording_info=recording_info,
            detector_spec=mocap_config.detector_spec,
            task_fn=task_fn,
            process_registry=self.process_registry,
            global_kill_flag=self.global_kill_flag,
        )
        pipeline.start()
        with self.lock:
            self.posthoc_pipelines[pipeline.id] = pipeline
        logger.info(
            f"Created posthoc mocap pipeline [{pipeline.id}] "
            f"for '{recording_info.recording_name}'"
        )
        return pipeline

    # ------------------------------------------------------------------
    # Global operations
    # ------------------------------------------------------------------

    def shutdown_all(self) -> None:
        """Shut down ALL pipelines and stop the reaper."""
        self._stop_reaper()
        with self.lock:
            for pipeline in self.realtime_pipelines.values():
                pipeline.shutdown()
            self.realtime_pipelines.clear()

            for pipeline in self.posthoc_pipelines.values():
                pipeline.shutdown()
            self.posthoc_pipelines.clear()

        logger.info("PipelineManager: all pipelines shut down")

    def close_all_realtime_pipelines(self) -> None:
        with self.lock:
            for pipeline in self.realtime_pipelines.values():
                pipeline.shutdown()
            self.realtime_pipelines.clear()
        logger.info("All realtime pipelines closed")

    def close_all_posthoc_pipelines(self) -> None:
        with self.lock:
            for pipeline in self.posthoc_pipelines.values():
                pipeline.shutdown()
            self.posthoc_pipelines.clear()
        logger.info("All posthoc pipelines closed")

    def pause_unpause_realtime_pipelines(self) -> None:
        with self.lock:
            for pipeline in self.realtime_pipelines.values():
                pipeline.camera_group.pause_unpause()

    async def start_recording_all(self, recording_info: RecordingInfo) -> None:
        with self.lock:
            for pipeline in self.realtime_pipelines.values():
                await pipeline.camera_group.start_recording(recording_info=recording_info)

    async def stop_recording_all(self) -> list[RecordingInfo]:
        with self.lock:
            recording_infos: list[RecordingInfo] = []
            for pipeline in self.realtime_pipelines.values():
                info = await pipeline.camera_group.stop_recording()
                recording_infos.append(info)
            return recording_infos
