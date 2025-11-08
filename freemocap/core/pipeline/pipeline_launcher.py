"""
Pipeline launcher that handles node orchestration and subscription pre-allocation.
All subscriptions are created in parent process before spawning workers.
"""
import logging
import multiprocessing
import uuid
from pydantic import BaseModel, ConfigDict

from skellycam.core.camera_group.camera_group import CameraGroup

from freemocap.core.pipeline.aggregation_node import AggregationNode
from freemocap.core.pipeline.base_node_abcs import ProcessNodeABC, PipelineType
from freemocap.core.pipeline.camera_node import CameraNode
from freemocap.core.pipeline.og.pipeline_ipc import PipelineIPC
from freemocap.core.pipeline.pipeline_launch_configs import (
    CameraNodeParams,
    AggregationNodeParams, PipelineLaunchConfigABC,
)
from skellycam.core.ipc.pubsub.pubsub_manager import TopicTypes

from freemocap.core.types.type_overloads import PipelineIdString, TopicSubscriptionQueue
from freemocap.pubsub.pubsub_abcs import PubSubTopicABC
from freemocap.pubsub.pubsub_manager import PubSubTopicManager

logger = logging.getLogger(__name__)


class PipelineInstance(BaseModel):
    """
    Lightweight container for a running pipeline.
    Does not manage processes directly - that's the launcher's job.
    """
    pipeline_id: PipelineIdString
    config: PipelineLaunchConfigABC
    nodes: dict[str, ProcessNodeABC]
    pubsub: PubSubTopicManager
    ipc: PipelineIPC
    
    @property
    def is_alive(self) -> bool:
        """Check if all nodes are alive."""
        return all(node.is_alive for node in self.nodes.values())
    
    def shutdown(self) -> None:
        """Shutdown all nodes in proper order."""
        # Shutdown nodes in reverse order of creation
        for node_id in reversed(list(self.nodes.keys())):
            self.nodes[node_id].shutdown()
        
        # Close IPC resources
        self.ipc.shutdown_pipeline()


class PipelineLauncher(BaseModel):
    """
    Handles pipeline orchestration and lifecycle management.
    
    Responsibilities:
    - Creates PubSub manager
    - Pre-allocates ALL subscriptions in parent process
    - Spawns worker processes with pre-allocated resources
    - Manages process lifecycle
    """

    model_config = ConfigDict(
        arbitrary_types_allowed = True
    )
    global_kill_flag: multiprocessing.Value
    heartbeat_timestamp: multiprocessing.Value
    subprocess_registry: list[multiprocessing.Process]
    
    def launch_pipeline(
        self,
        *,
        config: PipelineLaunchConfigABC,
        camera_group: CameraGroup | None = None,
        recording_path: str | None = None,
    ) -> PipelineInstance:
        """
        Launch a pipeline from declarative configuration.
        
        CRITICAL FLOW:
        1. Create PubSubTopicManager
        2. Pre-allocate subscriptions in parent process
        3. Create Pipeline IPC with pre-allocated resources
        4. Spawn processes with subscriptions
        
        Args:
            config: Declarative pipeline configuration
            camera_group: For realtime pipelines
            recording_path: For posthoc pipelines
        
        Returns:
            PipelineInstance with running nodes
        """
        pipeline_id = str(uuid.uuid4())[:6]
        logger.info(f"Launching pipeline {pipeline_id} of type {config.pipeline_type}")
        
        # Validate inputs based on pipeline type
        if config.pipeline_type == PipelineType.REALTIME:
            if camera_group is None:
                raise ValueError("Realtime pipeline requires camera_group")
        elif config.pipeline_type == PipelineType.POSTHOC:
            if recording_path is None:
                raise ValueError("Posthoc pipeline requires recording_path")
        
        # Create PubSub manager and IPC
        ipc = self._create_ipc(
            pipeline_id=pipeline_id,
            camera_group=camera_group,
        )
        
        # Pre-allocate pubsub subscriptions
        subscriptions_by_node = self._preallocate_subscriptions(
            config=config,
            pubsub=ipc.pubsub,
        )
        
        # Create nodes with pre-allocated subscriptions
        nodes = {}
        
        # Create camera nodes
        for camera_id, camera_params in config.camera_node_params.items():
            node_id = f"camera-{camera_id}"
            nodes[node_id] = self._create_camera_node(
                node_id=node_id,
                params=camera_params,
                subscriptions=subscriptions_by_node[node_id],
                ipc=ipc,
                camera_group=camera_group,
                config=config,
            )
        
        # Create aggregation node
        agg_node_id = f"aggregation-{config.camera_group_id}"
        nodes[agg_node_id] = self._create_aggregation_node(
            node_id=agg_node_id,
            params=config.aggregation_node_params,
            subscriptions=subscriptions_by_node[agg_node_id],
            ipc=ipc,
            camera_group=camera_group,
            config=config,
        )
        
        # Step 4: Start all nodes
        pipeline = PipelineInstance(
            pipeline_id=pipeline_id,
            config=config,
            nodes=nodes,
            pubsub=ipc.pubsub,
            ipc=ipc,
        )
        
        self._start_pipeline(pipeline)
        
        return pipeline
    
    def create_ipc(
        self,
        *,
        pipeline_id: PipelineIdString,
        camera_group: CameraGroup | None,
    ) -> PipelineIPC:
        """Create IPC resources for the pipeline."""

        # For realtime, get shared memory topic from camera group
        if camera_group is not None:
            shm_topic = camera_group.ipc.pubsub.topics[TopicTypes.SHM_UPDATES]
        else:
            # For posthoc, create a dummy topic or handle differently
            from skellycam.core.ipc.pubsub.pubsub_topics import SetShmTopic
            shm_topic = SetShmTopic()
        
        return PipelineIPC.create(
            global_kill_flag=self.global_kill_flag,
            heartbeat_timestamp=self.heartbeat_timestamp,
            shm_topic=shm_topic,
            pipeline_id=pipeline_id,
        )
    
    def preallocate_subscriptions(
        self,
        *,
        config: PipelineLaunchConfigABC,
        pubsub: PubSubTopicManager,
    ) -> dict[str, dict[type[PubSubTopicABC], TopicSubscriptionQueue]]:
        """
        Pre-allocate all subscriptions for all nodes.
        MUST be called from parent process!
        
        Returns:
            Dictionary mapping node_id to its subscriptions
        """
        logger.debug("Pre-allocating subscriptions for all nodes")
        
        subscriptions_by_node = {}
        
        # Allocate for camera nodes
        for camera_id, camera_params in config.camera_node_params.items():
            node_id = f"camera-{camera_id}"
            node_subs = {}
            
            for topic_type in camera_params.get_subscription_requirements():
                logger.trace(f"Allocating subscription for {node_id} to {topic_type.__name__}")
                node_subs[topic_type] = pubsub.get_subscription(topic_type)
            
            subscriptions_by_node[node_id] = node_subs
        
        # Allocate for aggregation node
        agg_node_id = f"aggregation-{config.camera_group_id}"
        agg_subs = {}
        
        for topic_type in config.aggregation_node_params.get_subscription_requirements():
            logger.trace(f"Allocating subscription for {agg_node_id} to {topic_type.__name__}")
            agg_subs[topic_type] = pubsub.get_subscription(topic_type)
        
        subscriptions_by_node[agg_node_id] = agg_subs
        
        # Also need to allocate the SHM topic subscription for aggregation node
        # This is a special case from the existing code
        from skellycam.core.ipc.pubsub.pubsub_topics import SetShmTopic
        if SetShmTopic not in agg_subs:
            agg_subs[SetShmTopic] = self.ipc.shm_topic.get_subscription()
        
        logger.info(f"Pre-allocated subscriptions for {len(subscriptions_by_node)} nodes")
        return subscriptions_by_node
    
    def create_camera_node(
        self,
        *,
        node_id: str,
        params: CameraNodeParams,
        subscriptions: dict[type[PubSubTopicABC], TopicSubscriptionQueue],
        ipc: PipelineIPC,
        camera_group: CameraGroup | None,
        config: PipelineLaunchConfigABC,
    ) -> ProcessNodeABC:
        """Create a camera processing node."""
        # Import here to avoid circular dependencies

        # Get camera-specific resources
        if camera_group is not None:
            camera_shm_dto = camera_group.shm.to_dto().camera_shm_dtos[params.camera_id]
        else:
            # For posthoc, would load from disk
            raise NotImplementedError("Posthoc camera node creation not implemented")
        
        return CameraNode.create(
            node_id=node_id,
            params=params,
            subscriptions=subscriptions,
            pubsub=ipc.pubsub,
            subprocess_registry=self.subprocess_registry,
            camera_shm_dto=camera_shm_dto,
            pipeline_config=config,
            ipc=ipc,
        )
    
    def create_aggregation_node(
        self,
        *,
        node_id: str,
        params: AggregationNodeParams,
        subscriptions: dict[type[PubSubTopicABC], TopicSubscriptionQueue],
        ipc: PipelineIPC,
        camera_group: CameraGroup | None,
        config: PipelineLaunchConfigABC,
    ) -> ProcessNodeABC:
        """Create an aggregation node."""
        # Import here to avoid circular dependencies

        return AggregationNode.create(
            node_id=node_id,
            params=params,
            subscriptions=subscriptions,
            pubsub=ipc.pubsub,
            subprocess_registry=self.subprocess_registry,
            pipeline_config=config,
            ipc=ipc,
        )
    

    def start_pipeline(self, pipeline: PipelineInstance) -> None:
        """Start all nodes in the pipeline."""
        logger.info(f"Starting pipeline {pipeline.pipeline_id}")
        
        # Start nodes in dependency order
        # First aggregation (it waits for camera outputs)
        for node_id, node in pipeline.nodes.items():
            if "aggregation" in node_id:
                node.start()
        
        # Then camera nodes
        for node_id, node in pipeline.nodes.items():
            if "camera" in node_id:
                node.start()
        
        # Verify all started
        if not pipeline.is_alive:
            raise RuntimeError(f"Failed to start all nodes in pipeline {pipeline.pipeline_id}")
        
        logger.info(f"Pipeline {pipeline.pipeline_id} started successfully")
