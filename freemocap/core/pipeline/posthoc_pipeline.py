"""
PosthocPipeline: a fire-and-forget pipeline that processes recorded video.

Replaces both PosthocCalibrationProcessingPipeline and PosthocMocapProcessingPipeline.
The pipeline is parameterized by:
  - detector_spec: what detector to run in the video nodes
  - task_fn: what processing to do in the aggregation node after collecting all frames

The pipeline self-terminates when processing is complete. All processes exit
naturally when their work is done.
"""
import logging
import multiprocessing
import uuid
from dataclasses import dataclass

from pydantic import BaseModel

from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.pipeline.pipeline_configs import DetectorSpec
from freemocap.core.pipeline.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.nodes.posthoc_aggregation_node import PosthocAggregationNode, PosthocTaskFn
from freemocap.core.pipeline.nodes.video_node import VideoNode
from freemocap.core.pipeline.video_helper import VideoGroupHelper
from freemocap.core.types.type_overloads import PipelineIdString, VideoIdString
from skellycam.core.ipc.process_management.process_registry import ProcessRegistry

logger = logging.getLogger(__name__)


@dataclass
class PosthocPipeline:
    """
    Generic posthoc pipeline: video nodes → aggregation node → task function.

    Self-terminates when processing is complete. Check .alive to see if it's
    still running, or subscribe to PosthocProgressTopic for status updates.
    """
    id: PipelineIdString
    recording_info: RecordingInfo
    video_nodes: dict[VideoIdString, VideoNode]
    aggregation_node: PosthocAggregationNode
    ipc: PipelineIPC
    started: bool = False

    @property
    def alive(self) -> bool:
        """True if any worker process is still running."""
        if not self.started:
            return False
        any_alive = any(node.is_alive for node in self.video_nodes.values())
        return any_alive or self.aggregation_node.is_alive

    @property
    def video_ids(self) -> list[VideoIdString]:
        return list(self.video_nodes.keys())

    @classmethod
    def create(
        cls,
        *,
        recording_info: RecordingInfo,
        detector_spec: DetectorSpec,
        task_fn: PosthocTaskFn,
        process_registry: ProcessRegistry,
        global_kill_flag: multiprocessing.Value,
    ) -> "PosthocPipeline":
        """
        Create a posthoc pipeline.

        Args:
            recording_info: Where to find the recorded videos.
            detector_spec: Which detector to run on each video frame.
            task_fn: The processing function (with task_config pre-bound via
                     functools.partial) to call after all frames are collected.
            process_registry: For creating managed processes.
            global_kill_flag: Shared app-wide kill flag.
        """
        # Validate videos exist and have matching frame counts
        video_group = VideoGroupHelper.from_recording_path(
            recording_path=recording_info.full_recording_path,
        )

        pipeline_id: PipelineIdString = str(uuid.uuid4())[:6]
        ipc = PipelineIPC.create(
            global_kill_flag=global_kill_flag,
            heartbeat_timestamp=process_registry.heartbeat_timestamp,
            pipeline_id=pipeline_id,
        )

        # Create video nodes
        video_nodes: dict[VideoIdString, VideoNode] = {}
        for video_id, video_helper in video_group.videos.items():
            video_nodes[video_id] = VideoNode.create(
                video_id=video_id,
                video_path=video_helper.video_path,
                detector_spec=detector_spec,
                process_registry=process_registry,
                ipc=ipc,
            )

        # Create aggregation node
        aggregation_node = PosthocAggregationNode.create(
            task_fn=task_fn,
            video_metadata=video_group.video_metadata_by_id,
            pipeline_id=pipeline_id,
            recording_info=recording_info,
            process_registry=process_registry,
            ipc=ipc,
        )

        # Close video group (videos are reopened inside node processes)
        video_group.close()

        return cls(
            id=pipeline_id,
            recording_info=recording_info,
            video_nodes=video_nodes,
            aggregation_node=aggregation_node,
            ipc=ipc,
        )

    def start(self) -> None:
        """Start all video nodes then the aggregation node."""
        if self.started:
            raise RuntimeError(f"PosthocPipeline {self.id} already started")
        self.started = True
        logger.info(
            f"Starting PosthocPipeline [{self.id}] for recording "
            f"'{self.recording_info.recording_name}' "
            f"with {len(self.video_nodes)} video node(s)"
        )

        for node in self.video_nodes.values():
            node.start()

        self.aggregation_node.start()
        logger.info(f"PosthocPipeline [{self.id}] — all workers started")

    def shutdown(self) -> None:
        """Force-shutdown the pipeline (for cleanup or cancellation)."""
        logger.debug(f"Shutting down PosthocPipeline [{self.id}]")
        self.ipc.shutdown_pipeline()
        for node in self.video_nodes.values():
            if node.is_alive:
                node.shutdown()
        if self.aggregation_node.is_alive:
            self.aggregation_node.shutdown()
        logger.debug(f"PosthocPipeline [{self.id}] shut down")
