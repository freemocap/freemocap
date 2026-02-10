"""
PosthocAggregationNode: collects all video node outputs, then calls a task function.

This replaces both PosthocCalibrationAggregationNode and PosthocMocapAggregationNode.
The frame-collection logic (which was duplicated line-for-line) is written once here.
The actual processing is delegated to a task function (e.g. run_calibration_task,
run_mocap_task) that is passed in as a picklable callable.

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

from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import TopicSubscriptionQueue

from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.nodes import BaseNode
from freemocap.core.pipeline.video_helper import VideoMetadata
from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt, VideoIdString
from freemocap.pubsub.pubsub_topics import (
    VideoNodeOutputMessage,
    VideoNodeOutputTopic,
    PosthocProgressTopic,
    PosthocProgressMessage,
)
from freemocap.utilities.wait_functions import wait_1ms
from skellycam.core.ipc.process_management.process_registry import ProcessRegistry

logger = logging.getLogger(__name__)

# Type alias for task functions. Concrete tasks may have additional kwargs
# pre-bound via functools.partial — the aggregation node doesn't need to know.
PosthocTaskFn = Callable[..., None]


@dataclass
class PosthocAggregationNode(BaseNode):

    @classmethod
    def create(
        cls,
        *,
        task_fn: PosthocTaskFn,
        video_metadata: dict[VideoIdString, VideoMetadata],
        pipeline_id: PipelineIdString,
        recording_info: RecordingInfo,
        process_registry: ProcessRegistry,
        ipc: PipelineIPC,
    ) -> "PosthocAggregationNode":
        shutdown_self_flag = multiprocessing.Value('b', False)
        worker = process_registry.create_process(
            target=cls._run,
            name=f"Pipeline-{pipeline_id}-PosthocAggregationNode",
            kwargs=dict(
                task_fn=task_fn,
                pipeline_id=pipeline_id,
                recording_info=recording_info,
                video_metadata=video_metadata,
                ipc=ipc,
                shutdown_self_flag=shutdown_self_flag,
                video_node_subscription=ipc.pubsub.topics[
                    VideoNodeOutputTopic
                ].get_subscription(),
            ),
            log_queue=ipc.ws_queue,
        )
        return cls(
            shutdown_self_flag=shutdown_self_flag,
            worker=worker,
        )

    @staticmethod
    def _run(
        *,
        task_fn: PosthocTaskFn,
        pipeline_id: PipelineIdString,
        recording_info: RecordingInfo,
        video_metadata: dict[VideoIdString, VideoMetadata],
        ipc: PipelineIPC,
        shutdown_self_flag: multiprocessing.Value,
        video_node_subscription: TopicSubscriptionQueue,
    ) -> None:
        # ---- Validate frame ranges across videos ----
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

        logger.debug(
            f"PosthocAggregationNode [{pipeline_id}] starting — "
            f"expecting {len(frame_numbers)} frames × {len(video_ids)} videos "
            f"= {total_expected} outputs"
        )

        # ---- Helper to publish progress ----
        def _publish_progress(phase: str, fraction: float, detail: str = "") -> None:
            try:
                ipc.pubsub.publish(
                    topic_type=PosthocProgressTopic,
                    message=PosthocProgressMessage(
                        pipeline_id=pipeline_id,
                        phase=phase,
                        progress_fraction=max(0.0, min(1.0, fraction)),
                        detail=detail,
                    ),
                )
            except Exception:
                pass  # progress reporting is best-effort

        def _report_progress(detail: str, fraction: float) -> None:
            """Callback passed to the task function for task-phase progress."""
            _publish_progress(phase="processing", fraction=fraction, detail=detail)

        # ---- Phase 1: Collect all frame outputs ----
        _publish_progress("collecting_frames", 0.0, "Waiting for video node outputs")

        video_outputs_by_frame: dict[FrameNumberInt, dict[VideoIdString, VideoNodeOutputMessage | None]] = {
            fn: {vid: None for vid in video_ids}
            for fn in frame_numbers
        }
        got_all_by_frame: dict[FrameNumberInt, bool] = {fn: False for fn in frame_numbers}
        received_count: int = 0

        try:
            while not shutdown_self_flag.value and ipc.should_continue:
                wait_1ms()

                if video_node_subscription.empty():
                    continue

                msg: VideoNodeOutputMessage = video_node_subscription.get()

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

                # Check if this frame is complete
                if all(
                    isinstance(v, VideoNodeOutputMessage)
                    for v in video_outputs_by_frame[msg.frame_number].values()
                ):
                    got_all_by_frame[msg.frame_number] = True

                # Report collection progress
                if received_count % max(1, total_expected // 20) == 0:
                    _publish_progress(
                        "collecting_frames",
                        received_count / total_expected,
                        f"Collected {received_count}/{total_expected} observations",
                    )

                # Check if ALL frames are complete
                if all(got_all_by_frame.values()):
                    break

            # ---- Validate completeness ----
            missing_frames = [fn for fn, complete in got_all_by_frame.items() if not complete]
            if missing_frames:
                raise RuntimeError(
                    f"Pipeline {pipeline_id} ended with {len(missing_frames)} "
                    f"incomplete frames (shutdown_flag={shutdown_self_flag.value}, "
                    f"should_continue={ipc.should_continue})"
                )

            _publish_progress("collecting_frames", 1.0, "All frames collected")
            logger.info(f"PosthocAggregationNode [{pipeline_id}] — all frames collected")

            # ---- Phase 2: Build observation list and call task ----
            _publish_progress("processing", 0.0, "Starting task processing")

            frame_observations: list[dict[VideoIdString, object]] = []
            for fn in frame_numbers:
                frame_data = video_outputs_by_frame[fn]
                observations = {}
                for vid_id, output_msg in frame_data.items():
                    if not isinstance(output_msg, VideoNodeOutputMessage):
                        raise RuntimeError(
                            f"Missing output for video {vid_id} frame {fn}"
                        )
                    observations[vid_id] = output_msg.observation
                frame_observations.append(observations)

            task_fn(
                frame_observations=frame_observations,
                recording_info=recording_info,
                video_metadata=video_metadata,
                report_progress=_report_progress,
            )

            _publish_progress("complete", 1.0, "Task completed successfully")
            logger.info(f"PosthocAggregationNode [{pipeline_id}] — task completed")

        except Exception as e:
            logger.error(
                f"Exception in PosthocAggregationNode [{pipeline_id}]: {e}",
                exc_info=True,
            )
            _publish_progress("failed", 0.0, str(e))
            ipc.shutdown_pipeline()
            raise
        finally:
            logger.debug(
                f"PosthocAggregationNode [{pipeline_id}] exiting"
            )
