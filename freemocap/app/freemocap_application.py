from freemocap.core.pipeline.posthoc.calibration_pipeline import CalibrationPipeline
"""
Top-level FreemocapApplication: owns the camera group manager, the realtime and
posthoc pipeline managers, and the worker registry, and orchestrates recording and
calibration/mocap pipeline operations.
"""
import logging
import multiprocessing
import asyncio
from freemocap.core.recording.recording_access import RecordingAccess
from dataclasses import dataclass, field
from multiprocessing.sharedctypes import Synchronized

from fastapi import FastAPI
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.camera_group.camera_group_manager import get_or_create_camera_group_manager
from skellycam.core.camera_group.camera_backend_manager import CameraBackendManager
from freemocap.core.pipeline.realtime.capture_group import CaptureGroup
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.inference_service import InferenceService
from freemocap.core.pipeline.posthoc.mocap_pipeline import MocapPipeline
from freemocap.core.pipeline.posthoc.posthoc_pipeline_manager import PosthocPipelineManager
from freemocap.core.pipeline.posthoc.sync_job import SyncJob
from freemocap.core.pipeline.posthoc.sync_job_manager import SyncJobManager
from freemocap.core.pipeline.realtime.realtime_aggregator_node import RealtimePipelineConfig
from freemocap.core.pipeline.realtime.realtime_pipeline import RealtimePipeline
from freemocap.core.pipeline.realtime.realtime_pipeline_manager import RealtimePipelineManager
from freemocap.core.pipeline.realtime.startup_status import RealtimeStartupStatus
from freemocap.core.tasks.calibration.calibration_task_config import PosthocCalibrationPipelineConfig
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.types.type_overloads import FrameNumberInt
from freemocap.core.pipeline.posthoc.progress_messages import PipelineProgressMessage
from freemocap.pubsub.pubsub_topics import AggregationNodeOutputMessage  # noqa: TC001 — beartype resolves the get_latest_aggregator_outputs return annotation at runtime
from skelly_synchronize.core.models import SyncRequest
from freemocap.core.streaming.outputs.manager import StreamingOutputManager

logger = logging.getLogger(__name__)


class RealtimeStartupConfigurationError(ValueError):
    """Requested realtime settings cannot safely start through this path."""


class RealtimeStartupStopped(RuntimeError):
    """The request stopped at a safe lifecycle boundary, not inside native work."""


async def _drain_realtime_operation(operation: asyncio.Task):
    """Retain ownership through repeated cancellation; native calls are not killed."""
    while not operation.done():
        try:
            await asyncio.shield(operation)
        except asyncio.CancelledError:
            continue
    return operation.result()


@dataclass
class FreemocapApplication:
    global_kill_flag: Synchronized
    inference_service: InferenceService
    worker_registry: WorkerRegistry
    realtime_pipeline_manager: RealtimePipelineManager
    posthoc_pipeline_manager: PosthocPipelineManager
    sync_job_manager: SyncJobManager
    camera_group_manager: CameraBackendManager
    streaming_outputs: StreamingOutputManager = field(init=False)
    startup_status: RealtimeStartupStatus = field(default_factory=RealtimeStartupStatus, init=False)
    _realtime_lifecycle_lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _realtime_startup_operation: asyncio.Task | None = field(default=None, init=False, repr=False)
    _realtime_stop_task: asyncio.Task | None = field(default=None, init=False, repr=False)
    _startup_pipeline_owned: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        from freemocap.core.streaming.outputs.registry import builtin_protocols
        from freemocap.core.streaming.outputs.source import RuntimeOutputSource
        self.streaming_outputs = StreamingOutputManager(
            source=RuntimeOutputSource(self), protocols=builtin_protocols())

    @classmethod
    def create(cls, fastapi_app: FastAPI) -> "FreemocapApplication":
        global_kill_flag = fastapi_app.state.global_kill_flag
        worker_registry = fastapi_app.state.worker_registry
        access = RecordingAccess()
        fastapi_app.state.recording_access = access

        inference_service = InferenceService(worker_registry=worker_registry)
        inference_service.start()
        return cls(
            inference_service=inference_service,
            global_kill_flag=global_kill_flag,
            worker_registry=worker_registry,
            realtime_pipeline_manager=RealtimePipelineManager(
                inference_service=inference_service,                worker_registry=worker_registry,
            ),
            posthoc_pipeline_manager=PosthocPipelineManager(
                access=access,
                inference_service=inference_service,                global_kill_flag=global_kill_flag,
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
        # Keep the lock until a cancelled caller's actual operation has drained.
        # Cancelling to_thread's await does not stop its native work.
        if self._realtime_stop_task is not None:
            await asyncio.shield(self._realtime_stop_task)
        async with self._realtime_lifecycle_lock:
            self.startup_status.begin()
            self._startup_pipeline_owned = False
            operation = asyncio.create_task(self._apply_realtime_pipeline(
                camera_configs=camera_configs, pipeline_config=pipeline_config,
                realtime_camera_ids=realtime_camera_ids,
            ))
            self._realtime_startup_operation = operation
            try:
                return await asyncio.shield(operation)
            except asyncio.CancelledError:
                self.startup_status.request_stop()
                try:
                    pipeline = await _drain_realtime_operation(operation)
                except RealtimeStartupStopped:
                    pass
                except Exception as error:
                    logger.error("Realtime startup failed while its caller was stopping: %s", error)
                else:
                    # Cancellation can arrive after creation's final stop check.
                    if self._startup_pipeline_owned:
                        self.startup_status.phase("stopping_pipeline")
                        cleanup = asyncio.create_task(asyncio.to_thread(
                            self.realtime_pipeline_manager.stop_pipeline, pipeline_id=pipeline.id,
                        ))
                        try:
                            await _drain_realtime_operation(cleanup)
                        except Exception as error:
                            self.startup_status.fail(str(error))
                            logger.exception("Cancelled startup pipeline cleanup failed")
                        else:
                            self.startup_status.stopped()
                    else:
                        self.startup_status.stopped("Startup request stopped; the existing pipeline remains running")
                raise
            finally:
                self._realtime_startup_operation = None

    async def stop_realtime_startup(self) -> bool:
        """Record stop intent immediately; completion is reported after cleanup."""
        if not self.startup_status.request_stop():
            return False
        operation = self._realtime_startup_operation
        if operation is None or operation.done():
            if self._startup_pipeline_owned:
                if self._realtime_stop_task is None or self._realtime_stop_task.done():
                    self._realtime_stop_task = asyncio.create_task(self._stop_created_startup_pipeline())
            else:
                self.startup_status.stopped("Startup request stopped; the existing pipeline remains running")
        return True

    async def _stop_created_startup_pipeline(self) -> None:
        async with self._realtime_lifecycle_lock:
            pipeline_id = self.startup_status.snapshot()["pipeline_id"]
            try:
                self.startup_status.phase("stopping_pipeline")
                await asyncio.to_thread(self.realtime_pipeline_manager.stop_pipeline, pipeline_id=pipeline_id)
            except Exception as error:
                self.startup_status.fail(str(error))
                logger.exception("Failed to stop newly created realtime pipeline")
            else:
                self.startup_status.stopped()

    def _check_startup_stop(self) -> None:
        if self.startup_status.stop_requested.is_set():
            raise RealtimeStartupStopped("Realtime startup stopped at a safe boundary")

    async def _apply_realtime_pipeline(
        self, *, camera_configs: CameraConfigs, pipeline_config: RealtimePipelineConfig,
        realtime_camera_ids: list[CameraIdString] | None,
    ) -> RealtimePipeline:
        try:
            return await self._apply_realtime_pipeline_steps(
                camera_configs=camera_configs, pipeline_config=pipeline_config,
                realtime_camera_ids=realtime_camera_ids,
            )
        except RealtimeStartupStopped:
            self.startup_status.stopped(
                "Startup request stopped; camera capture and any pre-existing pipeline remain independently managed"
            )
            raise
        except Exception as error:
            self.startup_status.fail(str(error))
            raise

    async def _apply_realtime_pipeline_steps(
        self, *, camera_configs: CameraConfigs, pipeline_config: RealtimePipelineConfig,
        realtime_camera_ids: list[CameraIdString] | None,
    ) -> RealtimePipeline:
        if (not pipeline_config.use_centralized_inference
                and pipeline_config.camera_node_config.skeleton_tracking_enabled
                and pipeline_config.skeleton_inference_node_config.execution_provider == "trt"):
            raise RealtimeStartupConfigurationError("TensorRT preparation requires centralized realtime inference")
        for pipeline in list(self.realtime_pipeline_manager.pipelines.values()):
            self._check_startup_stop()
            if not pipeline.alive:
                self.startup_status.phase("stopping_pipeline")
                await asyncio.to_thread(self.realtime_pipeline_manager.stop_pipeline, pipeline_id=pipeline.id)
                continue
            self.startup_status.phase("updating_pipeline")
            await asyncio.to_thread(self.realtime_pipeline_manager.update_pipeline_config,
                                    pipeline_id=pipeline.id, new_config=pipeline_config)
            self._check_startup_stop()
            self.startup_status.pipeline_created(pipeline.id)
            return pipeline

        self._check_startup_stop()
        self.startup_status.phase("starting_cameras")
        camera_group = await self.camera_group_manager.create_or_update_camera_group(
            camera_configs=camera_configs,
            backend=self.camera_group_manager.backend,
        )
        self._check_startup_stop()
        self.startup_status.phase("starting_pipeline")
        capture = await asyncio.to_thread(CaptureGroup, camera_group, self.global_kill_flag)
        try:
            self._check_startup_stop()
            pipeline = await asyncio.to_thread(
                self.realtime_pipeline_manager.create_pipeline,
                camera_group=capture,
                pipeline_config=pipeline_config,
                realtime_camera_ids=realtime_camera_ids,
            )
        except BaseException:
            await asyncio.to_thread(capture.close_transport)
            raise
        self._startup_pipeline_owned = True
        if self.startup_status.stop_requested.is_set():
            self.startup_status.phase("stopping_pipeline")
            await asyncio.to_thread(self.realtime_pipeline_manager.stop_pipeline, pipeline_id=pipeline.id)
            self._check_startup_stop()
        self.startup_status.pipeline_created(pipeline.id)
        return pipeline

    # ------------------------------------------------------------------
    # Posthoc pipeline operations
    # ------------------------------------------------------------------

    async def create_posthoc_calibration_pipeline(
            self,
            recording_info: RecordingInfo,
            calibration_config: PosthocCalibrationPipelineConfig,
    ) -> CalibrationPipeline:
        pipeline = self.posthoc_pipeline_manager.create_calibration_pipeline(
            recording_info=recording_info,
            calibration_config=calibration_config,
        )
        return pipeline

    async def create_posthoc_mocap_pipeline(
            self,
            recording_info: RecordingInfo,
            mocap_config: PosthocMocapPipelineConfig,
    ) -> MocapPipeline:
        pipeline = self.posthoc_pipeline_manager.create_mocap_pipeline(
            recording_info=recording_info,
            mocap_config=mocap_config,
        )
        return pipeline

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
                    "error": pipeline.failure,
                }
                for pipeline in self.realtime_pipeline_manager.pipelines.values()
            ],
        }

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def shutdown_all_processing(self) -> None:
        self.realtime_pipeline_manager.shutdown()
        self.posthoc_pipeline_manager.shutdown()
        self.sync_job_manager.shutdown()

    def pause_unpause_pipelines(self) -> None:
        self.realtime_pipeline_manager.pause_unpause_all()

    def close(self) -> None:
        self.global_kill_flag.value = True
        try:
            try:
                self.streaming_outputs.close()
            finally:
                self.shutdown_all_processing()
        finally:
            self.inference_service.close()


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
