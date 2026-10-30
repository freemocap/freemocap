"""Managed Mocap recording task: group detection, annotation, and reconstruction."""

from contextlib import ExitStack, closing
from freemocap.core.pipeline.performance_report import PerformanceReport
from dataclasses import dataclass, field
from multiprocessing.sharedctypes import Synchronized
from pathlib import Path
from queue import Empty, Queue
from concurrent.futures import CancelledError

from skellycam.core.ipc.process_management.managed_worker import ManagedWorker, WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.core import DetectionStageConfig, TrackerConfig
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition, CharucoDetectorConfig

from freemocap.core.pipeline.inference_service import InferenceService
from freemocap.core.pipeline.abcs.pipeline_abc import PipelineABC
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc.mocap_detection import MocapDetectionRequest, detect_mocap_recording
from freemocap.core.pipeline.posthoc.mocap_video_node import MocapVideoNode
from freemocap.core.pipeline.posthoc.pipeline_phases import AggregatorPhase, MocapStage, PosthocPipelineType
from freemocap.core.pipeline.posthoc.progress_messages import AggregatorNodeProgressMessage, PipelineProgressMessage
from freemocap.core.pipeline.posthoc.operation_progress import OperationProgressReporter
from freemocap.core.pipeline.posthoc.task_progress_reporter import TaskProgressReporter
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tasks.mocap.posthoc_mocap_task import run_posthoc_mocap_task
from freemocap.core.tracking.board_selection import CharucoBoardMode
from freemocap.core.tracking.tracker_factory import CHARUCO_STAGE_NAME

# The app's beartype import hook evaluates local variable annotations at runtime.
# Keep these imports available even though static analysis sees only type usage.
from skellytracker.core.data_primitives.observation import Observation  # noqa: TC002
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata  # noqa: TC001


@dataclass(frozen=True, slots=True)
class MocapWorkerRequest:
    pipeline_id: str
    recording: RecordingInfo
    config: PosthocMocapPipelineConfig
    ipc: PipelineIPC
    progress_queue: Queue[PipelineProgressMessage]

    registry: WorkerRegistry
    inference_service: InferenceService
    video_nodes: list[MocapVideoNode]
    performance: PerformanceReport = field(default_factory=PerformanceReport)
    operation_progress: OperationProgressReporter = field(default_factory=OperationProgressReporter)

    def report(self, stage: str, detail: str, fraction: float) -> None:
        self.operation_progress.report(self, stage, detail, fraction)

    def report_operation(self, operation_id: str, label: str, status: str,
                         detail: str = "", completed: int | None = None,
                         total: int | None = None, unit: str | None = None,
                         *, phase: str = "reconstructing") -> None:
        self.operation_progress.update(self, operation_id, label, status, detail,
                                       completed, total, unit, phase=phase)

    def report_export(self, task_id: str, label: str, state: str, detail: str,
                      completed: int | None = None, total: int | None = None) -> None:
        self.report_operation(task_id, label, state, detail, completed, total,
                              "channels" if total is not None else None,
                              phase="exporting_csv")


def complete_mocap(request: MocapWorkerRequest) -> None:
    """Finish independent exports before reporting the recording's final outcome."""
    from freemocap.core.pipeline.posthoc.export_completion import complete_recording_exports
    complete_recording_exports(request)


def run_mocap_pipeline(*, request: MocapWorkerRequest) -> None:
    outcome = "failed"
    try:
        _run_mocap_pipeline(request=request)
        outcome = "complete" if request.ipc.should_continue else "cancelled"
    except CancelledError:
        outcome = "cancelled"
        return
    finally:
        request.performance.log(pipeline_id=request.pipeline_id, outcome=outcome)


def _run_mocap_pipeline(*, request: MocapWorkerRequest) -> None:
    try:
        if request.config.pipeline_implementation == "typed_dataflow":
            from freemocap.core.pipeline.dataflow.application_pipeline import run_application_graph
            run_application_graph(request=request)
            return
        if request.config.start_stage != 'observations':
            from freemocap.core.pipeline.posthoc.saved_stage_processing import (
                recording_structure, run_saved_numerical_stages,
            )
            structure = recording_structure(str(request.recording.full_recording_path))
            if request.config.start_stage != 'triangulation':
                run_saved_numerical_stages(structure=structure, config=request.config,
                    reporter=TaskProgressReporter(callback=request.report), cancelled=lambda: not request.ipc.should_continue)
            else:
                from freemocap.core.recording.result_processing.saved_observations import read_saved_observations
                request.report(AggregatorPhase.SETTING_UP, 'Loading saved 2D tracking; skipping detection', 0.0)
                saved = read_saved_observations(structure=structure, run_id=request.config.base_run_id, sensor_group=request.config.sensor_group)
                group = saved.sensor_group
                # Reused detections retain the detector and board that actually produced them.
                current = request.config
                config = saved.config.model_copy(update={name: getattr(current, name) for name in (
                    'start_stage', 'base_run_id', 'sensor_group', 'calibration_toml_path', 'camera_matching',
                    'triangulation_config', 'filter_config', 'body_alignment')})
                config = config.model_copy(update={'sensor_group': group})
                board = config.charuco_board if 'charuco' in saved.frames.stage_names else None
                run_posthoc_mocap_task(frame_observations=saved.frames, recording_info=request.recording,
                    video_metadata=saved.videos, task_config=config, selected_board=board,
                    reporter=TaskProgressReporter(callback=request.report), cancelled=lambda: not request.ipc.should_continue,
                    saved_timing=saved.timing, performance=request.performance)
            if request.ipc.should_continue:
                complete_mocap(request)
            return
        request.report(AggregatorPhase.SETTING_UP, "Loading recording and detectors", 0.0)
        observations: list[dict[str, Observation]] = []
        video_metadata: dict[str, VideoMetadata] = {}
        selected_board: CharucoBoardDefinition | None = None
        resolved_config = request.config
        with request.performance.measure("detection.total"), ExitStack() as cleanup:
            frames = cleanup.enter_context(closing(detect_mocap_recording(MocapDetectionRequest(
                recording_path=Path(request.recording.full_recording_path),
                config=request.config, ipc=request.ipc, progress=request.progress_queue,
                registry=request.registry, inference_service=request.inference_service,
                video_nodes=request.video_nodes, performance=request.performance,
            ))))
            for frame in frames:
                video_metadata = frame.video_metadata
                if frame.selected_board is not None and selected_board is None:
                    selected_board = frame.selected_board
                    tracker_config = TrackerConfig(stages=[
                        *request.config.tracker_config.stages,
                        DetectionStageConfig(name=CHARUCO_STAGE_NAME, keypoint_detectors=[CharucoDetectorConfig(board=selected_board)]),
                    ])
                    resolved_config = request.config.model_copy(update={
                        "charuco_board": selected_board, "board_mode": CharucoBoardMode.EXPLICIT,
                        "tracker_config": tracker_config,
                    })
                observations.append(frame.observations)
                if len(observations) % max(1, frame.frame_count // 50) == 0 or len(observations) == frame.frame_count:
                    request.report(AggregatorPhase.COLLECTING_CAMERA_OUTPUT,
                        f"Detecting and annotating {len(observations)}/{frame.frame_count} synchronized frames",
                        len(observations) / frame.frame_count)
            if not request.ipc.should_continue:
                return
            if not observations:
                raise ValueError("Mocap detection produced no frames")
        if not request.ipc.should_continue:
            return
        run_posthoc_mocap_task(
            frame_observations=observations, recording_info=request.recording,
            video_metadata=video_metadata, task_config=resolved_config, selected_board=selected_board,
            reporter=TaskProgressReporter(callback=request.report),
            cancelled=lambda: not request.ipc.should_continue, performance=request.performance,
        )
        if request.ipc.should_continue:
            complete_mocap(request)
    except CancelledError:
        raise
    except Exception as error:
        request.report(AggregatorPhase.FAILED, f"{type(error).__name__}: {error}", 0.0)
        request.ipc.shutdown_pipeline()
        raise


@dataclass
class MocapPipeline(PipelineABC):
    id: str
    recording_info: RecordingInfo
    ipc: PipelineIPC
    worker: ManagedWorker
    progress_queue: Queue[PipelineProgressMessage]
    video_nodes: list[MocapVideoNode] = field(default_factory=list)
    pipeline_type: PosthocPipelineType = field(default=PosthocPipelineType.MOCAP, init=False)
    started: bool = False
    _latest: dict[str, PipelineProgressMessage] = field(default_factory=dict)

    @classmethod
    def create(
        cls, *, pipeline_id: str, recording_info: RecordingInfo, config: PosthocMocapPipelineConfig,
        worker_registry: WorkerRegistry, global_kill_flag: Synchronized, inference_service: InferenceService,
    ) -> "MocapPipeline":
        ipc = PipelineIPC.create(global_kill_flag=global_kill_flag,
            heartbeat_timestamp=worker_registry.heartbeat_timestamp, pipeline_id=pipeline_id)
        progress_queue: Queue[PipelineProgressMessage] = Queue()
        video_nodes: list[MocapVideoNode] = []
        request = MocapWorkerRequest(pipeline_id=pipeline_id, recording=recording_info,
            config=config, ipc=ipc, progress_queue=progress_queue, registry=worker_registry,
            inference_service=inference_service, video_nodes=video_nodes)
        try:
            worker = worker_registry.create_worker(
                shutdown_flag=ipc.pipeline_shutdown_flag, worker_mode=WorkerMode.THREAD,
                target=run_mocap_pipeline, name=f"Mocap-{pipeline_id}", log_queue=ipc.ws_queue,
                kwargs={"request": request},
            )
        except Exception:
            ipc.shutdown_pipeline()
            raise
        pipeline = cls(id=pipeline_id, recording_info=recording_info, ipc=ipc,
            worker=worker, progress_queue=progress_queue, video_nodes=video_nodes)
        pipeline._latest[pipeline_id] = AggregatorNodeProgressMessage(
            pipeline_id=pipeline_id, pipeline_type=str(PosthocPipelineType.MOCAP),
            phase=AggregatorPhase.SETTING_UP, detail="Mocap pipeline queued",
            recording_name=recording_info.recording_name,
            recording_path=str(recording_info.full_recording_path),
        )
        return pipeline

    @property
    def alive(self) -> bool:
        return self.worker.is_alive() or any(node.worker.is_alive() for node in self.video_nodes)

    def start(self) -> None:
        if self.started:
            raise RuntimeError("Mocap pipeline already started")
        self.worker.start()
        self.started = True

    def get_progress_messages(self) -> list[PipelineProgressMessage]:
        while True:
            try:
                message = self.progress_queue.get_nowait()
            except Empty:
                break
            self._latest[message.pipeline_id] = message
        exited_without_outcome = self.started and not self.alive and not any(
            message.phase in (AggregatorPhase.COMPLETE, AggregatorPhase.FAILED)
            for message in self._latest.values() if message.pipeline_id == self.id
        )
        if (self.worker.failure_exitcode is not None or exited_without_outcome) and not any(
            message.phase == AggregatorPhase.FAILED for message in self._latest.values() if message.pipeline_id == self.id
        ):
            self._latest[self.id] = AggregatorNodeProgressMessage(
                pipeline_id=self.id, pipeline_type=str(self.pipeline_type), phase=AggregatorPhase.FAILED,
                detail=f"Mocap worker exited without completing the task (exit code {self.worker.exitcode})",
                recording_name=self.recording_info.recording_name,
                recording_path=str(self.recording_info.full_recording_path),
                operations=self._latest[self.id].operations if self.id in self._latest else None,
                timing=self._latest[self.id].timing if self.id in self._latest else None,
            )
            self.ipc.shutdown_pipeline()
        return list(self._latest.values())

    def drain_and_get_messages(self) -> list[PipelineProgressMessage]:
        return self.get_progress_messages()

    def shutdown(self) -> None:
        self.worker.mark_stopping()
        self.ipc.shutdown_pipeline()
        if self.worker.is_alive():
            self.worker.terminate_gracefully()
        else:
            self.worker._reap()
        alive = [node.config.camera_id for node in self.video_nodes if node.worker.is_alive()]
        if self.worker.is_alive() or alive:
            raise RuntimeError(f"Mocap threads are still shutting down; active video threads: {alive}")
