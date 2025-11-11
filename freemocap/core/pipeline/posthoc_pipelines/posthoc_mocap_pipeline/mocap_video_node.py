import logging
import multiprocessing
from dataclasses import dataclass
from pathlib import Path

from skellycam.core.types.type_overloads import WorkerType
from skellytracker.trackers.mediapipe_tracker.mediapipe_detector import MediapipeDetector

from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc_pipelines.posthoc_mocap_pipeline.posthoc_mocap_pipeline import \
    MocapPipelineTaskConfig
from freemocap.core.pipeline.posthoc_pipelines.video_helper import VideoHelper
from freemocap.core.types.type_overloads import VideoIdString
from freemocap.pubsub.pubsub_topics import VideoNodeOutputTopic, VideoNodeOutputMessage

logger = logging.getLogger(__name__)


@dataclass
class MocapVideoNode:
    video_id: VideoIdString
    video_path: Path
    mocap_task_config: MocapPipelineTaskConfig
    shutdown_self_flag: multiprocessing.Value
    worker: WorkerType

    @classmethod
    def create(cls,
               video_id: VideoIdString,
               video_path: Path,
               subprocess_registry: list[multiprocessing.Process],
               mocap_task_config: MocapPipelineTaskConfig,
               ipc: PipelineIPC):
        shutdown_self_flag = multiprocessing.Value('b', False)
        worker = multiprocessing.Process(target=cls._run,
                                         name=f"VideoProcessingNode-{video_path.stem}",
                                         kwargs=dict(
                                             video_id=video_id,
                                             video_path=video_path,
                                             ipc=ipc,
                                             mocap_task_config=mocap_task_config,
                                             shutdown_self_flag=shutdown_self_flag,
                                         ),
                                         daemon=True
                                         )
        subprocess_registry.append(worker)
        return cls(video_id=video_id,
                   video_path=video_path,
                   shutdown_self_flag=shutdown_self_flag,
                   mocap_task_config=mocap_task_config,
                   worker=worker
                   )

    @staticmethod
    def _run(video_id: VideoIdString,
             video_path: Path,
             ipc: PipelineIPC,
             mocap_task_config: MocapPipelineTaskConfig,
             shutdown_self_flag: multiprocessing.Value,
             ):
        if multiprocessing.parent_process():
            # Configure logging if multiprocessing (i.e. if there is a parent process)
            from freemocap.system.logging_configuration.configure_logging import configure_logging
            from freemocap import LOG_LEVEL
            configure_logging(LOG_LEVEL, ws_queue=ipc.ws_queue)

        with VideoHelper.from_video_path(video_path=video_path) as video:
            logger.info(f"Starting video processing node for video: {video.video_path.stem}")

            mediapipe_detector = MediapipeDetector.create(config=mocap_task_config.detector_config)
            try:
                while video.has_frames and not shutdown_self_flag.value and ipc.should_continue:
                    image = video.read_next_frame()
                    mediapipe_observation = mediapipe_detector.detect(
                        frame_number=video.last_read_frame,
                        image=image)

                    ipc.pubsub.publish(
                        topic_type=VideoNodeOutputTopic,
                        message=VideoNodeOutputMessage(
                            video_id=video_id,
                            frame_number=video.last_read_frame,
                            observation=mediapipe_observation,
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
