"""
PosthocPipelineManager: lifecycle manager for fire-and-forget posthoc pipelines.

Each posthoc pipeline processes a recorded video group through detection and
a task function (calibration, mocap, etc.), then self-terminates. The processes
log their own errors and report progress via pubsub — the manager just tracks
them for cancellation/shutdown purposes.

Dead pipelines are cleaned up lazily whenever the manager is accessed.
"""
import uuid
import functools
import logging
import multiprocessing
import multiprocessing.synchronize
from dataclasses import dataclass, field
from pathlib import Path
from multiprocessing.sharedctypes import Synchronized

from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.pipeline.posthoc.calibration_pipeline import CalibrationPipeline
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.abcs.pipeline_manager_abc import PipelineManagerABC
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.core.pipeline.posthoc.pipeline_phases import AggregatorPhase, PosthocPipelineType
from freemocap.core.pipeline.posthoc.posthoc_pipeline import PosthocPipeline
from freemocap.core.tasks.calibration.calibration_task_config import PosthocCalibrationPipelineConfig
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.types.type_overloads import PipelineIdString
from freemocap.core.pipeline.posthoc.progress_messages import AggregatorNodeProgressMessage, PipelineProgressMessage

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
    pipelines: dict[PipelineIdString, PosthocPipeline | CalibrationPipeline] = field(default_factory=dict)
    # Synthetic terminal messages for pipelines stopped manually (via stop_pipeline/
    # stop_all_pipelines), which never emit their own terminal COMPLETE/FAILED message
    # since they're killed rather than left to finish. Drained by get_progress_updates().
    pending_stop_messages: list[PipelineProgressMessage] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Lazy cleanup
    # ------------------------------------------------------------------

    terminal_progress: dict[str, PipelineProgressMessage] = field(default_factory=dict)

    def _retain_terminal_progress(self, messages: list[PipelineProgressMessage]) -> None:
        """Keep the latest 100 task outcomes available to every connected client."""
        for message in messages:
            if ":" not in message.pipeline_id and message.phase in (AggregatorPhase.COMPLETE, AggregatorPhase.FAILED):
                self.terminal_progress[message.pipeline_id] = message
        while len(self.terminal_progress) > 100:
            del self.terminal_progress[next(iter(self.terminal_progress))]

    def _evict_dead(self) -> list[PipelineProgressMessage]:
        """Remove pipelines whose processes have all exited. Caller must hold self.lock.

        Drains any remaining progress messages BEFORE closing pubsub so that
        terminal COMPLETE/FAILED messages emitted just before worker exit are
        not lost. Returns those final messages.
        """
        dead_ids: list[PipelineIdString] = [
            pid for pid, pipeline in self.pipelines.items()
            if pipeline.started and not pipeline.alive
        ]
        final_messages: list[PipelineProgressMessage] = []
        for pid in dead_ids:
            pipeline = self.pipelines.pop(pid)
            # Flush relay (pub→sub) THEN drain subscription queues so the
            # terminal COMPLETE/FAILED message emitted just before worker exit
            # is not missed. Without the flush, the relay may not have had a
            # chance to move the message from the publication queue before we
            # read the subscription queue.
            final_messages.extend(pipeline.drain_and_get_messages())
            pipeline.shutdown()
            logger.debug(
                f"Evicted completed PosthocPipeline [{pid}] "
                f"for '{pipeline.recording_info.recording_name}'"
            )
        self._retain_terminal_progress(final_messages)
        return final_messages

    def evict_completed(self) -> list[PipelineProgressMessage]:
        """Clean up any posthoc pipelines that have finished running.

        Returns any final progress messages drained from dead pipelines.
        Safe to call frequently — skips lock acquisition when there are no
        pipelines to check.
        """
        if not self.pipelines:
            return []
        with self.lock:
            return self._evict_dead()

    # ------------------------------------------------------------------
    # Pipeline creation
    # ------------------------------------------------------------------

    def create_calibration_pipeline(
        self, *, recording_info: RecordingInfo,
        calibration_config: PosthocCalibrationPipelineConfig,
    ) -> CalibrationPipeline:
        pipeline_id = str(uuid.uuid4())[:6]
        pipeline = CalibrationPipeline(
            id=pipeline_id, recording_info=recording_info, config=calibration_config,
            ipc=PipelineIPC.create(global_kill_flag=self.global_kill_flag,
                heartbeat_timestamp=self.worker_registry.heartbeat_timestamp, pipeline_id=pipeline_id),
            worker_registry=self.worker_registry,
        )
        with self.lock:
            self._evict_dead()
            self.pipelines[pipeline.id] = pipeline
            pipeline.start()
        return pipeline

    def create_mocap_pipeline(
        self,
        *,
        recording_info: RecordingInfo,
        mocap_config: PosthocMocapPipelineConfig,
        start_pipeline: bool = True,
    ) -> PosthocPipeline:
        structure = RecordingStructure(
            base_directory=Path(recording_info.recording_directory),
            recording_name=recording_info.recording_name,
        )
        if structure.data_parquet_path.exists():
            read_metadata(path=structure.data_parquet_path)
        # Lazy import: the posthoc mocap task drags in the (still-deferred) skellyforge
        # Human/filter/interpolation modules, so it must not be imported at module load.
        from freemocap.core.tasks.mocap.posthoc_mocap_task import run_posthoc_mocap_aggregator_task
        mocap_task_fn = functools.partial(
            run_posthoc_mocap_aggregator_task,
            task_config=mocap_config,
        )
        pipeline = PosthocPipeline.create(
            pipeline_id=str(uuid.uuid4())[:6],
            recording_info=recording_info,
            detector_config=mocap_config.tracker_config,
            aggregation_task_fn=mocap_task_fn,
            pipeline_type=PosthocPipelineType.MOCAP,
            worker_registry=self.worker_registry,
            global_kill_flag=self.global_kill_flag,
        )
        pipeline.queued_progress_message = PipelineProgressMessage(
            pipeline_id=pipeline.id,
            pipeline_type=str(PosthocPipelineType.MOCAP),
            phase="queued",
            progress_fraction=0.0,
            detail="Pipeline queued, starting workers...",
            recording_name=recording_info.recording_name,
            recording_path=str(recording_info.full_recording_path),
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

    def _stopped_by_user_message(self, pipeline: PosthocPipeline | CalibrationPipeline) -> AggregatorNodeProgressMessage:
        return AggregatorNodeProgressMessage(
            pipeline_id=pipeline.id,
            pipeline_type=str(pipeline.pipeline_type),
            phase="failed",
            progress_fraction=0.0,
            detail="Stopped by user",
            recording_name=pipeline.recording_info.recording_name,
            recording_path=str(pipeline.recording_info.full_recording_path),
        )

    def stop_pipeline(self, *, pipeline_id: PipelineIdString, pipeline_type: PosthocPipelineType) -> bool:
        """Shutdown a single pipeline by ID. Returns True if found, False if not."""
        with self.lock:
            pipeline = self.pipelines.get(pipeline_id)
            if pipeline is None or pipeline.pipeline_type != pipeline_type:
                return False
            self.pipelines.pop(pipeline_id)
            self.pending_stop_messages.append(self._stopped_by_user_message(pipeline))
        pipeline.shutdown()
        logger.info(f"Stopped posthoc pipeline [{pipeline_id}]")
        return True

    def stop_all_pipelines(self, *, pipeline_type: PosthocPipelineType) -> None:
        """Shutdown all active posthoc pipelines."""
        with self.lock:
            pipelines = [pipeline for pipeline in self.pipelines.values() if pipeline.pipeline_type == pipeline_type]
            for pipeline in pipelines:
                self.pipelines.pop(pipeline.id)
            self.pending_stop_messages.extend(
                self._stopped_by_user_message(pipeline) for pipeline in pipelines
            )
        for pipeline in pipelines:
            pipeline.shutdown()
        logger.info(f"Stopped {len(pipelines)} posthoc pipeline(s)")

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
        with self.lock:
            self._retain_terminal_progress(self.pending_stop_messages)
            self.pending_stop_messages.clear()
            progress_messages = list(self.terminal_progress.values())
            for pipeline in self.pipelines.values():
                progress_messages.extend(pipeline.get_progress_messages())
            return progress_messages
