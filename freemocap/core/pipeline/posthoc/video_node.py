"""
VideoNode: reads frames from a video file, runs a tracker, publishes observations.

Generic video processing node parameterized by TrackerConfig — the same node
handles charuco detection, RTMPose skeleton detection, or any future tracker type.

Optionally saves annotated video output. If an existing annotated video is found
in the annotated_videos/ folder, new annotations are drawn on top of those frames
(allowing layering of e.g. charuco + skeleton annotations). Otherwise, annotations
are drawn on the source video frames.
"""
import csv
import logging
import multiprocessing
import pickle
from dataclasses import dataclass
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
from freemocap.system.default_paths import ANNOTATED_VIDEOS_FOLDER_NAME

logger = logging.getLogger(__name__)


def _is_charuco_config(tracker_config: TrackerConfig) -> bool:
    """Return True if this TrackerConfig is for charuco board detection."""
    for stage in tracker_config.stages:
        for kp_det in stage.keypoint_detectors:
            if isinstance(kp_det, CharucoDetectorConfig):
                return True
    return False


def _extract_board_def(tracker_config: TrackerConfig) -> CharucoBoardDefinition:
    for stage in tracker_config.stages:
        for kp_det in stage.keypoint_detectors:
            if isinstance(kp_det, CharucoDetectorConfig):
                return kp_det.board
    return CharucoBoardDefinition.create_letter_size_5x3()


def _build_tracker(tracker_config: TrackerConfig) -> tuple[Tracker, object]:
    """Build a (Tracker, session) pair from a TrackerConfig.

    For charuco configs, returns (Tracker, CpuSession).
    For skeleton configs, returns (Tracker, OnnxSession).
    """
    from freemocap.core.tracking.tracker_factory import (
        build_charuco_tracker,
        build_skeleton_onnx_session,
        build_skeleton_tracker,
    )
    from skellytracker.core.detectors.keypoint_detectors.rtmpose import RTMPoseDetectorConfig

    if _is_charuco_config(tracker_config):
        board_def = _extract_board_def(tracker_config)
        return build_charuco_tracker(board_def)

    model_name = "rtmw-x-l_256x192"
    for stage in tracker_config.stages:
        for kp_det in stage.keypoint_detectors:
            if isinstance(kp_det, RTMPoseDetectorConfig):
                model_name = kp_det.model_name
                break
    onnx_session = build_skeleton_onnx_session(batch_size=1, model_name=model_name)
    tracker = build_skeleton_tracker(onnx_session=onnx_session, model_name=model_name)
    return tracker, onnx_session


def _build_annotator(tracker_config: TrackerConfig):
    """Build an Annotator for the given TrackerConfig."""
    from skellytracker.core.annotation.keypoint_annotator import KeypointAnnotator, KeypointAnnotatorConfig
    from skellytracker.core.detectors.keypoint_detectors.charuco.charuco_observation_annotator import (
        CharucoObservationAnnotator,
        _CharucoObservationAnnotatorConfig,
    )

    if _is_charuco_config(tracker_config):
        board_def = _extract_board_def(tracker_config)
        return CharucoObservationAnnotator.create(
            _CharucoObservationAnnotatorConfig(board_def=board_def)
        )
    return KeypointAnnotator(config=KeypointAnnotatorConfig())


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
        annotated_dir = recording_path / ANNOTATED_VIDEOS_FOLDER_NAME
        annotated_dir.mkdir(parents=True, exist_ok=True)

        output_path = annotated_dir / f"{video_path.stem}_annotated{video_path.suffix}"

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
        detector_config: TrackerConfig,
        ipc: PipelineIPC,
        video_output_pub: TopicPublicationQueue,
        video_progress_pub: TopicPublicationQueue,
        shutdown_self_flag: Synchronized,
        recording_path: Path,
        save_annotated_video: bool,
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
        tracker, session = _build_tracker(detector_config)
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
        video_writer: cv2.VideoWriter | None = None
        base_reader: cv2.VideoCapture | None = None
        prev_annotated_path: Path | None = None

        frame_number: int = 0
        _error_occurred = False
        try:
            if save_annotated_video:
                annotator = _build_annotator(detector_config)
                annotated_output_path, prev_annotated_path = VideoNode._resolve_annotated_video_paths(
                    recording_path=recording_path,
                    video_path=video_path,
                )

                if prev_annotated_path is not None:
                    base_reader = cv2.VideoCapture(str(prev_annotated_path), cv2.CAP_FFMPEG)
                    if not base_reader.isOpened():
                        logger.warning(
                            f"Failed to open previous annotated video for {video_path.stem} — "
                            f"will annotate from source frames instead"
                        )
                        base_reader = None

                fps = video_reader.get(cv2.CAP_PROP_FPS)
                width = int(video_reader.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(video_reader.get(cv2.CAP_PROP_FRAME_HEIGHT))
                video_writer = cv2.VideoWriter(
                    str(annotated_output_path), cv2.VideoWriter_fourcc(*"avc1"), fps, (width, height)
                )
                if not video_writer.isOpened():
                    video_writer.release()
                    logger.warning(
                        f"H.264 ('avc1') encoder unavailable for {video_path.stem} — "
                        f"falling back to 'mp4v'"
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

                    if annotator is not None and video_writer is not None:
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

                        annotated_frame = annotator.annotate(annotation_base, observation)
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
            if video_writer is not None:
                video_writer.release()
            if base_reader is not None:
                base_reader.release()
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
            cache_by_recording_frame[recording_frame_number] = observation

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
    if not _is_charuco_config(detector_config):
        logger.debug(
            f"VideoNode [{camera_id}]: not a charuco config — realtime cache N/A"
        )
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

    request_board = _extract_board_def(detector_config)
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
    recording_info = RecordingInfo(
        recording_name=recording_path.name,
        recording_directory=str(recording_path.parent),
    )
    csv_path = Path(recording_info.camera_timestamps_file_path_from_camera_id(camera_id))
    if not csv_path.exists():
        logger.warning(
            f"VideoNode [{camera_id}]: timestamps CSV not found at {csv_path} — "
            f"cannot align realtime cache, falling back to full detection"
        )
        return None

    try:
        recording_to_connection: dict[int, int] = {}
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                recording_to_connection[int(row["recording_frame_number"])] = int(
                    row["connection_frame_number"]
                )
        return recording_to_connection
    except Exception:
        logger.warning(
            f"VideoNode [{camera_id}]: failed to parse timestamps CSV {csv_path} — "
            f"falling back to full detection",
            exc_info=True,
        )
        return None


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
