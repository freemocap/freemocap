"""
Updated pipeline manager using the new launcher architecture.
"""
import logging
import multiprocessing
from pydantic import BaseModel, ConfigDict, Field
from typing import Any

from skellycam.core.camera_group.camera_group import CameraGroup
from skellycam.core.recorders.videos.recording_info import RecordingInfo
from skellycam.core.types.type_overloads import CameraIdString

from freemocap.core.pipeline.og.frontend_payload import FrontendPayload
from freemocap.core.pipeline.og.pipeline_configs import CalibrationTaskConfig
from freemocap.core.pipeline.pipeline_implementations import (
    PipelineABC,
    RealtimePipeline,
    PosthocPipeline,
)
from freemocap.core.pipeline.pipeline_launcher import PipelineLauncher
from freemocap.core.pipeline.pipeline_launch_configs import (
    RealtimeLaunchConfig,
    PosthocPipelineLaunchConfig, PipelineLaunchConfigABC,
)

from freemocap.core.types.type_overloads import PipelineIdString, FrameNumberInt

logger = logging.getLogger(__name__)


class PipelineManager(BaseModel):
    """
    High-level pipeline manager using the new launcher architecture.

    Manages multiple pipelines and delegates orchestration to PipelineLauncher.
    """
    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
    )

    global_kill_flag: multiprocessing.Value
    heartbeat_timestamp: multiprocessing.Value
    subprocess_registry: list[multiprocessing.Process]

    # Internal state
    launcher: PipelineLauncher
    lock: multiprocessing.Lock = Field(default_factory=multiprocessing.Lock)
    pipelines: dict[PipelineIdString, PipelineABC] = Field(default_factory=dict)

    @classmethod
    def create(
            cls,
            *,
            global_kill_flag: multiprocessing.Value,
            heartbeat_timestamp: multiprocessing.Value,
            subprocess_registry: list[multiprocessing.Process]):
        """
        Factory method to create a PipelineManager.

        Args:
            global_kill_flag: Shared kill flag for subprocesses
            heartbeat_timestamp: Shared heartbeat timestamp
            subprocess_registry: Registry of subprocesses
        Returns:
            Initialized PipelineManager instance
        """
        return cls(
            global_kill_flag=global_kill_flag,
            heartbeat_timestamp=heartbeat_timestamp,
            subprocess_registry=subprocess_registry,
            launcher=PipelineLauncher(
                global_kill_flag=global_kill_flag,
                heartbeat_timestamp=heartbeat_timestamp,
                subprocess_registry=subprocess_registry,
            )
        )


    async def create_realtime_pipeline(
            self,
            *,
            camera_group: CameraGroup,
            calibration_task_config: CalibrationTaskConfig | None = None,
    ) -> RealtimePipeline:
        """
        Create a realtime processing pipeline.

        Args:
            camera_group: Camera group for realtime feeds
            calibration_task_config: Optional calibration configuration

        Returns:
            Started realtime pipeline
        """
        with self.lock:
            # Check if pipeline already exists for these cameras
            camera_ids = set(camera_group.configs.keys())
            for pipeline in self.pipelines.values():
                if isinstance(pipeline, RealtimePipeline):
                    pipeline_camera_ids = set(pipeline.config.get_camera_ids())
                    if camera_ids == pipeline_camera_ids:
                        logger.info(f"Found existing pipeline {pipeline.pipeline_id} for cameras")
                        return pipeline

            # Create new realtime config
            config = RealtimeLaunchConfig.create(
                camera_group_id=camera_group.id,
                camera_configs=camera_group.configs,
                calibration_task_config=calibration_task_config,
            )

            # Create and start pipeline
            pipeline = RealtimePipeline(
                launcher=self.launcher,
                config=config,
                camera_group=camera_group,
            )

            pipeline.start()

            # Register pipeline
            if pipeline.pipeline_id:
                self.pipelines[pipeline.pipeline_id] = pipeline

            logger.info(f"Created realtime pipeline {pipeline.pipeline_id}")
            return pipeline

    async def create_posthoc_pipeline(
            self,
            *,
            recording_path: str,
            calibration_task_config: CalibrationTaskConfig | None = None,
    ) -> PosthocPipeline:
        """
        Create a post-hoc processing pipeline.

        Args:
            recording_path: Path to recorded data directory
            video_paths: Optional explicit video paths per camera
            calibration_task_config: Optional calibration configuration

        Returns:
            Started posthoc pipeline
        """
        with self.lock:
            # Auto-discover videos from directory
            config = PosthocPipelineLaunchConfig.from_recording_directory(
                recording_path=recording_path,
                calibration_task_config=calibration_task_config,
            )

            # Create and start pipeline
            pipeline = PosthocPipeline(
                launcher=self.launcher,
                config=config,
            )

            pipeline.start()

            # Register pipeline
            if pipeline.pipeline_id:
                self.pipelines[pipeline.pipeline_id] = pipeline

            logger.info(f"Created posthoc pipeline {pipeline.pipeline_id}")
            return pipeline

    def get_pipeline(self, pipeline_id: PipelineIdString) -> PipelineABC | None:
        """
        Get pipeline by ID.

        Args:
            pipeline_id: Pipeline identifier

        Returns:
            Pipeline instance or None if not found
        """
        with self.lock:
            return self.pipelines.get(pipeline_id)

    def get_pipeline_by_cameras(
            self,
            camera_ids: list[CameraIdString]
    ) -> PipelineABC | None:
        """
        Get pipeline by camera IDs.

        Args:
            camera_ids: List of camera identifiers

        Returns:
            Pipeline instance or None if not found
        """
        with self.lock:
            camera_set = set(camera_ids)
            for pipeline in self.pipelines.values():
                pipeline_camera_set = set(pipeline.config.get_camera_ids())
                if camera_set == pipeline_camera_set:
                    return pipeline
            return None

    def close_pipeline(self, pipeline_id: PipelineIdString) -> None:
        """
        Close a specific pipeline.

        Args:
            pipeline_id: Pipeline to close
        """
        with self.lock:
            pipeline = self.pipelines.get(pipeline_id)
            if pipeline:
                logger.info(f"Closing pipeline {pipeline_id}")
                pipeline.stop()
                del self.pipelines[pipeline_id]
            else:
                logger.warning(f"Pipeline {pipeline_id} not found")

    def close_all_pipelines(self) -> None:
        """Close all running pipelines."""
        with self.lock:
            logger.info(f"Closing {len(self.pipelines)} pipelines")

            for pipeline_id in list(self.pipelines.keys()):
                pipeline = self.pipelines[pipeline_id]
                pipeline.stop()
                del self.pipelines[pipeline_id]

            logger.info("All pipelines closed")

    def get_latest_frontend_payloads(
            self,
            if_newer_than: FrameNumberInt
    ) -> dict[PipelineIdString, tuple[bytes | None, FrontendPayload | None]]:
        """
        Get latest frontend payloads from all pipelines.

        Args:
            if_newer_than: Only return payloads newer than this frame

        Returns:
            Dictionary mapping pipeline ID to payload tuple
        """
        payloads = {}

        with self.lock:
            for pipeline_id, pipeline in self.pipelines.items():
                payload = pipeline.get_latest_frontend_payload(if_newer_than)
                if payload is not None:
                    payloads[pipeline_id] = payload
                    logger.trace(f"Got payload from pipeline {pipeline_id}")

        return payloads

    def pause_unpause_pipelines(self) -> None:
        """Pause/unpause all realtime pipelines."""
        with self.lock:
            for pipeline in self.pipelines.values():
                if isinstance(pipeline, RealtimePipeline):
                    pipeline.camera_group.pause_unpause()

    def start_recording_all(self, recording_info: RecordingInfo) -> None:
        """
        Start recording on all realtime pipelines.

        Args:
            recording_info: Recording configuration
        """
        with self.lock:
            for pipeline in self.pipelines.values():
                if isinstance(pipeline, RealtimePipeline):
                    pipeline.start_recording(recording_info)
                    logger.info(f"Started recording on pipeline {pipeline.pipeline_id}")

    def stop_recording_all(self) -> None:
        """Stop recording on all realtime pipelines."""
        with self.lock:
            for pipeline in self.pipelines.values():
                if isinstance(pipeline, RealtimePipeline):
                    pipeline.stop_recording()
                    logger.info(f"Stopped recording on pipeline {pipeline.pipeline_id}")

    def update_calibration_config(
            self,
            calibration_task_config: CalibrationTaskConfig
    ) -> None:
        """
        Update calibration configuration for all pipelines.

        Args:
            calibration_task_config: New calibration configuration
        """
        with self.lock:
            for pipeline in self.pipelines.values():
                # Create new config based on pipeline type
                if isinstance(pipeline, RealtimePipeline):
                    # Update realtime config
                    old_config = pipeline.config
                    new_config = RealtimeLaunchConfig(
                        pipeline_type=old_config.pipeline_type,
                        camera_group_id=old_config.camera_group_id,
                        camera_configs=old_config.camera_configs,
                        camera_node_params=old_config.camera_node_params,
                        aggregation_node_params=old_config.aggregation_node_params,
                        calibration_task_config=calibration_task_config,
                        mocap_task_config=old_config.mocap_task_config,
                    )
                elif isinstance(pipeline, PosthocPipeline):
                    # Update posthoc config
                    old_config = pipeline.config
                    new_config = PosthocPipelineLaunchConfig(
                        pipeline_type=old_config.pipeline_type,
                        camera_group_id=old_config.camera_group_id,
                        recording_path=old_config.recording_path,
                        video_paths=old_config.video_paths,
                        video_node_params=old_config.video_node_params,
                        aggregation_node_params=old_config.aggregation_node_params,
                        calibration_task_config=calibration_task_config,
                        mocap_task_config=old_config.mocap_task_config,
                        start_frame=old_config.start_frame,
                        end_frame=old_config.end_frame,
                    )
                else:
                    logger.warning(f"Unknown pipeline type: {type(pipeline)}")
                    continue

                pipeline.update_config(new_config)
                logger.info(f"Updated calibration config for pipeline {pipeline.pipeline_id}")

    def start_calibration_recording(
            self,
            recording_info: RecordingInfo,
            config: CalibrationTaskConfig,
            pipeline_id: PipelineIdString | None = None,
    ) -> None:
        """
        Start calibration recording.

        Args:
            recording_info: Recording configuration
            config: Calibration configuration
            pipeline_id: Optional specific pipeline (uses first if not specified)
        """
        with self.lock:
            if pipeline_id:
                pipeline = self.pipelines.get(pipeline_id)
                if not pipeline:
                    raise ValueError(f"Pipeline {pipeline_id} not found")
                pipelines = [pipeline]
            else:
                pipelines = list(self.pipelines.values())
                if not pipelines:
                    raise RuntimeError("No pipelines available")

            # Use first realtime pipeline
            for pipeline in pipelines:
                if isinstance(pipeline, RealtimePipeline):
                    # Update calibration config
                    pipeline.update_config(RealtimeLaunchConfig(
                        **pipeline.config.model_dump(),
                        calibration_task_config=config,
                    ))

                    # Start recording
                    pipeline.start_recording(recording_info)

                    logger.info(f"Started calibration recording on pipeline {pipeline.pipeline_id}")
                    return

            raise RuntimeError("No realtime pipelines available for calibration recording")

    def stop_calibration_recording(
            self,
            pipeline_id: PipelineIdString | None = None,
    ) -> None:
        """
        Stop calibration recording and trigger calibration.

        Args:
            pipeline_id: Optional specific pipeline
        """
        with self.lock:
            if pipeline_id:
                pipeline = self.pipelines.get(pipeline_id)
                if not pipeline:
                    raise ValueError(f"Pipeline {pipeline_id} not found")
                pipelines = [pipeline]
            else:
                pipelines = list(self.pipelines.values())

            for pipeline in pipelines:
                if isinstance(pipeline, RealtimePipeline):
                    pipeline.stop_recording()
                    pipeline.start_calibration()
                    logger.info(
                        f"Stopped calibration recording and started calibration on pipeline {pipeline.pipeline_id}")
                    return

            raise RuntimeError("No realtime pipelines available")

    def get_pipeline_states(self) -> dict[PipelineIdString, dict[str, Any]]:
        """
        Get status of all pipelines.

        Returns:
            Dictionary mapping pipeline ID to status info
        """
        states = {}

        with self.lock:
            for pipeline_id, pipeline in self.pipelines.items():
                states[pipeline_id] = {
                    "type": pipeline.config.pipeline_type.value,
                    "is_running": pipeline.is_running,
                    "camera_count": len(pipeline.config.get_camera_ids()),
                    "camera_ids": list(pipeline.config.get_camera_ids()),
                }

        return states