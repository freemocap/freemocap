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
import pickle
from dataclasses import dataclass
from multiprocessing.sharedctypes import Synchronized
from pathlib import Path

import cv2
from tqdm import tqdm
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseDetectorConfig, BaseObservation
from skellytracker.trackers.base_tracker.detector_helpers import create_detector_from_config, \
    create_annotator_from_config
from skellytracker.trackers.charuco_tracker.charuco_observation import CharucoObservation

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.abcs.source_node_abc import SourceNode
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.posthoc.pipeline_phases import VideoNodePhase, PosthocPipelineType
from freemocap.core.pipeline.posthoc.progress_messages import VideoNodeProgressMessage, PipelineProgressMessage
from freemocap.core.types.type_overloads import TopicPublicationQueue, PipelineIdString, \
    TopicSubscriptionQueue
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import VideoNodeOutputTopic, VideoNodeOutputMessage
from freemocap.system.default_paths import ANNOTATED_VIDEOS_FOLDER_NAME

logger = logging.getLogger(__name__)



@dataclass
class VideoNode(SourceNode):
    camera_id: CameraIdString
    video_path: Path
    progress_subscription: TopicSubscriptionQueue

    @classmethod
    def create(
        cls,
        *,
        camera_id: CameraIdString,
        video_path: Path,
        detector_config: BaseDetectorConfig,
        worker_registry: WorkerRegistry,
        ipc: PipelineIPC,
        pubsub: PubSubTopicManager,
        recording_path: Path,
        pipeline_type: PosthocPipelineType,
        save_annotated_video: bool = True,
        pipeline_id: PipelineIdString | None = None,
    ) -> "VideoNode":
        _progress_queue: multiprocessing.queues.Queue = multiprocessing.Queue()
        shutdown_self_flag, worker = cls._create_worker(
            target=cls._run,
            name=f"VideoNode-{video_path.stem}",
            worker_registry=worker_registry,
            log_queue=ipc.ws_queue,
            kwargs=dict(
                camera_id=camera_id,
                video_path=video_path,
                detector_config=detector_config,
                ipc=ipc,
                video_output_pub=pubsub.get_publication_queue(
                    VideoNodeOutputTopic,
                ),
                video_progress_pub=_progress_queue,
                recording_path=recording_path,
                save_annotated_video=save_annotated_video,
                pipeline_id=pipeline_id,
                pipeline_type=pipeline_type,
            ),
        )
        return cls(
            camera_id=camera_id,
            video_path=video_path,
            shutdown_self_flag=shutdown_self_flag,
            worker=worker,
            progress_subscription=_progress_queue,
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
        camera_id: CameraIdString,
        video_path: Path,
        detector_config: BaseDetectorConfig,
        ipc: PipelineIPC,
        video_output_pub: TopicPublicationQueue,
        video_progress_pub: TopicPublicationQueue,
        shutdown_self_flag: Synchronized,
        recording_path: Path,
        save_annotated_video: bool,
        pipeline_id: PipelineIdString,
        pipeline_type: PosthocPipelineType,
    ) -> None:
        # Compound pipeline_id groups this camera node under the base pipeline on the frontend.
        node_pipeline_id = f"{pipeline_id}:{camera_id}"
        # Emit immediately so the frontend shows the pipeline before the (potentially slow) model load.
        video_progress_pub.put(VideoNodeProgressMessage(
            camera_id=camera_id,
            pipeline_id=node_pipeline_id,
            pipeline_type=str(pipeline_type),
            phase=VideoNodePhase.SETTING_UP,
            progress_fraction=0.0,
            detail="Loading detector...",
            recording_name=recording_path.name,
            recording_path=str(recording_path),
        ))
        detector = create_detector_from_config(detector_config)

        # Try to load cached Charuco observations from a prior realtime
        # recording. On cache hit, detection is skipped per-frame but video
        # I/O and frame sequencing are completely unchanged.
        cache = _try_load_cache(
            recording_path=recording_path,
            camera_id=camera_id,
            detector_config=detector_config,
        )
        if cache is not None:
            logger.info(
                f"VideoNode [{camera_id}]: using cached observations "
                f"({len(cache)} frames) — detection will be skipped"
            )

        video_reader = cv2.VideoCapture(str(video_path), cv2.CAP_FFMPEG)
        if not video_reader.isOpened():
            raise RuntimeError(f"Failed to open video file: {video_path}")
        frame_count: int = int(video_reader.get(cv2.CAP_PROP_FRAME_COUNT))
        video_progress_pub.put(VideoNodeProgressMessage(
            camera_id=camera_id,
            pipeline_id=node_pipeline_id,
            pipeline_type=str(pipeline_type),
            phase=VideoNodePhase.SETTING_UP,
            progress_fraction=0.0,
            detail=f"Preparing {frame_count} frames",
            recording_name=recording_path.name,
            recording_path=str(recording_path),
        ))

        # Set up annotation pipeline if requested
        annotator = None
        video_writer: cv2.VideoWriter | None = None
        base_reader: cv2.VideoCapture | None = None
        prev_annotated_path: Path | None = None

        frame_number: int = 0
        _error_occurred = False
        try:
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
                # Prefer H.264 ("avc1") so annotated videos play directly in browsers/Electron's
                # <video> element. Fall back to "mp4v" if the local OpenCV/ffmpeg build lacks an
                # H.264 encoder — playable in desktop players but not in <video> tags.
                video_writer = cv2.VideoWriter(
                    str(annotated_output_path), cv2.VideoWriter_fourcc(*"avc1"), fps, (width, height)
                )
                if not video_writer.isOpened():
                    video_writer.release()
                    logger.warning(
                        f"H.264 ('avc1') encoder unavailable for {video_path.stem} — "
                        f"falling back to 'mp4v' (annotated video will not play in browser <video> tags)"
                    )
                    video_writer = cv2.VideoWriter(
                        str(annotated_output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
                    )
                if not video_writer.isOpened():
                    raise RuntimeError(
                        f"Failed to create video writer for: {annotated_output_path}"
                    )

            logger.info(
                f"VideoNode started for {video_path.stem}"
                f"{' (with annotation)' if save_annotated_video else ''}"
            )
            with tqdm(
                total=frame_count,
                desc=video_path.stem,
                unit="frame",
                leave=True,
                dynamic_ncols=True,
            ) as pbar:
                success, image = video_reader.read()
                while success and not shutdown_self_flag.value and ipc.should_continue:
                    observation = _get_observation(
                        frame_number=frame_number,
                        image=image,
                        detector=detector,
                        cache=cache,
                    )
                    video_output_pub.put(
                        VideoNodeOutputMessage(
                            camera_id=camera_id,
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
                    video_progress_pub.put(VideoNodeProgressMessage(
                        camera_id=camera_id,
                        pipeline_id=node_pipeline_id,
                        pipeline_type=str(pipeline_type),
                        phase=VideoNodePhase.PROCESSING_IMAGES,
                        progress_fraction=frame_number / frame_count,
                        detail=f"Camera {camera_id}: {frame_number}/{frame_count} frames",
                        recording_name=recording_path.name,
                        recording_path=str(recording_path),
                    ))
                    pbar.update(1)

            logger.info(
                f"VideoNode for {video_path.stem} finished reading "
                f"{frame_number} frames"
            )

        except Exception as e:
            logger.exception(
                f"Exception in VideoNode for {video_path.stem}: {e}"
            )
            _error_occurred = True
            video_progress_pub.put(VideoNodeProgressMessage(
                camera_id=camera_id,
                pipeline_id=node_pipeline_id,
                pipeline_type=str(pipeline_type),
                phase=VideoNodePhase.FAILED,
                progress_fraction=frame_number / frame_count if frame_count > 0 else 0.0,
                detail=f"{type(e).__name__}: {e}",
                recording_name=recording_path.name,
                recording_path=str(recording_path),
            ))
            ipc.shutdown_pipeline()
            # Do NOT re-raise: unhandled exceptions here kill the worker, and the WorkerRegistry
            # child monitor escalates that to a parent-process shutdown (exit code 15).
            # The error is surfaced via the progress message so the frontend can report it.
        finally:
            video_reader.release()
            if not _error_occurred:
                video_progress_pub.put(VideoNodeProgressMessage(
                    camera_id=camera_id,
                    pipeline_id=node_pipeline_id,
                    pipeline_type=str(pipeline_type),
                    phase=VideoNodePhase.COMPLETE,
                    progress_fraction=1.0,
                    recording_name=recording_path.name,
                    recording_path=str(recording_path),
                ))
            if video_writer is not None:
                video_writer.release()
            if base_reader is not None:
                base_reader.release()
            # Clean up the .prev file after we're done reading from it
            if prev_annotated_path is not None and prev_annotated_path.exists():
                prev_annotated_path.unlink()
            logger.debug(f"VideoNode for {video_path.stem} exiting")

    def get_progress_messages(self) -> list[PipelineProgressMessage]:
        from queue import Empty
        messages: list[VideoNodeProgressMessage] = []
        while True:
            try:
                messages.append(self.progress_subscription.get_nowait())
            except Empty:
                break
        return messages


CACHE_FILENAME = "charuco_observations_realtime.pkl"


def _try_load_cache(
    *,
    recording_path: Path,
    camera_id: CameraIdString,
    detector_config: BaseDetectorConfig,
) -> dict[int, BaseObservation] | None:
    """Load the realtime Charuco observation cache if it exists and matches.

    Returns a dict mapping ``frame_number`` → ``CharucoObservation``, or
    ``None`` if the cache is missing, corrupt, or has a mismatched board config.
    """
    cache_path = recording_path / "output_data" / CACHE_FILENAME
    if not cache_path.exists():
        logger.debug(f"No Charuco observation cache at {cache_path}")
        return None

    try:
        with open(cache_path, "rb") as f:
            cache_data = pickle.load(f)
    except Exception:
        logger.warning(
            f"Failed to load Charuco observation cache from {cache_path} — "
            f"falling back to normal detection",
            exc_info=True,
        )
        return None

    cached_board = cache_data.get("board_definition")
    if cached_board is None:
        logger.warning("Cache missing board_definition — rejecting")
        return None

    # Compare key board parameters against the detector config.
    # CharucoDetectorConfig delegates board properties, so we can compare
    # directly. For non-charuco configs the cache simply won't match.
    try:
        if (
            cached_board.squares_x != detector_config.squares_x
            or cached_board.squares_y != detector_config.squares_y
            or abs(cached_board.square_length_mm - detector_config.square_length_mm) > 0.01
            or cached_board.aruco_dictionary_enum != detector_config.aruco_dictionary_enum
        ):
            logger.info(
                f"Cache board config mismatch — "
                f"cache=({cached_board.squares_x}x{cached_board.squares_y}, "
                f"{cached_board.square_length_mm}mm), "
                f"request=({detector_config.squares_x}x{detector_config.squares_y}, "
                f"{detector_config.square_length_mm}mm) — "
                f"falling back to normal detection"
            )
            return None
    except AttributeError:
        # detector_config is not a CharucoDetectorConfig (e.g. MediaPipe)
        logger.debug("Detector config is not charuco — cache does not apply")
        return None

    observations = cache_data.get("observations", {})
    if camera_id not in observations:
        logger.info(
            f"Camera {camera_id} not found in cache — "
            f"falling back to normal detection"
        )
        return None

    obs_list = observations[camera_id]
    logger.info(
        f"Loaded {len(obs_list)} cached Charuco observations "
        f"for camera {camera_id} from {cache_path}"
    )
    return {frame_number: obs for frame_number, obs in enumerate(obs_list)}


def _get_observation(
    *,
    frame_number: int,
    image,
    detector,
    cache: dict[int, BaseObservation] | None,
) -> BaseObservation:
    """Get observation for a frame — from cache if available, else detect.

    The video I/O loop is completely unchanged. The cache only determines
    whether ``detector.detect()`` is called on the image.
    """
    if cache is not None and frame_number in cache:
        return cache[frame_number]

    return detector.detect(
        frame_number=frame_number,
        image=image,
    )
