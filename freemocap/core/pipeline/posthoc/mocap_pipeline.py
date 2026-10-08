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
from skellytracker.core.data_primitives.observation import Observation
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition, CharucoDetectorConfig

from freemocap.core.pipeline.inference_service import InferenceService
from freemocap.core.pipeline.abcs.pipeline_abc import PipelineABC
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc.mocap_detection import MocapDetectionRequest, detect_mocap_recording
from freemocap.core.pipeline.posthoc.mocap_video_node import MocapVideoNode
from freemocap.core.pipeline.posthoc.pipeline_phases import AggregatorPhase, MocapStage, PosthocPipelineType
from freemocap.core.pipeline.posthoc.progress_messages import AggregatorNodeProgressMessage, PipelineProgressMessage
from freemocap.core.pipeline.posthoc.task_progress_reporter import TaskProgressReporter
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.tasks.mocap.mocap_task_config import PosthocMocapPipelineConfig
from freemocap.core.tasks.mocap.posthoc_mocap_task import run_posthoc_mocap_task
from freemocap.core.tracking.board_selection import CharucoBoardMode
from freemocap.core.tracking.tracker_factory import CHARUCO_STAGE_NAME


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

    def report(self, stage: str, detail: str, fraction: float) -> None:
        self.progress_queue.put(AggregatorNodeProgressMessage(
            pipeline_id=self.pipeline_id, pipeline_type=str(PosthocPipelineType.MOCAP),
            phase=stage, detail=detail, progress_fraction=fraction,
            recording_name=self.recording.recording_name,
            recording_path=str(self.recording.full_recording_path),
        ))


def complete_mocap(request: MocapWorkerRequest) -> None:
    """Publish optional exports after successful processing, preserving its outcome."""
    detail = 'Mocap processing complete'
    if request.config.export_tall_csv:
        from freemocap.core.recording.exports.tall_csv import TallCsvRequest, export_tall_csv
        from freemocap.core.pipeline.posthoc.saved_stage_processing import recording_structure
        try:
            request.report(MocapStage.EXPORTING_CSV, 'Saving tall CSV to exports folder', 0.0)
            result = export_tall_csv(
                structure=recording_structure(str(request.recording.full_recording_path)),
                request=TallCsvRequest(), cancelled=lambda: not request.ipc.should_continue)
            detail += f'; tall CSV saved to {result.manifest_path.parent}'
        except CancelledError:
            detail += '; tall CSV export cancelled'
        except Exception as error:
            detail += f'; tall CSV export failed: {error}. Retry in Exports.'
    if request.config.export_to_blender and request.ipc.should_continue:
        from freemocap.core.blender.export_to_blender import export_to_blender
        try:
            request.report(MocapStage.EXPORTING_BLENDER, 'Exporting the published recording to Blender', 0.0)
            output = export_to_blender(
                recording_folder_path=request.recording.full_recording_path,
                blender_exe_path=request.config.blender_exe_path,
                open_file_on_completion=request.config.auto_open_blend_file,
                route=request.config.blender_import_route,
                package=request.config.blender_package,
                sensor_group=request.config.sensor_group,
                blender_export_config=request.config.blender_export.model_dump(),
            )
            detail += f'; Blender scene saved to {output}'
        except Exception as error:
            detail += f'; Blender export failed: {error}. Retry in Blender settings.'
    request.report(AggregatorPhase.COMPLETE, detail, 1.0)


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
        if request.config.start_stage != 'observations':
            from freemocap.core.pipeline.posthoc.saved_stage_processing import (
                recording_structure, run_saved_numerical_stages, select_group,
            )
            structure = recording_structure(str(request.recording.full_recording_path))
            if request.config.start_stage != 'triangulation':
                run_saved_numerical_stages(structure=structure, config=request.config,
                    reporter=TaskProgressReporter(callback=request.report), cancelled=lambda: not request.ipc.should_continue)
            else:
                from freemocap.core.recording.parquet_storage.parquet_reader import read_metadata
                from freemocap.core.recording.result_processing.saved_observations import read_saved_observations
                metadata = read_metadata(path=structure.data_parquet_path)
                group = select_group(metadata.runs[request.config.base_run_id], request.config.sensor_group)
                request.report(AggregatorPhase.SETTING_UP, 'Loading saved 2D tracking; skipping detection', 0.0)
                saved = read_saved_observations(structure=structure, run_id=request.config.base_run_id, sensor_group=group)
                # Reused detections retain the detector and board that actually produced them.
                current = request.config
                config = saved.config.model_copy(update={name: getattr(current, name) for name in (
                    'start_stage', 'base_run_id', 'sensor_group', 'calibration_toml_path', 'camera_matching',
                    'triangulation_config', 'filter_config', 'body_alignment')})
                config = config.model_copy(update={'sensor_group': group})
                board = config.charuco_board if any('charuco' in obs.stages for obs in saved.frames[0].values()) else None
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
