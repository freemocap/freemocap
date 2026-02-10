"""
VideoNode: reads frames from a video file, runs a detector, publishes observations.

Generic video processing node parameterized by DetectorSpec — the same node
handles charuco detection, mediapipe detection, or any future detector type.
"""
import logging
import multiprocessing
from dataclasses import dataclass
from pathlib import Path

import cv2

from freemocap.core.pipeline.shared.pipeline_configs import DetectorSpec, create_detector_from_spec
from freemocap.core.pipeline.shared.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.shared.base_node import BaseNode
from freemocap.core.types.type_overloads import VideoIdString
from freemocap.pubsub.pubsub_topics import VideoNodeOutputTopic, VideoNodeOutputMessage
from skellycam.core.ipc.process_management.process_registry import ProcessRegistry

logger = logging.getLogger(__name__)


@dataclass
class VideoNode(BaseNode):
    video_id: VideoIdString
    video_path: Path

    @classmethod
    def create(
        cls,
        *,
        video_id: VideoIdString,
        video_path: Path,
        detector_spec: DetectorSpec,
        process_registry: ProcessRegistry,
        ipc: PipelineIPC,
    ) -> "VideoNode":
        shutdown_self_flag, worker = cls._create_worker(
            target=cls._run,
            name=f"VideoNode-{video_path.stem}",
            process_registry=process_registry,
            log_queue=ipc.ws_queue,
            kwargs=dict(
                video_id=video_id,
                video_path=video_path,
                detector_spec=detector_spec,
                ipc=ipc,
            ),
        )
        return cls(
            video_id=video_id,
            video_path=video_path,
            shutdown_self_flag=shutdown_self_flag,
            worker=worker,
        )

    @staticmethod
    def _run(
        *,
        video_id: VideoIdString,
        video_path: Path,
        detector_spec: DetectorSpec,
        ipc: PipelineIPC,
        shutdown_self_flag: multiprocessing.Value,
    ) -> None:
        detector = create_detector_from_spec(detector_spec)
        video_reader = cv2.VideoCapture(str(video_path))
        if not video_reader.isOpened():
            raise RuntimeError(f"Failed to open video file: {video_path}")

        logger.info(f"VideoNode started for {video_path.stem}")
        frame_number: int = 0
        try:
            success, image = video_reader.read()
            while success and not shutdown_self_flag.value and ipc.should_continue:
                observation = detector.detect(
                    frame_number=frame_number,
                    image=image,
                )
                ipc.pubsub.publish(
                    topic_type=VideoNodeOutputTopic,
                    message=VideoNodeOutputMessage(
                        video_id=video_id,
                        frame_number=frame_number,
                        observation=observation,
                    ),
                )
                success, image = video_reader.read()
                frame_number += 1

            logger.info(
                f"VideoNode for {video_path.stem} finished reading "
                f"{frame_number} frames"
            )

        except Exception as e:
            logger.exception(
                f"Exception in VideoNode for {video_path.stem}: {e}"
            )
            ipc.shutdown_pipeline()
            raise
        finally:
            video_reader.release()
            logger.debug(f"VideoNode for {video_path.stem} exiting")