"""
PosthocPipelineManager: lifecycle manager for fire-and-forget posthoc pipelines.

Each posthoc pipeline processes a recorded video group through detection and
a task function (calibration, mocap, etc.), then self-terminates. The processes
log their own errors and report progress via pubsub — the manager just tracks
them for cancellation/shutdown purposes.

Dead pipelines are cleaned up lazily whenever the manager is accessed.
"""
import functools
import logging
import multiprocessing
import multiprocessing.synchronize
from dataclasses import dataclass, field
from multiprocessing.sharedctypes import Synchronized

from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.pipeline.abcs.pipeline_manager_abc import PipelineManagerABC
from freemocap.core.pipeline.posthoc.posthoc_pipeline import PosthocPipeline
from freemocap.core.tasks.calibration.calibration_task_config import PosthocCalibrationPipelineConfig
from freemocap.core.tasks.calibration.posthoc_calibration_task import run_posthoc_calibration_task
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tasks.mocap.posthoc_mocap_task import run_posthoc_mocap_aggregator_task
from freemocap.core.types.type_overloads import PipelineIdString
from freemocap.pubsub.pubsub_topics import PipelineProgressMessage

logger = logging.getLogger(__name__)


@dataclass
class PosthocPipelineManager(PipelineManagerABC):
    """
    Manages fire-and-forget posthoc pipelines.

    Pipelines self-terminate when processing completes. The manager tracks
    them only for force-shutdown / cancellation. Dead entries are evicted
    lazily on access.
    """

    global_kill_flag: Synchronized
    worker_registry: WorkerRegistry
    lock: multiprocessing.synchronize.Lock = field(default_factory=multiprocessing.Lock)
    pipelines: dict[PipelineIdString, PosthocPipeline] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Lazy cleanup
    # ------------------------------------------------------------------

    def _evict_dead(self) -> None:
        """Remove pipelines whose processes have all exited. Caller must hold self.lock.

        Calls shutdown() on each dead pipeline to release PubSub resources
        (relay thread, multiprocessing.Queue instances, OS pipes).
        """
        dead_ids: list[PipelineIdString] = [
            pid for pid, pipeline in self.pipelines.items()
            if pipeline.started and not pipeline.alive
        ]
        for pid in dead_ids:
            pipeline = self.pipelines.pop(pid)
            pipeline.shutdown()
            logger.debug(
                f"Evicted completed PosthocPipeline [{pid}] "
                f"for '{pipeline.recording_info.recording_name}'"
            )

    def evict_completed(self) -> None:
        """Clean up any posthoc pipelines that have finished running.

        Safe to call frequently — skips lock acquisition when there are no
        pipelines to check.
        """
        if not self.pipelines:
            return
        with self.lock:
            self._evict_dead()

    # ------------------------------------------------------------------
    # Pipeline creation
    # ------------------------------------------------------------------

    def create_calibration_pipeline(
        self,
        *,
        recording_info: RecordingInfo,
        calibration_config: PosthocCalibrationPipelineConfig,
    ) -> PosthocPipeline:
        calibration_aggregation_task_fn = functools.partial(
            run_posthoc_calibration_task,
            task_config=calibration_config,
        )
        pipeline = PosthocPipeline.create(
            recording_info=recording_info,
            detector_config=calibration_config.detector_config,
            aggregation_task_fn=calibration_aggregation_task_fn,
            worker_registry=self.worker_registry,
            global_kill_flag=self.global_kill_flag,
        )
        pipeline.start()
        with self.lock:
            self._evict_dead()
            self.pipelines[pipeline.id] = pipeline
        logger.info(
            f"Created posthoc calibration pipeline [{pipeline.id}] "
            f"for '{recording_info.recording_name}'"
        )
        return pipeline

    def create_mocap_pipeline(
        self,
        *,
        recording_info: RecordingInfo,
        mocap_config: PosthocMocapPipelineConfig,
        start_pipeline: bool = True,
    ) -> PosthocPipeline:
        mocap_task_fn = functools.partial(
            run_posthoc_mocap_aggregator_task,
            task_config=mocap_config,
        )
        pipeline = PosthocPipeline.create(
            recording_info=recording_info,
            detector_config=mocap_config.skeleton_detector_config,
            aggregation_task_fn=mocap_task_fn,
            worker_registry=self.worker_registry,
            global_kill_flag=self.global_kill_flag,
        )
        if start_pipeline:
            pipeline.start()
        with self.lock:
            self._evict_dead()
            self.pipelines[pipeline.id] = pipeline
        logger.info(
            f"Created posthoc mocap pipeline [{pipeline.id}] "
            f"for '{recording_info.recording_name}'"
        )
        return pipeline

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Force-shutdown all posthoc pipelines (running or completed).

        Calls shutdown() on every pipeline to release PubSub resources,
        not just alive ones — completed pipelines still hold relay threads
        and multiprocessing.Queue instances until explicitly closed.
        """
        with self.lock:
            for pipeline in self.pipelines.values():
                pipeline.shutdown()
            self.pipelines.clear()
        logger.info("PosthocPipelineManager: all pipelines shut down")

    def get_progress_updates(self) -> list[PipelineProgressMessage]:
        progress_messages: list[PipelineProgressMessage] = []

        for pipeline in self.pipelines.values():
            progress_messages.extend(pipeline.get_progress_messages())

        return progress_messages
