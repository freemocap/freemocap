"""
Concrete pipeline implementations for realtime and posthoc processing.
"""
import logging
from abc import ABC, abstractmethod
from pydantic import BaseModel

from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.recorders.videos.recording_info import RecordingInfo

from freemocap.core.pipeline.base_node_abcs import PipelineType
from freemocap.core.pipeline.og.frontend_payload import FrontendPayload
from freemocap.core.pipeline.pipeline_launch_configs import PipelineLaunchConfigABC, RealtimeLaunchConfig, \
    PosthocPipelineLaunchConfig
from freemocap.core.pipeline.pipeline_launcher import PipelineInstance, PipelineLauncher

from freemocap.core.types.type_overloads import FrameNumberInt
from freemocap.pubsub.pubsub_topics import (
    AggregationNodeOutputMessage,
    AggregationNodeOutputTopic,
    PipelineConfigUpdateMessage,
    PipelineConfigUpdateTopic,
    ShouldCalibrateMessage,
    ShouldCalibrateTopic,
)

logger = logging.getLogger(__name__)


class PipelineABC(BaseModel,ABC):
    """Abstract base class for all pipeline types."""
    
    launcher: PipelineLauncher
    config: PipelineLaunchConfigABC

    instance: PipelineInstance | None = None
        
    aggregation_subscription = None
    
    @abstractmethod
    def start(self) -> None:
        """Start the pipeline."""
        raise NotImplementedError
    
    @abstractmethod
    def stop(self) -> None:
        """Stop the pipeline."""
        raise NotImplementedError
    
    @property
    def is_running(self) -> bool:
        """Check if pipeline is running."""
        return self.instance is not None and self.instance.is_alive
    
    @property
    def pipeline_id(self) -> str | None:
        """Get pipeline ID if running."""
        return self.instance.pipeline_id if self.instance else None
    
    def get_latest_frontend_payload(
        self,
        if_newer_than: FrameNumberInt
    ) -> tuple[bytes, FrontendPayload | None] | None:
        """
        Get latest frontend payload if available.
        
        Args:
            if_newer_than: Only return payload if newer than this frame
        
        Returns:
            Tuple of (frame_bytes, frontend_payload) or None
        """
        if not self.is_running or self.aggregation_subscription is None:
            return None
        
        # Get latest aggregation output
        aggregation_output: AggregationNodeOutputMessage | None = None
        while not self.aggregation_subscription.empty():
            aggregation_output = self.aggregation_subscription.get()
        
        if aggregation_output is None or aggregation_output.frame_number <= if_newer_than:
            return None
        
        # Convert to frontend payload
        frontend_payload = FrontendPayload.from_aggregation_output(
            aggregation_output=aggregation_output
        )
        
        # Get frame bytes (placeholder - would get from camera group)
        frame_bytes = b""  # TODO: Get actual frame bytes
        
        return (frame_bytes, frontend_payload)
    
    def update_config(self, new_config: PipelineLaunchConfigABC) -> None:
        """
        Update pipeline configuration.
        
        Args:
            new_config: New pipeline configuration
        """
        if not self.is_running:
            raise RuntimeError("Cannot update config on stopped pipeline")
        
        # Verify config type matches
        if type(new_config) != type(self.config):
            raise TypeError(
                f"Cannot change config type from {type(self.config).__name__} "
                f"to {type(new_config).__name__}"
            )
        
        self.config = new_config
        
        # Get camera configs based on config type
        camera_configs = None
        if isinstance(new_config, RealtimeLaunchConfig):
            camera_configs = new_config.camera_configs
        elif isinstance(new_config, PosthocPipelineLaunchConfig):
            # For posthoc, create dummy camera configs
            from skellycam.core.camera.config.camera_config import CameraConfig, CameraConfigs
            camera_configs = CameraConfigs()
            for camera_id in new_config.get_camera_ids():
                camera_configs[camera_id] = CameraConfig(
                    camera_id=camera_id,
                    resolution=(1920, 1080),
                    fps=30,
                )
        
        # Convert to legacy config and publish update
        from freemocap.core.pipeline.og.pipeline_configs import PipelineConfig
        
        legacy_config = PipelineConfig(
            camera_configs=camera_configs,
            calibration_task_config=new_config.calibration_task_config,
            mocap_task_config=new_config.mocap_task_config,
        )
        
        self.instance.pubsub.publish(
            topic_type=PipelineConfigUpdateTopic,
            message=PipelineConfigUpdateMessage(pipeline_config=legacy_config)
        )


class RealtimePipeline(PipelineABC):
    """
    Pipeline for processing realtime camera feeds.
    """

    config: RealtimeLaunchConfig
    camera_group: CameraGroup

    def start(self) -> None:
        """Start realtime pipeline processing."""
        if self.is_running:
            logger.warning("Pipeline already running")
            return
        
        logger.info(f"Starting realtime pipeline for camera group {self.config.camera_group_id}")
        
        # Start camera group if needed
        if not self.camera_group.started:
            self.camera_group.start()
        
        # Launch pipeline with pre-allocated resources
        self.instance = self.launcher.launch_pipeline(
            config=self.config,
            camera_group=self.camera_group,
        )
        
        # Subscribe to aggregation output
        self.aggregation_subscription = self.instance.pubsub.get_subscription(
            AggregationNodeOutputTopic
        )
        
        logger.info(f"Realtime pipeline {self.pipeline_id} started successfully")
    
    def stop(self) -> None:
        """Stop realtime pipeline processing."""
        if not self.is_running:
            logger.warning("Pipeline not running")
            return
        
        logger.info(f"Stopping realtime pipeline {self.pipeline_id}")
        
        # Shutdown pipeline instance
        self.instance.shutdown()
        
        # Stop camera group if we started it
        if self.camera_group.started:
            self.camera_group.close()
        
        self.instance = None
        self.aggregation_subscription = None
        
        logger.info("Realtime pipeline stopped")
    
    def start_recording(self, recording_info: RecordingInfo) -> None:
        """
        Start recording video from cameras.
        
        Args:
            recording_info: Recording configuration
        """
        if not self.is_running:
            raise RuntimeError("Pipeline must be running to start recording")
        
        self.camera_group.start_recording(recording_info=recording_info)
    
    def stop_recording(self) -> None:
        """Stop recording video from cameras."""
        if not self.is_running:
            raise RuntimeError("Pipeline must be running to stop recording")
        
        self.camera_group.stop_recording()
    
    def start_calibration(self) -> None:
        """Trigger calibration process."""
        if not self.is_running:
            raise RuntimeError("Pipeline must be running to start calibration")
        
        self.instance.pubsub.publish(
            topic_type=ShouldCalibrateTopic,
            message=ShouldCalibrateMessage()
        )


class PosthocPipeline(PipelineABC):
    """
    Pipeline for processing recorded data.
    """
    
    launcher: PipelineLauncher
    config: PosthocPipelineLaunchConfig


    def start(self) -> None:
        """Start posthoc pipeline processing."""
        if self.is_running:
            logger.warning("Pipeline already running")
            return
        
        logger.info(f"Starting posthoc pipeline for recording {self.config.recording_path}")
        
        # Launch pipeline (no camera_group needed for posthoc)
        self.instance = self.launcher.launch_pipeline(
            config=self.config,
            camera_group=None,
        )
        
        # Subscribe to aggregation output
        self.aggregation_subscription = self.instance.pubsub.get_subscription(
            AggregationNodeOutputTopic
        )
        
        logger.info(f"Posthoc pipeline {self.pipeline_id} started successfully")
    
    def stop(self) -> None:
        """Stop posthoc pipeline processing."""
        if not self.is_running:
            logger.warning("Pipeline not running")
            return
        
        logger.info(f"Stopping posthoc pipeline {self.pipeline_id}")
        
        # Shutdown pipeline instance
        self.instance.shutdown()
        
        self.instance = None
        self.aggregation_subscription = None
        
        logger.info("Posthoc pipeline stopped")
    
    def process_batch(
        self,
        start_frame: int,
        end_frame: int,
        step: int = 1
    ) -> None:
        """
        Process a batch of frames.
        
        Args:
            start_frame: Starting frame number
            end_frame: Ending frame number (inclusive)
            step: Frame step size
        """
        if not self.is_running:
            raise RuntimeError("Pipeline must be running to process batch")
        
        # Send frame numbers to be processed
        from freemocap.pubsub.pubsub_topics import ProcessFrameNumberMessage, ProcessFrameNumberTopic
        
        for frame_num in range(start_frame, end_frame + 1, step):
            self.instance.pubsub.publish(
                topic_type=ProcessFrameNumberTopic,
                message=ProcessFrameNumberMessage(frame_number=frame_num)
            )
            
        logger.info(f"Queued frames {start_frame} to {end_frame} (step={step}) for processing")
    
    def get_progress(self) -> tuple[int, int]:
        """
        Get processing progress.
        
        Returns:
            Tuple of (processed_frames, total_frames)
        """
        if not self.config.end_frame:
            return (0, 0)
        
        total_frames = self.config.end_frame - self.config.start_frame + 1
        # TODO: Track actual processed frames from aggregation output
        processed_frames = 0
        
        return (processed_frames, total_frames)
