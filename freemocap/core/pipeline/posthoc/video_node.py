"""
VideoNode: reads frames from a video file, runs a tracker, publishes observations.

Generic video processing node parameterized by TrackerConfig — the same node
handles charuco detection, RTMPose skeleton detection, or any future tracker type.

Annotations use raw frames by default, or an explicitly selected annotated input.
"""
from freemocap.core.pipeline.posthoc.annotation_style import build_observation_annotator

from freemocap.core.pipeline.posthoc.annotation_output import AnnotationOutputRequest, AnnotationVideoOutput
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.pipeline.posthoc.annotation_input import AnnotationInput

from skellycam.core.timestamps.recording_timing_reader import recorded_camera_timing_path
import csv
import logging
import multiprocessing
import pickle
from dataclasses import dataclass, replace
from multiprocessing.sharedctypes import Synchronized
from pathlib import Path

import cv2
from tqdm import tqdm
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellytracker.core import TrackerConfig
from skellytracker.core.data_primitives.observation import Observation
from skellytracker.core.detectors.keypoint_detectors.charuco import (
    CharucoDetectorConfig,
    CharucoBoardDefinition,
)
from skellytracker.core.tracker.tracker import Tracker
from skellytracker.core.tracker.tracker_state import TrackerState

from freemocap.core.tracking.tracker_factory import build_configured_tracker
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.abcs.source_node_abc import SourceNode
from skellycam.core.types.type_overloads import CameraIdString
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.pipeline.posthoc.pipeline_phases import VideoNodePhase, PosthocPipelineType
from freemocap.core.pipeline.posthoc.progress_messages import VideoNodeProgressMessage, PipelineProgressMessage
from freemocap.core.types.type_overloads import TopicPublicationQueue, PipelineIdString, \
    TopicSubscriptionQueue
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import VideoNodeOutputTopic, VideoNodeOutputMessage

logger = logging.getLogger(__name__)


def _cached_board_detector(tracker_config: TrackerConfig) -> CharucoDetectorConfig | None:
    """A board-only cache can satisfy only one independent board detection stage."""
    if len(tracker_config.stages) != 1:
        return None
    stage = tracker_config.stages[0]
    if stage.children or stage.object_detector is not None or len(stage.keypoint_detectors) != 1:
        return None
    detector = stage.keypoint_detectors[0]
    return detector if isinstance(detector, CharucoDetectorConfig) else None


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
        detector_config: TrackerConfig,
        worker_registry: WorkerRegistry,
        ipc: PipelineIPC,
        pubsub: PubSubTopicManager,
        recording_path: Path,
        pipeline_type: PosthocPipelineType,
        save_annotated_video: bool = True,
        annotation_input: AnnotationInput = AnnotationInput.RAW,
        pipeline_id: PipelineIdString | None = None,
    ) -> "VideoNode":
        _progress_queue: multiprocessing.queues.Queue = multiprocessing.Queue()
        shutdown_self_flag, worker = cls._create_worker(
            owner_shutdown_flag=ipc.pipeline_shutdown_flag,
            worker_mode=worker_registry.worker_mode,
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
                annotation_input=annotation_input,
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
    def _run(
        *,
        camera_id: CameraIdString,
        video_path: Path,
        detector_config: TrackerConfig,
        ipc: PipelineIPC,
        video_output_pub: TopicPublicationQueue,
        video_progress_pub: TopicPublicationQueue,
        shutdown_self_flag: Synchronized,
        recording_path: Path,
        save_annotated_video: bool,
        annotation_input: AnnotationInput,
        pipeline_id: PipelineIdString,
        pipeline_type: PosthocPipelineType,
    ) -> None:
        node_pipeline_id = f"{pipeline_id}:{camera_id}"
        video_progress_pub.put(VideoNodeProgressMessage(
            camera_id=camera_id,
            pipeline_id=node_pipeline_id,
            pipeline_type=str(pipeline_type),
            phase=VideoNodePhase.SETTING_UP,
            progress_fraction=0.0,
            detail="Loading tracker...",
            recording_name=recording_path.name,
            recording_path=str(recording_path),
        ))
        tracker = build_configured_tracker(config=detector_config, batch_size=1)
        tracker_state = TrackerState()

        cache = _build_recording_frame_cache(
            recording_path=recording_path,
            camera_id=camera_id,
            detector_config=detector_config,
        )
        if cache is not None:
            logger.info(
                f"VideoNode [{camera_id}]: reusing {len(cache)} realtime Charuco "
                f"observations — only uncached frames will be detected"
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

        annotator = None
        annotation_output: AnnotationVideoOutput | None = None

        frame_number: int = 0
        _error_occurred = False
        try:
            if save_annotated_video:
                annotator = build_observation_annotator(detector_config)
                fps = video_reader.get(cv2.CAP_PROP_FPS)
                annotation_output = AnnotationVideoOutput(AnnotationOutputRequest(
                    recording_path=recording_path, pipeline_id=pipeline_id, input_mode=annotation_input,
                    video=VideoMetadata(file_path=video_path, fps=fps, frame_count=frame_count,
                        width=int(video_reader.get(cv2.CAP_PROP_FRAME_WIDTH)),
                        height=int(video_reader.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                        fourcc="", duration_seconds=frame_count / fps, end_frame=frame_count),
                ))

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
                mininterval=0.25,
            ) as pbar:
                success, image = video_reader.read()
                while success and not shutdown_self_flag.value and ipc.should_continue:
                    observation, tracker_state = _get_observation(
                        frame_number=frame_number,
                        image=image,
                        tracker=tracker,
                        state=tracker_state,
                        cache=cache,
                    )
                    video_output_pub.put(
                        VideoNodeOutputMessage(
                            camera_id=camera_id,
                            frame_number=frame_number,
                            observation=observation,
                        ),
                    )

                    if annotator is not None and annotation_output is not None:
                        annotation_output.write_frame(image=image, observation=observation, annotator=annotator)

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

            if shutdown_self_flag.value or not ipc.should_continue:
                _error_occurred = True
            elif frame_number != frame_count:
                raise RuntimeError(f"Video ended after {frame_number} frames; expected {frame_count}: {video_path}")
            else:
                if annotation_output is not None:
                    annotation_output.publish()

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
        finally:
            tracker.close()
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
            if annotation_output is not None:
                annotation_output.close()
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


def _build_recording_frame_cache(
    *,
    recording_path: Path,
    camera_id: CameraIdString,
    detector_config: TrackerConfig,
) -> dict[int, Observation] | None:
    """Resolve the realtime cache into a {recording_frame_number: observation} map."""
    cache_by_connection_frame = _load_cache_by_connection_frame(
        recording_path=recording_path,
        camera_id=camera_id,
        detector_config=detector_config,
    )
    if cache_by_connection_frame is None:
        return None

    recording_to_connection = _load_recording_to_connection_frame_map(
        recording_path=recording_path,
        camera_id=camera_id,
    )
    if recording_to_connection is None:
        logger.warning(
            f"VideoNode [{camera_id}]: have a realtime Charuco cache but no "
            f"timestamps CSV to align it — detecting all frames to stay correct"
        )
        return None

    cache_by_recording_frame: dict[int, Observation] = {}
    for recording_frame_number, connection_frame_number in recording_to_connection.items():
        observation = cache_by_connection_frame.get(connection_frame_number)
        if observation is not None:
            cache_by_recording_frame[recording_frame_number] = replace(
                observation, frame_number=recording_frame_number
            )

    if not cache_by_recording_frame:
        logger.info(
            f"VideoNode [{camera_id}]: realtime cache had no observations "
            f"overlapping this recording's frames — detecting all frames"
        )
        return None

    logger.debug(
        f"VideoNode [{camera_id}]: aligned {len(cache_by_recording_frame)} of "
        f"{len(recording_to_connection)} recorded frames to realtime observations"
    )
    return cache_by_recording_frame


def _load_cache_by_connection_frame(
    *,
    recording_path: Path,
    camera_id: CameraIdString,
    detector_config: TrackerConfig,
) -> dict[int, Observation] | None:
    """Load realtime charuco observations keyed by connection frame number."""
    board_detector = _cached_board_detector(detector_config)
    if board_detector is None:
        return None

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
    if not isinstance(cached_board, CharucoBoardDefinition):
        logger.warning(
            f"VideoNode [{camera_id}]: cache board_definition is "
            f"{type(cached_board).__name__}, expected CharucoBoardDefinition — "
            f"rejecting cache (stale cache format)"
        )
        return None

    request_board = board_detector.board
    if (
        cached_board.squares_x != request_board.squares_x
        or cached_board.squares_y != request_board.squares_y
        or abs(cached_board.square_length_mm - request_board.square_length_mm) > 0.01
        or cached_board.aruco_dictionary_enum != request_board.aruco_dictionary_enum
    ):
        logger.info(
            f"VideoNode [{camera_id}]: cache board mismatch — "
            f"cache=({cached_board.squares_x}x{cached_board.squares_y}, "
            f"{cached_board.square_length_mm}mm, dict={cached_board.aruco_dictionary_enum}) "
            f"vs request=({request_board.squares_x}x{request_board.squares_y}, "
            f"{request_board.square_length_mm}mm, dict={request_board.aruco_dictionary_enum}) "
            f"— falling back to normal detection"
        )
        return None

    observations = cache_data.get("observations")
    if not isinstance(observations, dict):
        logger.warning(
            f"VideoNode [{camera_id}]: cache 'observations' is "
            f"{type(observations).__name__}, expected dict — rejecting cache"
        )
        return None

    if camera_id not in observations:
        logger.info(
            f"VideoNode [{camera_id}]: camera not present in cache "
            f"(have {list(observations.keys())}) — falling back to normal detection"
        )
        return None

    obs_by_connection_frame = observations[camera_id]
    if not isinstance(obs_by_connection_frame, dict):
        logger.warning(
            f"VideoNode [{camera_id}]: cached observations are "
            f"{type(obs_by_connection_frame).__name__}, expected dict — rejecting cache"
        )
        return None

    stage_name = detector_config.stages[0].name
    for observation in obs_by_connection_frame.values():
        if not isinstance(observation, Observation):
            raise TypeError(f"Invalid cached observation in {cache_path}")
        if set(observation.stages) != {stage_name} or observation.stages[stage_name].children:
            return None

    logger.info(
        f"Loaded {len(obs_by_connection_frame)} cached Charuco observations "
        f"for camera {camera_id} from {cache_path}"
    )
    return obs_by_connection_frame


def _load_recording_to_connection_frame_map(
    *,
    recording_path: Path,
    camera_id: CameraIdString,
) -> dict[int, int] | None:
    csv_path = recorded_camera_timing_path(recording_folder=recording_path, camera_id=camera_id)
    if csv_path is None:
        return None

    recording_to_connection: dict[int, int] = {}
    with csv_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            frame = int(row["recording_frame_number"])
            connection_frame = int(row["connection_frame_number"])
            if frame in recording_to_connection or frame < 0 or connection_frame < 0:
                raise ValueError(f"Invalid recording/connection frame association in {csv_path}")
            recording_to_connection[frame] = connection_frame
    return recording_to_connection


def _get_observation(
    *,
    frame_number: int,
    image,
    tracker: Tracker,
    state: TrackerState,
    cache: dict[int, Observation] | None,
) -> tuple[Observation, TrackerState]:
    """Get observation for a frame — from cache if available, else detect."""
    if cache is not None and frame_number in cache:
        observation = cache[frame_number]
        return observation, state

    return tracker.process_image(image, frame_number, state)
