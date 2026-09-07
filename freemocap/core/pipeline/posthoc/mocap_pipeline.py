"""Managed Mocap recording task: group detection, annotation, and reconstruction."""

import multiprocessing
from contextlib import ExitStack, closing
from dataclasses import dataclass, field
from multiprocessing.queues import Queue
from multiprocessing.sharedctypes import Synchronized
from pathlib import Path
from queue import Empty

from skellycam.core.ipc.process_management.managed_worker import ManagedWorker
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.core import DetectionStageConfig, TrackerConfig
from skellytracker.core.annotation.keypoint_annotator import KeypointAnnotator
from skellytracker.core.data_primitives.observation import Observation
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition, CharucoDetectorConfig

from freemocap.core.pipeline.abcs.pipeline_abc import PipelineABC
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc.annotation_input import AnnotationInput
from freemocap.core.pipeline.posthoc.annotation_output import AnnotationOutputRequest, AnnotationVideoOutput
from freemocap.core.pipeline.posthoc.mocap_detection import MocapDetectionRequest, detect_mocap_recording
from freemocap.core.pipeline.posthoc.pipeline_phases import AggregatorPhase, PosthocPipelineType
from freemocap.core.pipeline.posthoc.progress_messages import AggregatorNodeProgressMessage, PipelineProgressMessage
from freemocap.core.pipeline.posthoc.task_progress_reporter import TaskProgressReporter
from freemocap.core.pipeline.posthoc.annotation_style import build_observation_annotator
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
    progress_queue: Queue

    def report(self, stage: str, detail: str, fraction: float) -> None:
        self.progress_queue.put(AggregatorNodeProgressMessage(
            pipeline_id=self.pipeline_id, pipeline_type=str(PosthocPipelineType.MOCAP),
            phase=stage, detail=detail, progress_fraction=fraction,
            recording_name=self.recording.recording_name,
            recording_path=str(self.recording.full_recording_path),
        ))


def run_mocap_pipeline(*, request: MocapWorkerRequest) -> None:
    try:
        request.report(AggregatorPhase.SETTING_UP, "Loading recording and detectors", 0.0)
        observations: list[dict[str, Observation]] = []
        video_metadata: dict[str, VideoMetadata] = {}
        selected_board: CharucoBoardDefinition | None = None
        resolved_config = request.config
        annotator: KeypointAnnotator = build_observation_annotator(request.config.tracker_config)
        outputs: dict[str, AnnotationVideoOutput] = {}
        with ExitStack() as cleanup:
            frames = cleanup.enter_context(closing(detect_mocap_recording(MocapDetectionRequest(
                recording_path=Path(request.recording.full_recording_path),
                tracker_config=request.config.tracker_config,
                detect_board=request.config.charuco_tracking_enabled,
                auto_select_board=request.config.board_mode == CharucoBoardMode.AUTO,
                board=request.config.charuco_board, should_continue=lambda: request.ipc.should_continue,
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
                    annotator = build_observation_annotator(tracker_config)
                for camera_id, observation in frame.observations.items():
                    if camera_id not in outputs:
                        output = AnnotationVideoOutput(AnnotationOutputRequest(
                            recording_path=Path(request.recording.full_recording_path), pipeline_id=request.pipeline_id,
                            video=video_metadata[camera_id], input_mode=AnnotationInput.RAW,
                        ))
                        cleanup.callback(output.close)
                        outputs[camera_id] = output
                    outputs[camera_id].write_frame(image=frame.images[camera_id], observation=observation, annotator=annotator)
                observations.append(frame.observations)
                if len(observations) % max(1, frame.frame_count // 50) == 0 or len(observations) == frame.frame_count:
                    request.report(AggregatorPhase.COLLECTING_CAMERA_OUTPUT,
                        f"Detecting and annotating {len(observations)}/{frame.frame_count} synchronized frames",
                        len(observations) / frame.frame_count)
            if not request.ipc.should_continue:
                return
            if not observations:
                raise ValueError("Mocap detection produced no frames")
            for output in outputs.values():
                output.publish()
        if not request.ipc.should_continue:
            return
        run_posthoc_mocap_task(
            frame_observations=observations, recording_info=request.recording,
            video_metadata=video_metadata, task_config=resolved_config, selected_board=selected_board,
            reporter=TaskProgressReporter(callback=request.report),
        )
        if request.ipc.should_continue:
            request.report(AggregatorPhase.COMPLETE, "Mocap processing complete", 1.0)
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
    progress_queue: Queue
    pipeline_type: PosthocPipelineType = field(default=PosthocPipelineType.MOCAP, init=False)
    started: bool = False
    _latest: dict[str, PipelineProgressMessage] = field(default_factory=dict)

    @classmethod
    def create(
        cls, *, pipeline_id: str, recording_info: RecordingInfo, config: PosthocMocapPipelineConfig,
        worker_registry: WorkerRegistry, global_kill_flag: Synchronized,
    ) -> "MocapPipeline":
        ipc = PipelineIPC.create(global_kill_flag=global_kill_flag,
            heartbeat_timestamp=worker_registry.heartbeat_timestamp, pipeline_id=pipeline_id)
        progress_queue = multiprocessing.Queue()
        request = MocapWorkerRequest(pipeline_id=pipeline_id, recording=recording_info,
            config=config, ipc=ipc, progress_queue=progress_queue)
        try:
            worker = worker_registry.create_worker(
                shutdown_flag=ipc.pipeline_shutdown_flag, worker_mode=worker_registry.worker_mode,
                target=run_mocap_pipeline, name=f"Mocap-{pipeline_id}", log_queue=ipc.ws_queue,
                kwargs={"request": request},
            )
        except Exception:
            progress_queue.close()
            raise
        pipeline = cls(id=pipeline_id, recording_info=recording_info, ipc=ipc,
            worker=worker, progress_queue=progress_queue)
        pipeline._latest[pipeline_id] = AggregatorNodeProgressMessage(
            pipeline_id=pipeline_id, pipeline_type=str(PosthocPipelineType.MOCAP),
            phase=AggregatorPhase.SETTING_UP, detail="Mocap pipeline queued",
            recording_name=recording_info.recording_name,
            recording_path=str(recording_info.full_recording_path),
        )
        return pipeline

    @property
    def alive(self) -> bool:
        return self.worker.is_alive()

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
            for message in self._latest.values()
        )
        if (self.worker.failure_exitcode is not None or exited_without_outcome) and not any(
            message.phase == AggregatorPhase.FAILED for message in self._latest.values()
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
        self.progress_queue.close()
        self.progress_queue.join_thread()
