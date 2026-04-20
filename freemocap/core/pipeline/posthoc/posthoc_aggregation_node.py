"""
PosthocAggregationNode: collects all video node outputs, then calls a task function.

The frame-collection logic is written once here. The actual processing is
delegated to a task function (e.g. run_calibration_task, run_mocap_task)
passed in as a picklable callable.

The task function signature must be:

    def my_task(
        *,
        frame_observations: list[dict[VideoIdString, BaseObservation]],
        recording_info: RecordingInfo,
        video_metadata: dict[VideoIdString, VideoMetadata],
        report_progress: Callable[[str, float], None],
    ) -> None:

Additional task-specific kwargs are pre-bound via functools.partial.
"""
import logging
import multiprocessing
from collections.abc import Callable
from dataclasses import dataclass
from multiprocessing.sharedctypes import Synchronized

from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import TopicSubscriptionQueue

from freemocap.core.pipeline.abcs.aggregator_node_abc import AggregatorNode
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.posthoc.video_group_helper import VideoMetadata
from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt, VideoIdString, TopicPublicationQueue
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.pubsub.pubsub_topics import (
    VideoNodeOutputMessage,
    VideoNodeOutputTopic,
    AggregatorNodeProgressTopic,
    AggregatorNodeProgressMessage, PipelineProgressMessage,
)
from freemocap.utilities.wait_functions import wait_1ms

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
            video_metadata: dict[VideoIdString, VideoMetadata],
            pipeline_id: PipelineIdString,
            recording_info: RecordingInfo,
            worker_registry: WorkerRegistry,
            ipc: PipelineIPC,
            pubsub: PubSubTopicManager,
    ) -> "PosthocAggregationNode":
        shutdown_self_flag, worker = cls._create_worker(
            target=cls._run,
            name=f"Pipeline-{pipeline_id}-PosthocAggregationNode",
            worker_registry=worker_registry,
            log_queue=ipc.ws_queue,
            kwargs=dict(
                aggregation_task_fn=aggregation_task_fn,
                pipeline_id=pipeline_id,
                recording_info=recording_info,
                video_metadata=video_metadata,
                ipc=ipc,
                aggregator_progress_pub=pubsub.get_publication_queue(
                    AggregatorNodeProgressTopic
                ),
                video_node_output_subscription=pubsub.get_subscription(
                    VideoNodeOutputTopic,
                ),
            ),

        )
        return cls(
            shutdown_self_flag=shutdown_self_flag,
            progress_subscription=pubsub.get_subscription(
                AggregatorNodeProgressTopic,),
            worker=worker,
        )

    @staticmethod
    def _run(
            *,
            aggregation_task_fn: PosthocAggregationNodeTaskFn,
            pipeline_id: PipelineIdString,
            recording_info: RecordingInfo,
            video_metadata: dict[VideoIdString, VideoMetadata],
            ipc: PipelineIPC,
            shutdown_self_flag: Synchronized,
            video_node_output_subscription: TopicSubscriptionQueue,
            aggregator_progress_pub: TopicPublicationQueue,
    ) -> None:

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
        video_ids = list(video_metadata.keys())
        total_expected = len(frame_numbers) * len(video_ids)

        progress_message = AggregatorNodeProgressMessage(pipeline_id=pipeline_id,
                                                         frame_count=total_expected)
        aggregator_progress_pub.put(progress_message)
        logger.debug(
            f"PosthocAggregationNode [{pipeline_id}] starting — "
            f"expecting {len(frame_numbers)} frames × {len(video_ids)} videos "
            f"= {total_expected} outputs"
        )

        video_outputs_by_frame: dict[FrameNumberInt, dict[VideoIdString, VideoNodeOutputMessage | None]] = {
            frame_number: {vid: None for vid in video_ids}
            for frame_number in frame_numbers
        }
        got_all_by_frame: dict[FrameNumberInt, bool] = {frame_number: False for frame_number in frame_numbers}
        received_count: int = 0

        try:
            while not shutdown_self_flag.value and ipc.should_continue:
                wait_1ms()

                if video_node_output_subscription.empty():
                    continue

                msg: VideoNodeOutputMessage = video_node_output_subscription.get()

                if msg.video_id not in video_ids:
                    raise ValueError(
                        f"Unexpected video ID '{msg.video_id}' — "
                        f"expected one of {video_ids}"
                    )
                if msg.frame_number not in video_outputs_by_frame:
                    raise ValueError(
                        f"Unexpected frame number {msg.frame_number} — "
                        f"expected range [{start_frame}, {end_frame})"
                    )

                video_outputs_by_frame[msg.frame_number][msg.video_id] = msg
                received_count += 1

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

            observations_by_frame: list[dict[VideoIdString, object]] = []
            for frame_number in frame_numbers:
                frame_data = video_outputs_by_frame[frame_number]
                observations = {}
                for vid_id, output_msg in frame_data.items():
                    if not isinstance(output_msg, VideoNodeOutputMessage):
                        raise RuntimeError(
                            f"Missing output for video {vid_id} frame {frame_number}"
                        )
                    observations[vid_id] = output_msg.observation
                observations_by_frame.append(observations)

            progress_message.running_aggregation_task = True
            aggregator_progress_pub.put(progress_message)

            aggregation_task_fn(
                frame_observations=observations_by_frame,
                recording_info=recording_info,
                video_metadata=video_metadata,

            )
            progress_message.running_aggregation_task = False
            aggregator_progress_pub.put(progress_message)

            logger.info(f"PosthocAggregationNode [{pipeline_id}] — task completed")

        except Exception as e:
            logger.error(
                f"Exception in PosthocAggregationNode [{pipeline_id}]: {e}",
                exc_info=True,
            )
            progress_message.error = True
            progress_message.error_message = f"{type(e).__name__}: {e}"
            progress_message.running_aggregation_task = False
            aggregator_progress_pub.put(progress_message)
            ipc.shutdown_pipeline()
            # Do NOT re-raise: an unhandled exception here kills the worker, and the WorkerRegistry
            # child monitor treats that as a fatal failure and shuts down the parent server.
            # The error has already been surfaced via the progress message (error=True, error_message=...)
            # so the frontend can display a meaningful message to the user.
        finally:
            progress_message.complete = True
            aggregator_progress_pub.put(progress_message)
            logger.debug(
                f"PosthocAggregationNode [{pipeline_id}] exiting"
            )

    def get_progress_messages(self) -> list[PipelineProgressMessage]:
        messages: list[AggregatorNodeProgressMessage] = []
        while not self.progress_subscription.empty():
            messages.append(self.progress_subscription.get())
        return messages
