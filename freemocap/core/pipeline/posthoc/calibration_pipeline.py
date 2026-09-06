"""Resolve one calibration board before starting camera processing workers."""

import functools
import logging
from dataclasses import dataclass, field

from skellycam.core.ipc.process_management.managed_worker import ManagedWorker, WorkerMode
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardSelector, CharucoBoardSelectionError

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc.pipeline_phases import AggregatorPhase, PosthocPipelineType
from freemocap.core.pipeline.posthoc.posthoc_pipeline import PosthocPipeline
from freemocap.core.pipeline.posthoc.progress_messages import PipelineProgressMessage
from freemocap.core.pipeline.posthoc.video_group_helper import VideoGroupHelper
from freemocap.core.tasks.calibration.calibration_task_config import CalibrationBoardMode, PosthocCalibrationPipelineConfig
from freemocap.core.tasks.calibration.posthoc_calibration_task import run_posthoc_calibration_task

logger = logging.getLogger(__name__)


@dataclass
class CalibrationPipeline:
    id: str
    recording_info: RecordingInfo
    config: PosthocCalibrationPipelineConfig
    ipc: PipelineIPC
    worker_registry: WorkerRegistry
    pipeline_type: PosthocPipelineType = field(default=PosthocPipelineType.CALIBRATION, init=False)
    started: bool = field(default=False, init=False)
    worker: ManagedWorker = field(init=False)
    pipeline: PosthocPipeline | None = field(default=None, init=False)
    progress: PipelineProgressMessage = field(init=False)

    def __post_init__(self) -> None:
        self._set_progress(phase=AggregatorPhase.SETTING_UP, detail="Selecting calibration board")
        self.worker = self.worker_registry.create_worker(
            shutdown_flag=self.ipc.pipeline_shutdown_flag,
            worker_mode=WorkerMode.THREAD,
            target=self._prepare_calibration,
            name=f"CalibrationPreparation-{self.id}",
            log_queue=self.ipc.ws_queue,
        )

    def _set_progress(self, *, phase: AggregatorPhase, detail: str) -> None:
        self.progress = PipelineProgressMessage(
            pipeline_id=self.id, pipeline_type=self.pipeline_type,
            phase=phase, detail=detail,
            recording_name=self.recording_info.recording_name,
            recording_path=str(self.recording_info.full_recording_path),
        )

    @property
    def alive(self) -> bool:
        return self.worker.is_alive() or (self.pipeline is not None and self.pipeline.alive)

    def start(self) -> None:
        if self.started:
            raise RuntimeError("Calibration preparation already started")
        self.started = True
        self.worker.start()

    def _prepare_calibration(self) -> None:
        try:
            config = self.config
            if config.board_mode == CalibrationBoardMode.AUTO:
                selector = CharucoBoardSelector()
                group = VideoGroupHelper.from_recording_path(
                    recording_path=str(self.recording_info.full_recording_path),
                )
                selected = None
                try:
                    for frame_number in range(group.frame_count):
                        for video in group.videos.values():
                            if not self.ipc.should_continue:
                                return
                            selected = selector.observe_image(image=video.read_frame_number(frame_number=frame_number))
                            if selected is not None:
                                break
                        if selected is not None:
                            break
                finally:
                    group.close()
                if selected is None:
                    raise CharucoBoardSelectionError("AUTO could not detect a supported 5x3 or 7x5 calibration board in the recording.")
                selected = selected.model_copy(update={"square_length_mm": config.charuco_board.square_length_mm})
                config = config.model_copy(update={"charuco_board": selected, "board_mode": CalibrationBoardMode.EXPLICIT})
                logger.info("AUTO selected %sx%s calibration board; user-configured square length: %s mm", selected.squares_x, selected.squares_y, selected.square_length_mm)
            if not self.ipc.should_continue:
                return
            self._set_progress(phase=AggregatorPhase.SETTING_UP, detail=f"Using {config.charuco_board.squares_x}x{config.charuco_board.squares_y} calibration board")
            self.pipeline = PosthocPipeline.create(
                pipeline_id=self.id,
                recording_info=self.recording_info,
                detector_config=config.detector_config,
                aggregation_task_fn=functools.partial(run_posthoc_calibration_task, task_config=config),
                pipeline_type=self.pipeline_type,
                worker_registry=self.worker_registry,
                global_kill_flag=self.ipc.global_kill_flag,
            )
            if self.ipc.should_continue:
                self.pipeline.start()
        except Exception as error:
            self._set_progress(phase=AggregatorPhase.FAILED, detail=f"{type(error).__name__}: {error}")
            self.ipc.shutdown_pipeline()
            logger.exception("Calibration preparation failed")

    def get_progress_messages(self) -> list[PipelineProgressMessage]:
        if self.progress.phase == AggregatorPhase.FAILED or self.pipeline is None:
            return [self.progress]
        messages = self.pipeline.get_progress_messages()
        return messages or [self.progress]

    def drain_and_get_messages(self) -> list[PipelineProgressMessage]:
        if self.pipeline is not None and self.progress.phase != AggregatorPhase.FAILED:
            return self.pipeline.drain_and_get_messages()
        return [self.progress]

    def shutdown(self) -> None:
        self.worker.mark_stopping()
        self.ipc.shutdown_pipeline()
        self.worker.terminate_gracefully()
        if self.pipeline is not None:
            self.pipeline.shutdown()
