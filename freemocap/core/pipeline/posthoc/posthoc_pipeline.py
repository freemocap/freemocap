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
from dataclasses import dataclass, field
from pathlib import Path
from multiprocessing.sharedctypes import Synchronized

from skellycam.core.ipc.process_management.worker_registry import WorkerRegistry
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellytracker.trackers.base_tracker.base_tracker_abcs import BaseDetectorConfig

from freemocap.core.pipeline.abcs.pipeline_abc import PipelineABC
from freemocap.core.pipeline.abcs.pipeline_ipc import PipelineIPC
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.posthoc.pipeline_phases import PosthocPipelineType
from freemocap.core.pipeline.posthoc.posthoc_aggregation_node import PosthocAggregationNode, \
    PosthocAggregationNodeTaskFn
from freemocap.core.pipeline.posthoc.video_group_helper import VideoGroupHelper
from freemocap.core.pipeline.posthoc.video_node import VideoNode
from freemocap.core.types.type_overloads import PipelineIdString
from freemocap.pubsub.pubsub_manager import PubSubTopicManager
from freemocap.core.pipeline.posthoc.progress_messages import PipelineProgressMessage

logger = logging.getLogger(__name__)


@dataclass
class PosthocPipeline(PipelineABC):
    """
    Generic posthoc pipeline: video nodes → aggregation node → task function.

    Self-terminates when processing is complete. Check .alive to see if it's
    still running, or subscribe to PosthocProgressTopic for status updates.
    """
    id: PipelineIdString
    pipeline_type: PosthocPipelineType
    recording_info: RecordingInfo
    video_nodes: dict[CameraIdString, VideoNode]
    aggregation_node: PosthocAggregationNode
    ipc: PipelineIPC
    pubsub: PubSubTopicManager
    started: bool = False
    queued_progress_message: PipelineProgressMessage | None = None
    # Retained latest progress message per node id (keyed by pipeline_id, e.g.
    # "<base>" for the aggregator and "<base>:<camera>" for each video node).
    # Progress is delivered as RETAINED STATE — the full snapshot is re-sent on
    # every poll — rather than as one-shot consumable events. This makes the UI
    # level-triggered: a single dropped/stolen progress message can no longer
    # leave a bar stuck, because each node's latest (incl. terminal COMPLETE/
    # FAILED) state keeps being re-asserted until the pipeline is evicted. The
    # frontend dedupes identical (phase, progress) per id, so repeats are free.
    _latest_progress_by_id: dict[str, PipelineProgressMessage] = field(default_factory=dict)

    @property
    def alive(self) -> bool:
        """True if any worker process is still running."""
        if not self.started:
            return False
        any_alive = any(node.is_alive for node in self.video_nodes.values())
        return any_alive or self.aggregation_node.is_alive

    @property
    def camera_ids(self) -> list[CameraIdString]:
        return list(self.video_nodes.keys())

    @classmethod
    def create(
        cls,
        *,
        recording_info: RecordingInfo,
        detector_config: BaseDetectorConfig,
        aggregation_task_fn: PosthocAggregationNodeTaskFn,
        pipeline_type: PosthocPipelineType,
        worker_registry: WorkerRegistry,
        global_kill_flag: Synchronized,
        save_annotated_video: bool = True,
    ) -> "PosthocPipeline":
        """
        Create a posthoc pipeline.

        Args:
            recording_info: Where to find the recorded videos.
            detector_config: Which detector to run on each video frame.
            aggregation_task_fn: The processing function (with task_config pre-bound via
                     functools.partial) to call after all frames are collected.
            worker_registry: For creating managed processes.
            global_kill_flag: Shared app-wide kill flag.
            save_annotated_video: Write annotated video output during detection.
                If an annotated video already exists, new annotations are layered
                on top of the existing one.
        """
        recording_path = Path(recording_info.full_recording_path)

        video_group = VideoGroupHelper.from_recording_path(
            recording_path=str(recording_path),
        )

        pipeline_id: PipelineIdString = str(uuid.uuid4())[:6]

        ipc = PipelineIPC.create(
            global_kill_flag=global_kill_flag,
            heartbeat_timestamp=worker_registry.heartbeat_timestamp,
            pipeline_id=pipeline_id,
        )
        pubsub = PubSubTopicManager.create(
            global_kill_flag=global_kill_flag,
        )

        video_nodes: dict[CameraIdString, VideoNode] = {}
        for camera_id, video_helper in video_group.videos.items():
            video_nodes[camera_id] = VideoNode.create(
                camera_id=camera_id,
                video_path=video_helper.video_path,
                detector_config=detector_config,
                worker_registry=worker_registry,
                ipc=ipc,
                pubsub=pubsub,
                recording_path=recording_path,
                save_annotated_video=save_annotated_video,
                pipeline_id=pipeline_id,
                pipeline_type=pipeline_type,
            )

        aggregation_node = PosthocAggregationNode.create(
            aggregation_task_fn=aggregation_task_fn,
            video_metadata=video_group.video_metadata_by_id,
            pipeline_id=pipeline_id,
            pipeline_type=pipeline_type,
            recording_info=recording_info,
            worker_registry=worker_registry,
            ipc=ipc,
            pubsub=pubsub,
        )

        video_group.close()

        return cls(
            id=pipeline_id,
            pipeline_type=pipeline_type,
            recording_info=recording_info,
            video_nodes=video_nodes,
            aggregation_node=aggregation_node,
            ipc=ipc,
            pubsub=pubsub,
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

        nodes = list(self.video_nodes.values())
        for i, node in enumerate(nodes):
            node.start()


        self.aggregation_node.start()
        logger.info(f"PosthocPipeline [{self.id}] — all workers started")

    def shutdown(self) -> None:
        """Force-shutdown the pipeline (for cleanup or cancellation)."""
        logger.debug(f"Shutting down PosthocPipeline [{self.id}]")
        self.ipc.shutdown_pipeline()
        self.pubsub.close()
        for node in self.video_nodes.values():
            if node.is_alive:
                node.shutdown()
        if self.aggregation_node.is_alive:
            self.aggregation_node.shutdown()
        logger.debug(f"PosthocPipeline [{self.id}] shut down")

    def get_progress_messages(self) -> list[PipelineProgressMessage]:
        # Drain any newly-emitted messages from the node queues, fold them into
        # the retained per-id snapshot, then return the FULL snapshot. Returning
        # the snapshot (rather than only the freshly-drained messages) is what
        # makes completion self-healing: if a terminal message was ever missed
        # downstream, it keeps being re-sent on subsequent polls until eviction.
        fresh: list[PipelineProgressMessage] = []
        if self.queued_progress_message is not None:
            fresh.append(self.queued_progress_message)
            self.queued_progress_message = None
        for node in list(self.video_nodes.values()):
            fresh.extend(node.get_progress_messages())
        fresh.extend(self.aggregation_node.get_progress_messages())

        for message in fresh:
            self._latest_progress_by_id[message.pipeline_id] = message

        return list(self._latest_progress_by_id.values())

    def drain_and_get_messages(self) -> list[PipelineProgressMessage]:
        """Flush the relay (pub→sub) then drain all subscription queues.

        Call this instead of get_progress_messages() when the pipeline workers
        have already exited — the relay may not have had a chance to move
        the terminal COMPLETE/FAILED message from the publication queue to
        the subscription queue yet.
        """
        self.pubsub.drain()
        return self.get_progress_messages()
