"""
VideoNode: reads frames from a video file, runs a detector, publishes observations.

Generic video processing node parameterized by BaseDetectorConfig — the same node
handles charuco detection, mediapipe detection, or any future detector type.

Optionally saves annotated video output. If an existing annotated video is found
in the annotated_videos/ folder, new annotations are drawn on top of those frames
(allowing layering of e.g. charuco + mediapipe annotations). Otherwise, annotations
are drawn on the source video frames.
"""
import logging
import multiprocessing
from dataclasses import dataclass
from multiprocessing.sharedctypes import Synchronized
from pathlib import Path

import cv2
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseDetectorConfig
from skellytracker.trackers.base_tracker.detector_helpers import create_detector_from_config, \
    create_annotator_from_config

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.abcs.source_node_abc import SourceNode
from freemocap.core.types.type_overloads import VideoIdString, TopicPublicationQueue, PipelineIdString, \
    TopicSubscriptionQueue
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import VideoNodeOutputTopic, VideoNodeOutputMessage, VideoNodeProgressTopic, \
    VideoNodeProgressMessage, PipelineProgressMessage

logger = logging.getLogger(__name__)

ANNOTATED_VIDEOS_FOLDER_NAME = "annotated_videos"


@dataclass
class VideoNode(SourceNode):
    video_id: VideoIdString
    video_path: Path
    progress_subscription: TopicSubscriptionQueue

    @classmethod
    def create(
        cls,
        *,
        video_id: VideoIdString,
        video_path: Path,
        detector_config: BaseDetectorConfig,
        worker_registry: WorkerRegistry,
        ipc: PipelineIPC,
        pubsub: PubSubTopicManager,
        recording_path: Path,
        save_annotated_video: bool = True,
        pipeline_id: PipelineIdString | None = None,
    ) -> "VideoNode":
        shutdown_self_flag, worker = cls._create_worker(
            target=cls._run,
            name=f"VideoNode-{video_path.stem}",
            worker_registry=worker_registry,
            log_queue=ipc.ws_queue,
            kwargs=dict(
                video_id=video_id,
                video_path=video_path,
                detector_config=detector_config,
                ipc=ipc,
                video_output_pub=pubsub.get_publication_queue(
                    VideoNodeOutputTopic,
                ),
                video_progress_pub = pubsub.get_publication_queue(
                    VideoNodeProgressTopic
                ),
                recording_path=recording_path,
                save_annotated_video=save_annotated_video,
                pipeline_id=pipeline_id,
            ),
        )
        return cls(
            video_id=video_id,
            video_path=video_path,
            shutdown_self_flag=shutdown_self_flag,
            worker=worker,
            progress_subscription=pubsub.get_subscription(VideoNodeProgressTopic)
        )

    @staticmethod
    def _resolve_annotated_video_paths(
        *,
        recording_path: Path,
        video_path: Path,
    ) -> tuple[Path, Path | None]:
        """
        Determine the output path for the annotated video and check if an
        existing annotated video can be used as the base for layered annotation.

        Returns:
            (output_path, existing_base_path_or_none)
        """
        annotated_dir = recording_path / ANNOTATED_VIDEOS_FOLDER_NAME
        annotated_dir.mkdir(parents=True, exist_ok=True)

        output_path = annotated_dir / f"{video_path.stem}_annotated{video_path.suffix}"




        # If an annotated video already exists, rename it so we can read from it
        # while writing the new layered version
        existing_base_path: Path | None = None
        if output_path.exists():
            existing_base_path = output_path.with_suffix(
                f".prev{output_path.suffix}"
            )
            if existing_base_path.exists():
                existing_base_path.unlink()
            output_path.rename(existing_base_path)
            logger.info(
                f"Found existing annotated video for {video_path.stem}, "
                f"will layer new annotations on top"
            )

        return output_path, existing_base_path

    @staticmethod
    def _run(
        *,
        video_id: VideoIdString,
        video_path: Path,
        detector_config: BaseDetectorConfig,
        ipc: PipelineIPC,
        video_output_pub: TopicPublicationQueue,
        video_progress_pub: TopicPublicationQueue,
        shutdown_self_flag: Synchronized,
        recording_path: Path,
        save_annotated_video: bool,
        pipeline_id: PipelineIdString,
    ) -> None:
        detector = create_detector_from_config(detector_config)
        video_reader = cv2.VideoCapture(str(video_path), cv2.CAP_FFMPEG)
        if not video_reader.isOpened():
            raise RuntimeError(f"Failed to open video file: {video_path}")
        frame_count: int = int(video_reader.get(cv2.CAP_PROP_FRAME_COUNT))
        progress_message = VideoNodeProgressMessage(video_id=video_id,
                                                    pipeline_id=pipeline_id,
                                                    frame_count=frame_count,)
        video_progress_pub.put(progress_message)

        # Set up annotation pipeline if requested
        annotator = None
        video_writer: cv2.VideoWriter | None = None
        base_reader: cv2.VideoCapture | None = None
        prev_annotated_path: Path | None = None



        if save_annotated_video:
            annotator = create_annotator_from_config(detector_config)
            annotated_output_path, prev_annotated_path = VideoNode._resolve_annotated_video_paths(
                recording_path=recording_path,
                video_path=video_path,
            )

            # Open base reader if we have a previous annotated video to layer on
            if prev_annotated_path is not None:
                base_reader = cv2.VideoCapture(str(prev_annotated_path), cv2.CAP_FFMPEG)
                if not base_reader.isOpened():
                    logger.warning(
                        f"Failed to open previous annotated video for {video_path.stem} — "
                        f"will annotate from source frames instead"
                    )
                    base_reader = None

            # Create video writer matching source video properties
            fps = video_reader.get(cv2.CAP_PROP_FPS)
            width = int(video_reader.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(video_reader.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            video_writer = cv2.VideoWriter(
                str(annotated_output_path), fourcc, fps, (width, height)
            )
            if not video_writer.isOpened():
                raise RuntimeError(
                    f"Failed to create video writer for: {annotated_output_path}"
                )

        logger.info(
            f"VideoNode started for {video_path.stem}"
            f"{' (with annotation)' if save_annotated_video else ''}"
        )

        frame_number: int = 0
        try:

            success, image = video_reader.read()
            while success and not shutdown_self_flag.value and ipc.should_continue:
                observation = detector.detect(
                    frame_number=frame_number,
                    image=image,
                )
                video_output_pub.put(
                    VideoNodeOutputMessage(
                        video_id=video_id,
                        frame_number=frame_number,
                        observation=observation,
                    ),
                )




                # Annotate and write frame if enabled
                if annotator is not None and video_writer is not None:
                    # Use previous annotated frame as base if available, else source frame
                    if base_reader is not None:
                        base_ok, base_frame = base_reader.read()
                        if not base_ok or base_frame is None:
                            logger.warning(
                                f"Previous annotated video ran out of frames at frame {frame_number} "
                                f"for {video_path.stem} — falling back to source frames"
                            )
                            base_reader.release()
                            base_reader = None
                            annotation_base = image
                        else:
                            annotation_base = base_frame
                    else:
                        annotation_base = image

                    annotated_frame = annotator.annotate_image(
                        image=annotation_base,
                        observation=observation,
                    )
                    video_writer.write(annotated_frame)

                success, image = video_reader.read()
                frame_number += 1
                video_progress_pub.put(progress_message.increment())

            logger.info(
                f"VideoNode for {video_path.stem} finished reading "
                f"{frame_number} frames"
            )

        except Exception as e:
            logger.exception(
                f"Exception in VideoNode for {video_path.stem}: {e}"
            )
            progress_message.error = True
            video_progress_pub.put(progress_message)
            ipc.shutdown_pipeline()
            raise
        finally:
            video_reader.release()
            progress_message.complete = True
            video_progress_pub.put(progress_message)
            if video_writer is not None:
                video_writer.release()
            if base_reader is not None:
                base_reader.release()
            # Clean up the .prev file after we're done reading from it
            if prev_annotated_path is not None and prev_annotated_path.exists():
                prev_annotated_path.unlink()
            logger.debug(f"VideoNode for {video_path.stem} exiting")

    def get_progress_messages(self) -> list[PipelineProgressMessage]:
        messages: list[VideoNodeProgressMessage] = []
        while not self.progress_subscription.empty():
            messages.append(self.progress_subscription.get())
        return messages
