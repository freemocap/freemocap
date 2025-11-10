import logging
import multiprocessing
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from skellycam.core.types.type_overloads import WorkerType
from skellytracker.trackers.charuco_tracker.charuco_detector import CharucoDetector

from freemocap.core.pipeline.posthoc_pipelines.posthoc_calibration_pipeline.posthoc_calibration_pipeline import \
    CalibrationTaskConfig
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc_pipelines.video_helper import VideoHelper
from freemocap.core.types.type_overloads import PipelineIdString
from freemocap.pubsub.pubsub_topics import VideoNodeOutputTopic, VideoNodeOutputMessage

logger = logging.getLogger(__name__)



class VideoNodeState(BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
        frozen=True
    )
    pipeline_id: PipelineIdString
    alive: bool
    last_seen_frame_number: int | None = None
    calibration_task_state: object | None = None
    mocap_task_state: object = None  # TODO - this


@dataclass
class CalibrationVideoNode:
    video_path:Path
    calibration_task_config: CalibrationTaskConfig
    shutdown_self_flag: multiprocessing.Value
    worker: WorkerType

    @classmethod
    def create(cls,
               video_path:Path,
               subprocess_registry: list[multiprocessing.Process],
               calibration_task_config: CalibrationTaskConfig,
               ipc: PipelineIPC):
        shutdown_self_flag = multiprocessing.Value('b', False)
        worker = multiprocessing.Process(target=cls._run,
                                         name=f"VideoProcessingNode-{video_path.stem}",
                                         kwargs=dict(video_path=video_path,
                                                     ipc=ipc,
                                                     calibration_task_config=calibration_task_config,
                                                     shutdown_self_flag=shutdown_self_flag,
                                                     ),
                                         daemon=True
                                         )
        subprocess_registry.append(worker)
        return cls(video_path=video_path,
                   shutdown_self_flag=shutdown_self_flag,
                     calibration_task_config=calibration_task_config,
                   worker=worker
                   )

    @staticmethod
    def _run(video_path:Path,
             ipc: PipelineIPC,
             calibration_task_config: CalibrationTaskConfig,
             shutdown_self_flag: multiprocessing.Value,
             ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.ws_queue)

        with VideoHelper.from_video_path(video_path=video_path) as video:
            logger.info(f"Starting video processing node for video: {video.video_path.stem}")

            charuco_detector = CharucoDetector.create(config=calibration_task_config.detector_config)
            try:
                while video.has_frames and not shutdown_self_flag.value and ipc.should_continue:
                    image = video.read_next_frame()
                    charuco_observation = charuco_detector.detect(
                        frame_number=video.last_read_frame,
                        image=image)

                    ipc.pubsub.publish(
                        topic_type=VideoNodeOutputTopic,
                        message=VideoNodeOutputMessage(
                            video_id=str(video.video_path),
                            frame_number=video.last_read_frame,
                            observation=charuco_observation,
                        ),
                    )
            except Exception as e:
                logger.exception(f"Exception in video node for video: {video.video_path.stem} - {e}")
                ipc.kill_everything()
                raise e
            finally:
                logger.debug(f"Shutting down video processing node for video: {video.video_path.stem}")
                video.close()

    def start(self):
        logger.debug(f"Starting {self.__class__.__name__} for video: {self.video_path.stem}")
        self.worker.start()

    def shutdown(self):
        logger.debug(f"Stopping {self.__class__.__name__} for video: {self.video_path.stem}")
        self.shutdown_self_flag.value = True
        self.worker.join()
