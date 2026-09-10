"""
Own posthoc workers and retain their task state independently of client connections.

The application collector refreshes progress and releases completed workers.
HTTP readers and WebSocket senders receive copies of the same retained registry.
"""
import uuid
import logging
import multiprocessing
import multiprocessing.synchronize
from dataclasses import dataclass, field
from multiprocessing.sharedctypes import Synchronized

from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.pipeline.posthoc.calibration_pipeline import CalibrationPipeline
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.abcs.pipeline_manager_abc import PipelineManagerABC
from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
from freemocap.system.recording_structure.recording_structure import RecordingStructure
from freemocap.core.pipeline.posthoc.pipeline_phases import PosthocPipelineType
from freemocap.core.pipeline.inference_service import InferenceService
from freemocap.core.pipeline.posthoc.mocap_pipeline import MocapPipeline
from freemocap.core.tasks.calibration.calibration_task_config import PosthocCalibrationPipelineConfig
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.types.type_overloads import PipelineIdString
from freemocap.core.pipeline.posthoc.progress_messages import AggregatorNodeProgressMessage, PipelineProgressMessage
from freemocap.core.pipeline.posthoc.task_snapshot import TaskRegistry, TaskRegistrySnapshot
from freemocap.core.recording.recording_access import RecordingAccess

logger = logging.getLogger(__name__)


class TaskStartError(RuntimeError):
    """A task failed to start and its resources have been released."""


@dataclass
class PosthocPipelineManager(PipelineManagerABC):
    """
    Manage posthoc worker lifetimes, cancellation, and retained task snapshots.
    """

    global_kill_flag: Synchronized
    worker_registry: WorkerRegistry
    inference_service: InferenceService
    lock: multiprocessing.synchronize.Lock = field(default_factory=multiprocessing.Lock)
    pipelines: dict[PipelineIdString, MocapPipeline | CalibrationPipeline] = field(default_factory=dict)
    registry: TaskRegistry = field(default_factory=TaskRegistry)
    access: RecordingAccess = field(default_factory=RecordingAccess)
    pending_starts: set[str] = field(default_factory=set)

    def _register(self, *, pipeline: MocapPipeline | CalibrationPipeline) -> None:
        recording = RecordingStructure.from_recording_info(recording=pipeline.recording_info)
        try:
            self.access.reserve(recording=recording, task_id=pipeline.id)
        except Exception:
            pipeline.shutdown()
            raise
        self.registry.register(task_id=pipeline.id, task_type=str(pipeline.pipeline_type), recording=recording)
        self.pipelines[pipeline.id] = pipeline

    def _start_ready(self, *, pipeline: MocapPipeline | CalibrationPipeline) -> None:
        if not self.access.ready(task_id=pipeline.id):
            self.pending_starts.add(pipeline.id)
            return
        try:
            if isinstance(pipeline, MocapPipeline):
                structure = RecordingStructure.from_recording_info(recording=pipeline.recording_info)
                if structure.data_parquet_path.exists():
                    read_metadata(path=structure.data_parquet_path)
            pipeline.start()
            self.pending_starts.discard(pipeline.id)
        except Exception as error:
            self.registry.update(task_id=pipeline.id, messages=[AggregatorNodeProgressMessage(
                pipeline_id=pipeline.id, phase="failed", detail=f"{type(error).__name__}: {error}")])
            pipeline.shutdown()
            self.pending_starts.discard(pipeline.id)
            self.pipelines.pop(pipeline.id)
            self.access.release(task_id=pipeline.id)
            raise TaskStartError(f"Task {pipeline.id} could not start: {error}") from error

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
            pipeline = self.pipelines[pid]
            # Flush relay (pub→sub) THEN drain subscription queues so the
            # terminal COMPLETE/FAILED message emitted just before worker exit
            # is not missed. Without the flush, the relay may not have had a
            # chance to move the message from the publication queue before we
            # read the subscription queue.
            messages = pipeline.drain_and_get_messages()
            self.registry.update(task_id=pid, messages=messages)
            final_messages.extend(messages)
            pipeline.shutdown()
            self.pipelines.pop(pid)
            self.access.release(task_id=pid)
            logger.debug(
                f"Evicted completed PosthocPipeline [{pid}] "
                f"for '{pipeline.recording_info.recording_name}'"
            )

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
        pipeline_id = str(uuid.uuid4())
        pipeline = CalibrationPipeline(
            id=pipeline_id, recording_info=recording_info, config=calibration_config,
            ipc=PipelineIPC.create(global_kill_flag=self.global_kill_flag,
                heartbeat_timestamp=self.worker_registry.heartbeat_timestamp, pipeline_id=pipeline_id),
            worker_registry=self.worker_registry,
        )
        with self.lock:
            self._evict_dead()
            self._register(pipeline=pipeline)
            self._start_ready(pipeline=pipeline)
        return pipeline

    def create_mocap_pipeline(
        self,
        *,
        recording_info: RecordingInfo,
        mocap_config: PosthocMocapPipelineConfig,
        start_pipeline: bool = True,
    ) -> MocapPipeline:
        structure = RecordingStructure.from_recording_info(recording=recording_info)
        with self.access.read(path=structure.full_path, cancel=lambda: None):
            if structure.data_parquet_path.exists():
                read_metadata(path=structure.data_parquet_path)
        pipeline = MocapPipeline.create(
            inference_service=self.inference_service,
            pipeline_id=str(uuid.uuid4()), recording_info=recording_info,
            config=mocap_config, worker_registry=self.worker_registry,
            global_kill_flag=self.global_kill_flag,
        )
        with self.lock:
            self._evict_dead()
            self._register(pipeline=pipeline)
            if start_pipeline:
                self._start_ready(pipeline=pipeline)
        logger.info(
            f"Created posthoc mocap pipeline [{pipeline.id}] "
            f"for '{recording_info.recording_name}'"
        )
        return pipeline

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def stop_pipeline(self, *, pipeline_id: PipelineIdString, pipeline_type: PosthocPipelineType) -> bool:
        """Ensure a known task of the requested type is stopped, including finished tasks."""
        with self.lock:
            pipeline = self.pipelines.get(pipeline_id)
            if pipeline is None:
                task = self.registry.tasks.get(pipeline_id)
                if task is None or task.task_type != pipeline_type:
                    return False
                if task.status == "running":
                    raise RuntimeError(f"Task {pipeline_id} is marked running but has no managed pipeline")
                return True
            if pipeline.pipeline_type != pipeline_type:
                return False
            pipeline.shutdown()
            self.pipelines.pop(pipeline_id)
            self.pending_starts.discard(pipeline_id)
            self.access.release(task_id=pipeline_id)
            self.registry.cancel(task_id=pipeline_id)
        logger.info(f"Stopped posthoc pipeline [{pipeline_id}]")
        return True

    def stop_all_pipelines(self, *, pipeline_type: PosthocPipelineType) -> None:
        """Shutdown all active posthoc pipelines."""
        with self.lock:
            pipelines = [pipeline for pipeline in self.pipelines.values() if pipeline.pipeline_type == pipeline_type]
            for pipeline in pipelines:
                pipeline.shutdown()
                self.pipelines.pop(pipeline.id)
                self.pending_starts.discard(pipeline.id)
                self.access.release(task_id=pipeline.id)
                self.registry.cancel(task_id=pipeline.id)
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
                self.access.release(task_id=pipeline.id)
            self.pipelines.clear()
            self.pending_starts.clear()
        logger.info("PosthocPipelineManager: all pipelines shut down")

    def refresh_progress(self) -> None:
        """Application-owned collection and cleanup, independent of connected viewers."""
        with self.lock:
            for task_id in tuple(self.pending_starts):
                try:
                    self._start_ready(pipeline=self.pipelines[task_id])
                except TaskStartError:
                    logger.exception("Deferred task startup failed; failure retained in task snapshot")
            for task_id, pipeline in self.pipelines.items():
                if task_id in self.pending_starts:
                    continue
                self.registry.update(task_id=task_id, messages=pipeline.get_progress_messages())
            self._evict_dead()
            self.registry.prune_completed(active_task_ids=set(self.pipelines))

    def task_snapshot(self) -> TaskRegistrySnapshot:
        with self.lock:
            snapshot = self.registry.snapshot()
            return snapshot.model_copy(update={"revision": snapshot.revision + self.access.revision,
                                               "recording_owners": self.access.snapshot()})

