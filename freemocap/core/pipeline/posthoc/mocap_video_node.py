"""Thread-owned sequential decoding, board detection, and annotation encoding."""

from concurrent.futures import Future
from contextlib import ExitStack
from dataclasses import dataclass, field
from pathlib import Path
from queue import Empty, Queue

from tqdm import tqdm

import numpy as np
from numpy.typing import NDArray
from skellycam.core.ipc.process_management.managed_worker import WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.sequential_video_reader import SequentialVideoReader
from skellytracker.core import Tracker, TrackerConfig, DetectionStageConfig
from skellytracker.core.data_primitives.observation import Observation
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition, CharucoDetectorConfig
from skellytracker.core.tracker.tracker_state import TrackerState

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc.annotation_input import AnnotationInput
from freemocap.core.pipeline.posthoc.annotation_output import AnnotationOutputRequest, AnnotationVideoOutput
from freemocap.core.pipeline.posthoc.annotation_style import build_observation_annotator
from freemocap.core.pipeline.posthoc.progress_messages import PipelineProgressMessage, VideoNodeProgressMessage
from freemocap.core.pipeline.posthoc.pipeline_phases import VideoNodePhase, PosthocPipelineType
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.tracking.tracker_factory import build_charuco_tracker, CHARUCO_STAGE_NAME


@dataclass(frozen=True)
class VideoWorkerConfig:
    camera_id: str
    video: VideoMetadata
    recording_path: Path
    tracker_config: TrackerConfig
    ipc: PipelineIPC
    progress: Queue[PipelineProgressMessage]


@dataclass
class ReadFrame:
    number: int
    result: Future[NDArray[np.uint8]] = field(default_factory=Future)


@dataclass
class AnnotateFrame:
    image: NDArray[np.uint8]
    observation: Observation
    board: CharucoBoardDefinition | None
    result: Future[Observation] = field(default_factory=Future)


@dataclass
class FinishVideo:
    publish: bool
    result: Future[None] = field(default_factory=Future)


class MocapVideoNode:
    def __init__(self, *, config: VideoWorkerConfig, registry: WorkerRegistry) -> None:
        self.config = config
        self.commands: Queue[ReadFrame | AnnotateFrame | FinishVideo] = Queue(maxsize=2)
        self.failure: BaseException | None = None
        self.worker = registry.create_worker(
            shutdown_flag=config.ipc.pipeline_shutdown_flag, worker_mode=WorkerMode.THREAD,
            target=self._run, name=f"MocapVideo-{config.ipc.pipeline_id}-{config.camera_id}",
            log_queue=config.ipc.ws_queue,
        )

    def report(self, *, phase: VideoNodePhase, detail: str, fraction: float) -> None:
        self.config.progress.put(VideoNodeProgressMessage(
            pipeline_id=f"{self.config.ipc.pipeline_id}:{self.config.camera_id}",
            pipeline_type=PosthocPipelineType.MOCAP, camera_id=self.config.camera_id,
            phase=phase, detail=detail, progress_fraction=fraction,
            recording_name=self.config.recording_path.name, recording_path=str(self.config.recording_path),
        ))

    def _run(self) -> None:
        command: ReadFrame | AnnotateFrame | FinishVideo | None = None
        try:
            with ExitStack() as cleanup:
                reader = SequentialVideoReader(path=self.config.video.file_path)
                cleanup.callback(reader.close)
                output = AnnotationVideoOutput(AnnotationOutputRequest(
                    recording_path=self.config.recording_path, pipeline_id=self.config.ipc.pipeline_id,
                    video=self.config.video, input_mode=AnnotationInput.RAW,
                ))
                cleanup.callback(output.close)
                progress_bar = cleanup.enter_context(tqdm(
                    total=self.config.video.frame_count,
                    desc=f"[{self.config.ipc.pipeline_id}] {self.config.camera_id}",
                    unit="frame", leave=True, dynamic_ncols=True, mininterval=0.25,
                ))
                annotator = build_observation_annotator(self.config.tracker_config)
                board_tracker: Tracker | None = None
                board_state = TrackerState()
                self.report(phase=VideoNodePhase.SETTING_UP, detail=self.config.video.file_path.name, fraction=0.0)
                while self.config.ipc.should_continue:
                    try:
                        command = self.commands.get(timeout=0.05)
                    except Empty:
                        continue
                    if not command.result.set_running_or_notify_cancel():
                        raise RuntimeError("Video commands must be canceled through the pipeline")
                    if isinstance(command, ReadFrame):
                        command.result.set_result(reader.read_bgr(frame_number=command.number))
                    elif isinstance(command, AnnotateFrame):
                        if command.board is not None:
                            if board_tracker is None:
                                board_tracker, _ = build_charuco_tracker(board_def=command.board)
                                cleanup.callback(board_tracker.close)
                                annotator = build_observation_annotator(TrackerConfig(stages=[
                                    *self.config.tracker_config.stages,
                                    DetectionStageConfig(name=CHARUCO_STAGE_NAME,
                                        keypoint_detectors=[CharucoDetectorConfig(board=command.board)]),
                                ]))
                            board_observation, board_state = board_tracker.process_image(
                                image=command.image, frame_number=command.observation.frame_number, state=board_state,
                            )
                            if command.observation.stages.keys() & board_observation.stages.keys():
                                raise ValueError("Board and skeleton observation stages must be distinct")
                            command.observation.stages.update(board_observation.stages)
                        output.write_frame(image=command.image, observation=command.observation, annotator=annotator)
                        progress_bar.update(1)
                        count = command.observation.frame_number + 1
                        if count % max(1, self.config.video.frame_count // 50) == 0:
                            self.report(phase=VideoNodePhase.PROCESSING_IMAGES,
                                detail=f"Annotated {count}/{self.config.video.frame_count} frames",
                                fraction=count / self.config.video.frame_count)
                        command.result.set_result(command.observation)
                    else:
                        if command.publish:
                            output.publish()
                            self.report(phase=VideoNodePhase.COMPLETE, detail="Annotated video saved", fraction=1.0)
                            command.result.set_result(None)
                            return
                        try:
                            reader.read_bgr(frame_number=self.config.video.frame_count)
                        except IndexError:
                            command.result.set_result(None)
                        else:
                            raise ValueError(f"Video has more frames than declared: {self.config.video.file_path}")
                    command = None
        except BaseException as error:
            self.failure = error
            self.config.ipc.shutdown_pipeline()
            self.report(phase=VideoNodePhase.FAILED, detail=f"{type(error).__name__}: {error}", fraction=0.0)
            if command is not None and not command.result.done():
                command.result.set_exception(error)
            raise
        finally:
            while True:
                try:
                    pending = self.commands.get_nowait()
                except Empty:
                    break
                pending.result.cancel()

