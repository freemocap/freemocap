"""
PosthocAggregationNode: collects all video node outputs, then calls a task function.

The frame-collection logic is written once here. The actual processing is
delegated to a task function (e.g. run_calibration_task, run_mocap_task)
passed in as a picklable callable.

The task function signature must be:

    def my_task(
        *,
        frame_observations: list[dict[CameraIdString, BaseObservation]],
        recording_info: RecordingInfo,
        video_metadata: dict[CameraIdString, VideoMetadata],
        reporter: TaskProgressReporter | None = None,
    ) -> None:

Additional task-specific kwargs are pre-bound via functools.partial.
"""
import logging
import multiprocessing
from dataclasses import dataclass
from multiprocessing.sharedctypes import Synchronized
from pathlib import Path
from typing import Callable

from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString, TopicSubscriptionQueue

from freemocap.core.pipeline.abcs.aggregator_node_abc import AggregatorNode
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc.pipeline_phases import AggregatorPhase, PosthocPipelineType
from freemocap.core.pipeline.posthoc.task_progress_reporter import TaskProgressReporter
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt, TopicPublicationQueue
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.core.pipeline.posthoc.progress_messages import AggregatorNodeProgressMessage, PipelineProgressMessage
from freemocap.pubsub.pubsub_topics import (
    VideoNodeOutputMessage,
    VideoNodeOutputTopic,
)
from tqdm import tqdm

from queue import Empty

logger = logging.getLogger(__name__)

PosthocAggregationNodeTaskFn = Callable[..., None]


@dataclass
class PosthocAggregationNode(AggregatorNode):
    progress_subscription: TopicSubscriptionQueue

    @classmethod
    def create(
            cls,
            *,
            aggregation_task_fn: PosthocAggregationNodeTaskFn,
            video_metadata: dict[CameraIdString, VideoMetadata],
            pipeline_id: PipelineIdString,
            pipeline_type: PosthocPipelineType,
            recording_info: RecordingInfo,
            worker_registry: WorkerRegistry,
            ipc: PipelineIPC,
            pubsub: PubSubTopicManager,
    ) -> "PosthocAggregationNode":
        _progress_queue: multiprocessing.queues.Queue = multiprocessing.Queue()
        shutdown_self_flag, worker = cls._create_worker(
            target=cls._run,
            name=f"Pipeline-{pipeline_id}-PosthocAggregationNode",
            worker_registry=worker_registry,
            log_queue=ipc.ws_queue,
            kwargs=dict(
                aggregation_task_fn=aggregation_task_fn,
                pipeline_id=pipeline_id,
                pipeline_type=pipeline_type,
                recording_info=recording_info,
                video_metadata=video_metadata,
                ipc=ipc,
                aggregator_progress_pub=_progress_queue,
                video_node_output_subscription=pubsub.get_subscription(
                    VideoNodeOutputTopic,
                ),
            ),
        )
        return cls(
            shutdown_self_flag=shutdown_self_flag,
            progress_subscription=_progress_queue,
            worker=worker,
        )

    @staticmethod
    def _run(
            *,
            aggregation_task_fn: PosthocAggregationNodeTaskFn,
            pipeline_id: PipelineIdString,
            pipeline_type: PosthocPipelineType,
            recording_info: RecordingInfo,
            video_metadata: dict[CameraIdString, VideoMetadata],
            ipc: PipelineIPC,
            shutdown_self_flag: Synchronized,
            video_node_output_subscription: TopicSubscriptionQueue,
            aggregator_progress_pub: TopicPublicationQueue,
    ) -> None:

        rec_path = Path(recording_info.full_recording_path)
        rec_name = rec_path.name
        rec_path_str = str(rec_path)

        start_frames = set(vm.start_frame for vm in video_metadata.values())
        end_frames = set(vm.end_frame for vm in video_metadata.values())
        if len(start_frames) != 1 or len(end_frames) != 1:
            raise ValueError(
                f"Mismatched start/end frames across videos in pipeline {pipeline_id}: "
                f"start_frames={start_frames}, end_frames={end_frames}"
            )
        start_frame = start_frames.pop()
        end_frame = end_frames.pop()
        frame_numbers = list(range(start_frame, end_frame))
        camera_ids = list(video_metadata.keys())
        total_expected = len(frame_numbers) * len(camera_ids)

        aggregator_progress_pub.put(AggregatorNodeProgressMessage(
            pipeline_id=pipeline_id,
            pipeline_type=str(pipeline_type),
            phase=AggregatorPhase.COLLECTING_CAMERA_OUTPUT,
            progress_fraction=0.0,
            detail=f"Collecting observations from {len(camera_ids)} cameras ({total_expected} total)",
            recording_name=rec_name,
            recording_path=rec_path_str,
        ))
        logger.debug(
            f"PosthocAggregationNode [{pipeline_id}] starting — "
            f"expecting {len(frame_numbers)} frames × {len(camera_ids)} cameras "
            f"= {total_expected} outputs"
        )

        video_outputs_by_frame: dict[FrameNumberInt, dict[CameraIdString, VideoNodeOutputMessage | None]] = {
            frame_number: {cam: None for cam in camera_ids}
            for frame_number in frame_numbers
        }
        got_all_by_frame: dict[FrameNumberInt, bool] = {frame_number: False for frame_number in frame_numbers}
        received_count: int = 0

        _error_occurred = True  # pessimistic; cleared to False only on clean completion
        try:
            with tqdm(
                total=total_expected,
                desc=f"[{pipeline_id}] collecting",
                unit="obs",
                leave=True,
                dynamic_ncols=True,
            ) as pbar:
                while not shutdown_self_flag.value and ipc.should_continue:
                    try:
                        msg: VideoNodeOutputMessage = video_node_output_subscription.get(timeout=0.001)
                    except Empty:
                        continue

                    if msg.camera_id not in camera_ids:
                        raise ValueError(
                            f"Unexpected camera ID '{msg.camera_id}' — "
                            f"expected one of {camera_ids}"
                        )
                    if msg.frame_number not in video_outputs_by_frame:
                        raise ValueError(
                            f"Unexpected frame number {msg.frame_number} — "
                            f"expected range [{start_frame}, {end_frame})"
                        )

                    video_outputs_by_frame[msg.frame_number][msg.camera_id] = msg
                    received_count += 1
                    pbar.update(1)

                    update_interval = max(1, total_expected // 50)
                    if received_count % update_interval == 0:
                        aggregator_progress_pub.put(AggregatorNodeProgressMessage(
                            pipeline_id=pipeline_id,
                            pipeline_type=str(pipeline_type),
                            phase=AggregatorPhase.COLLECTING_CAMERA_OUTPUT,
                            progress_fraction=received_count / total_expected,
                            detail=f"Collecting observations {received_count}/{total_expected}",
                            recording_name=rec_name,
                            recording_path=rec_path_str,
                        ))

                    if all(
                            isinstance(v, VideoNodeOutputMessage)
                            for v in video_outputs_by_frame[msg.frame_number].values()
                    ):
                        got_all_by_frame[msg.frame_number] = True

                    if all(got_all_by_frame.values()):
                        break

            missing_frames = [frame_number for frame_number, complete in got_all_by_frame.items() if not complete]
            if missing_frames:
                raise RuntimeError(
                    f"Pipeline {pipeline_id} ended with {len(missing_frames)} missing frames out of {total_expected}, "
                    f"incomplete frames (shutdown_flag={shutdown_self_flag.value}, "
                    f"should_continue={ipc.should_continue})"
                )

            logger.info(f"PosthocAggregationNode [{pipeline_id}] — all frames collected")

            observations_by_frame: list[dict[CameraIdString, object]] = []
            for frame_number in frame_numbers:
                frame_data = video_outputs_by_frame[frame_number]
                observations = {}
                for cam_id, output_msg in frame_data.items():
                    if not isinstance(output_msg, VideoNodeOutputMessage):
                        raise RuntimeError(
                            f"Missing output for camera {cam_id} frame {frame_number}"
                        )
                    observations[cam_id] = output_msg.observation
                observations_by_frame.append(observations)

            reporter = TaskProgressReporter(
                callback=lambda stage, detail, fraction: aggregator_progress_pub.put(
                    AggregatorNodeProgressMessage(
                        pipeline_id=pipeline_id,
                        pipeline_type=str(pipeline_type),
                        phase=stage,
                        progress_fraction=fraction,
                        detail=detail,
                        recording_name=rec_name,
                        recording_path=rec_path_str,
                    )
                )
            )

            aggregation_task_fn(
                frame_observations=observations_by_frame,
                recording_info=recording_info,
                video_metadata=video_metadata,
                reporter=reporter,
            )

            logger.info(f"PosthocAggregationNode [{pipeline_id}] — task completed")
            _error_occurred = False

        except Exception as e:
            logger.error(
                f"Exception in PosthocAggregationNode [{pipeline_id}]: {e}",
                exc_info=True,
            )
            _error_occurred = True
            aggregator_progress_pub.put(AggregatorNodeProgressMessage(
                pipeline_id=pipeline_id,
                pipeline_type=str(pipeline_type),
                phase=AggregatorPhase.FAILED,
                progress_fraction=0.0,
                detail=f"{type(e).__name__}: {e}",
                recording_name=rec_name,
                recording_path=rec_path_str,
            ))
            ipc.shutdown_pipeline()
            # Do NOT re-raise: an unhandled exception here kills the worker, and the WorkerRegistry
            # child monitor treats that as a fatal failure and shuts down the parent server.
            # The error has already been surfaced via the progress message so the frontend can
            # display a meaningful message to the user.
        finally:
            if not _error_occurred:
                aggregator_progress_pub.put(AggregatorNodeProgressMessage(
                    pipeline_id=pipeline_id,
                    pipeline_type=str(pipeline_type),
                    phase=AggregatorPhase.COMPLETE,
                    progress_fraction=1.0,
                    recording_name=rec_name,
                    recording_path=rec_path_str,
                ))
            logger.debug(
                f"PosthocAggregationNode [{pipeline_id}] exiting"
            )

    def get_progress_messages(self) -> list[PipelineProgressMessage]:
        from queue import Empty
        messages: list[AggregatorNodeProgressMessage] = []
        while True:
            try:
                messages.append(self.progress_subscription.get_nowait())
            except Empty:
                break
        return messages
