"""
PosthocSkeletonTrackingNode: centralized multi-camera mocap tracking.

Replaces N per-camera VideoNode processes (one Tracker/session each) with a
single process holding ONE shared Tracker/session for all cameras, calling
skellytracker's Tracker.process_batch() once per frame across every camera.
This avoids redundant per-camera model downloads/GPU probes (mediapipe) and
the known same-process-only ONNX-session-build race (rtmpose), by building
the tracker/session exactly once instead of once per camera.

Mocap-only (mediapipe/rtmpose) — charuco calibration tracking still uses the
per-camera VideoNode path (see video_node.py), since charuco's CpuSession
backend gets no batching benefit from process_batch().
"""
import logging
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from multiprocessing.sharedctypes import Synchronized
from pathlib import Path

import cv2
from tqdm import tqdm
from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellytracker.core import TrackerConfig
from skellytracker.core.tracker.tracker import Tracker
from skellytracker.core.tracker.tracker_state import TrackerState

from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.abcs.source_node_abc import SourceNode
from freemocap.core.pipeline.realtime.camera_node_config import CameraNodeConfig
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.posthoc.pipeline_phases import VideoNodePhase, PosthocPipelineType
from freemocap.core.pipeline.posthoc.progress_messages import VideoNodeProgressMessage, PipelineProgressMessage
from freemocap.core.pipeline.posthoc.video_node import (
    VideoNode,
    _build_annotator,
    _is_mediapipe_config,
)
from freemocap.core.types.type_overloads import TopicPublicationQueue, PipelineIdString, \
    TopicSubscriptionQueue
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import VideoNodeOutputTopic, VideoNodeOutputMessage

logger = logging.getLogger(__name__)


def _annotate_and_write_one(
    *,
    camera_id: CameraIdString,
    observation: object,
    raw_image,
    annotators: dict,
    video_writers: dict,
    base_readers: dict,
) -> tuple[CameraIdString, bool]:
    """Annotate + encode one camera's frame. Returns (camera_id, base_reader_exhausted)
    so the caller can mutate base_readers from the main thread instead of here.
    """
    if camera_id not in annotators or camera_id not in video_writers:
        return camera_id, False

    base_reader_exhausted = False
    base_reader = base_readers.get(camera_id)
    if base_reader is not None:
        base_ok, base_frame = base_reader.read()
        if not base_ok or base_frame is None:
            base_reader_exhausted = True
            annotation_base = raw_image
        else:
            annotation_base = base_frame
    else:
        annotation_base = raw_image

    annotated_frame = annotators[camera_id].annotate(annotation_base, observation)
    video_writers[camera_id].write(annotated_frame)
    return camera_id, base_reader_exhausted


@dataclass
class PosthocSkeletonTrackingNode(SourceNode):
    camera_ids: list[CameraIdString]
    progress_subscription: TopicSubscriptionQueue

    @classmethod
    def create(
        cls,
        *,
        camera_video_paths: dict[CameraIdString, Path],
        detector_config: TrackerConfig,
        camera_node_config: CameraNodeConfig,
        worker_registry: WorkerRegistry,
        ipc: PipelineIPC,
        pubsub: PubSubTopicManager,
        recording_path: Path,
        pipeline_type: PosthocPipelineType,
        save_annotated_video: bool = True,
        pipeline_id: PipelineIdString | None = None,
    ) -> "PosthocSkeletonTrackingNode":
        _progress_queue: multiprocessing.queues.Queue = multiprocessing.Queue()
        shutdown_self_flag, worker = cls._create_worker(
            target=cls._run,
            name=f"PosthocSkeletonTrackingNode-{len(camera_video_paths)}cam",
            worker_registry=worker_registry,
            log_queue=ipc.ws_queue,
            kwargs=dict(
                camera_video_paths=camera_video_paths,
                detector_config=detector_config,
                camera_node_config=camera_node_config,
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
            camera_ids=list(camera_video_paths.keys()),
            shutdown_self_flag=shutdown_self_flag,
            worker=worker,
            progress_subscription=_progress_queue,
        )

    @staticmethod
    def _run(
        *,
        camera_video_paths: dict[CameraIdString, Path],
        detector_config: TrackerConfig,
        camera_node_config: CameraNodeConfig,
        ipc: PipelineIPC,
        video_output_pub: TopicPublicationQueue,
        video_progress_pub: TopicPublicationQueue,
        shutdown_self_flag: Synchronized,
        recording_path: Path,
        save_annotated_video: bool,
        pipeline_id: PipelineIdString,
        pipeline_type: PosthocPipelineType,
    ) -> None:
        from freemocap.core.pipeline.realtime.realtime_skeleton_inference_node import (
            _build_session_and_tracker,
        )
        from freemocap.core.pipeline.realtime.realtime_skeleton_inference_node_config import (
            RealtimeSkeletonInferenceNodeConfig,
        )
        from freemocap.core.tracking.tracker_factory import merge_mediapipe_hand_face_children

        camera_ids = list(camera_video_paths.keys())
        is_mediapipe = _is_mediapipe_config(detector_config)

        def _progress_for_all(**kwargs) -> None:
            for camera_id in camera_ids:
                video_progress_pub.put(VideoNodeProgressMessage(
                    camera_id=camera_id,
                    pipeline_id=f"{pipeline_id}:{camera_id}",
                    pipeline_type=str(pipeline_type),
                    recording_name=recording_path.name,
                    recording_path=str(recording_path),
                    **kwargs,
                ))

        _progress_for_all(phase=VideoNodePhase.SETTING_UP, progress_fraction=0.0, detail="Loading tracker...")
        tracker, session = _build_session_and_tracker(
            camera_node_config=camera_node_config,
            inf_config=RealtimeSkeletonInferenceNodeConfig(max_batch_size=len(camera_ids)),
            num_cameras=len(camera_ids),
        )
        if tracker is None:
            raise RuntimeError(
                "PosthocSkeletonTrackingNode: failed to build batched tracker/session"
            )
        tracker_states: dict[CameraIdString, TrackerState] = {}

        video_readers: dict[CameraIdString, cv2.VideoCapture] = {}
        for camera_id, video_path in camera_video_paths.items():
            reader = cv2.VideoCapture(str(video_path), cv2.CAP_FFMPEG)
            if not reader.isOpened():
                raise RuntimeError(f"Failed to open video file: {video_path}")
            video_readers[camera_id] = reader

        frame_counts = {
            camera_id: int(reader.get(cv2.CAP_PROP_FRAME_COUNT))
            for camera_id, reader in video_readers.items()
        }
        frame_count = min(frame_counts.values())
        if len(set(frame_counts.values())) > 1:
            logger.warning(
                f"PosthocSkeletonTrackingNode: cameras have mismatched frame counts "
                f"{frame_counts} — processing to the shortest ({frame_count} frames)"
            )
        _progress_for_all(
            phase=VideoNodePhase.SETTING_UP, progress_fraction=0.0,
            detail=f"Preparing {frame_count} frames across {len(camera_ids)} cameras",
        )

        annotators: dict[CameraIdString, object] = {}
        video_writers: dict[CameraIdString, cv2.VideoWriter] = {}
        base_readers: dict[CameraIdString, cv2.VideoCapture] = {}
        prev_annotated_paths: dict[CameraIdString, Path] = {}

        frame_number = 0
        _error_occurred = False
        executor = ThreadPoolExecutor(max_workers=len(camera_ids))
        try:
            if save_annotated_video:
                for camera_id, video_path in camera_video_paths.items():
                    annotators[camera_id] = _build_annotator(detector_config)
                    annotated_output_path, prev_annotated_path = VideoNode._resolve_annotated_video_paths(
                        recording_path=recording_path,
                        video_path=video_path,
                    )
                    if prev_annotated_path is not None:
                        prev_annotated_paths[camera_id] = prev_annotated_path
                        base_reader = cv2.VideoCapture(str(prev_annotated_path), cv2.CAP_FFMPEG)
                        if base_reader.isOpened():
                            base_readers[camera_id] = base_reader
                        else:
                            logger.warning(
                                f"Failed to open previous annotated video for {video_path.stem} — "
                                f"will annotate from source frames instead"
                            )

                    reader = video_readers[camera_id]
                    fps = reader.get(cv2.CAP_PROP_FPS)
                    width = int(reader.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(reader.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    writer = None
                    for fourcc in ("avc1", "mp4v", "MJPG"):
                        writer = cv2.VideoWriter(
                            str(annotated_output_path), cv2.VideoWriter.fourcc(*fourcc), fps, (width, height)
                        )
                        if writer.isOpened():
                            if fourcc != "avc1":
                                logger.warning(
                                    f"H.264 ('avc1') encoder unavailable for {video_path.stem} — "
                                    f"using '{fourcc}' instead"
                                )
                            break
                        writer.release()
                    if not writer.isOpened():
                        raise RuntimeError(f"Failed to create video writer for: {annotated_output_path}")
                    video_writers[camera_id] = writer

            logger.info(
                f"PosthocSkeletonTrackingNode started for {len(camera_ids)} cameras"
                f"{' (with annotation)' if save_annotated_video else ''}"
            )
            with tqdm(
                total=frame_count,
                desc="skeleton_tracking",
                unit="frame",
                leave=True,
                dynamic_ncols=True,
            ) as pbar:
                while frame_number < frame_count and not shutdown_self_flag.value and ipc.should_continue:
                    read_results = list(executor.map(
                        lambda camera_id: (camera_id, *video_readers[camera_id].read()),
                        camera_ids,
                    ))
                    images = {
                        camera_id: image
                        for camera_id, success, image in read_results
                        if success
                    }
                    if len(images) < len(camera_ids):
                        logger.warning(
                            f"PosthocSkeletonTrackingNode: at least one camera ran out of frames "
                            f"at frame {frame_number} — stopping"
                        )
                        break

                    observations, tracker_states = tracker.process_batch(
                        images, frame_number, tracker_states,
                    )

                    for camera_id in camera_ids:
                        observation = observations[camera_id]
                        if is_mediapipe:
                            merge_mediapipe_hand_face_children(observation)

                        video_output_pub.put(
                            VideoNodeOutputMessage(
                                camera_id=camera_id,
                                frame_number=frame_number,
                                observation=observation,
                            ),
                        )

                    # Annotation drawing + video encoding is CPU-heavy (previously
                    # ran in parallel across N OS processes); dispatch it across
                    # the same thread pool used for frame reads so it doesn't
                    # serialize across cameras now that we're in one process.
                    # Each camera's VideoWriter/Annotator/base_reader is a
                    # separate object, so concurrent per-camera calls are safe;
                    # base_readers mutation (dict del on exhaustion) is deferred
                    # to the main thread via the returned flag.
                    if annotators:
                        annotate_results = list(executor.map(
                            lambda camera_id: _annotate_and_write_one(
                                camera_id=camera_id,
                                observation=observations[camera_id],
                                raw_image=images[camera_id],
                                annotators=annotators,
                                video_writers=video_writers,
                                base_readers=base_readers,
                            ),
                            camera_ids,
                        ))
                        for camera_id, base_reader_exhausted in annotate_results:
                            if base_reader_exhausted:
                                logger.warning(
                                    f"Previous annotated video ran out of frames at frame "
                                    f"{frame_number} for camera {camera_id} — falling back to source frames"
                                )
                                base_readers[camera_id].release()
                                del base_readers[camera_id]

                    frame_number += 1
                    _progress_for_all(
                        phase=VideoNodePhase.PROCESSING_IMAGES,
                        progress_fraction=frame_number / frame_count,
                        detail=f"{frame_number}/{frame_count} frames",
                    )
                    pbar.update(1)

            logger.info(
                f"PosthocSkeletonTrackingNode finished reading {frame_number} frames "
                f"for {len(camera_ids)} cameras"
            )

        except Exception as e:
            logger.exception(f"Exception in PosthocSkeletonTrackingNode: {e}")
            _error_occurred = True
            _progress_for_all(
                phase=VideoNodePhase.FAILED,
                progress_fraction=frame_number / frame_count if frame_count > 0 else 0.0,
                detail=f"{type(e).__name__}: {e}",
            )
            ipc.shutdown_pipeline()
        finally:
            executor.shutdown(wait=False)
            tracker.close()
            for reader in video_readers.values():
                reader.release()
            if not _error_occurred:
                _progress_for_all(phase=VideoNodePhase.COMPLETE, progress_fraction=1.0, detail="")
            for writer in video_writers.values():
                writer.release()
            for base_reader in base_readers.values():
                base_reader.release()
            for prev_annotated_path in prev_annotated_paths.values():
                if prev_annotated_path.exists():
                    prev_annotated_path.unlink()
            # Cancel queue feeder threads so this process can exit promptly
            # instead of blocking forever on a full pipe buffer if the
            # consumer isn't draining as fast as we published (mirrors the
            # log_queue fix in skellycam's managed_worker.py
            # _process_entry_point). Must happen last, after all puts above.
            for pub_queue in (video_output_pub, video_progress_pub):
                try:
                    pub_queue.cancel_join_thread()
                except Exception:
                    pass
            logger.debug("PosthocSkeletonTrackingNode exiting")

    def get_progress_messages(self) -> list[PipelineProgressMessage]:
        from queue import Empty
        messages: list[VideoNodeProgressMessage] = []
        while True:
            try:
                messages.append(self.progress_subscription.get_nowait())
            except Empty:
                break
        return messages
