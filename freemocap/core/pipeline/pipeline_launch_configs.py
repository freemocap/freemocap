"""
Declarative pipeline launch configurations with abstract base and concrete implementations.
"""
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field, ConfigDict
from skellycam.core.camera.config.camera_config import CameraConfigs
from skellycam.core.types.type_overloads import CameraIdString, CameraGroupIdString

from freemocap.core.pipeline.aggregation_node import AggregationNodeParams
from freemocap.core.pipeline.base_node_abcs import ProcessNodeParams, PipelineType
from freemocap.core.pipeline.camera_node import CameraNodeParams
from freemocap.core.pipeline.og.pipeline_configs import CalibrationTaskConfig, MocapTaskConfig
from freemocap.core.pipeline.video_node import VideoNodeParams
from freemocap.pubsub.pubsub_abcs import PubSubTopicABC


class PipelineLaunchConfigABC(BaseModel, ABC):
    """
    Abstract base for pipeline launch configurations.
    Defines common interface and abstract methods for pipeline setup.
    """
    model_config = ConfigDict(
        extra="forbid",
        frozen=True
    )

    pipeline_type: PipelineType
    camera_group_id: CameraGroupIdString

    # Task configurations (common to all pipelines)
    calibration_task_config: CalibrationTaskConfig = Field(default_factory=CalibrationTaskConfig)
    mocap_task_config: MocapTaskConfig = Field(default_factory=MocapTaskConfig)

    @property
    @abstractmethod
    def source_node_params(self) -> dict[CameraIdString, ProcessNodeParams]:
        """Get the source node params (camera or video nodes)."""
        raise NotImplementedError

    @property
    @abstractmethod
    def aggregation_node_params(self) -> AggregationNodeParams:
        """Get aggregation node parameters."""
        raise NotImplementedError

    # Concrete implementations - no duplication needed!
    def get_all_node_params(self) -> list[ProcessNodeParams]:
        """Get all node parameters for subscription pre-allocation."""
        nodes: list[ProcessNodeParams] = list(self.source_node_params.values())
        nodes.append(self.aggregation_node_params)
        return nodes

    def get_required_topics(self) -> set[type[PubSubTopicABC]]:
        """Get all topics needed by any node in the pipeline."""
        topics: set[type[PubSubTopicABC]] = set()
        for node_params in self.get_all_node_params():
            topics.update(node_params.get_subscription_requirements())
            topics.update(node_params.get_publication_topics())
        return topics

    def get_camera_ids(self) -> list[CameraIdString]:
        """Get list of camera IDs in this pipeline."""
        return list(self.source_node_params.keys())


class RealtimeLaunchConfig(PipelineLaunchConfigABC):
    """
    Launch configuration for realtime pipelines.
    Works with live CAMERA feeds from hardware.
    """

    pipeline_type: PipelineType = Field(default=PipelineType.REALTIME, frozen=True)

    # Realtime-specific: camera configurations and nodes
    camera_configs: CameraConfigs
    camera_node_params: dict[CameraIdString, CameraNodeParams]
    aggregation_node_params: AggregationNodeParams

    @property
    def source_node_params(self) -> dict[CameraIdString, ProcessNodeParams]:
        """Get the source node params (camera nodes for realtime)."""
        return self.camera_node_params



    @classmethod
    def create(
        cls,
        *,
        camera_group_id: CameraGroupIdString,
        camera_configs: CameraConfigs,
        calibration_task_config: CalibrationTaskConfig | None = None,
        mocap_task_config: MocapTaskConfig | None = None,
    ) -> "RealtimeLaunchConfig":
        """
        Factory method for creating realtime pipeline configuration.

        Args:
            camera_group_id: Identifier for the camera group
            camera_configs: Hardware camera configurations
            calibration_task_config: Optional calibration settings
            mocap_task_config: Optional mocap settings

        Returns:
            Configured realtime launch config
        """
        camera_ids = list(camera_configs.keys())

        # Create node params for each camera
        camera_node_params = {
            camera_id: CameraNodeParams(
                camera_id=camera_id,
                calibration_task_config=calibration_task_config or CalibrationTaskConfig(),
                mocap_task_config=mocap_task_config or MocapTaskConfig(),
            )
            for camera_id in camera_ids
        }

        # Create aggregation node params
        aggregation_node_params = AggregationNodeParams(
            camera_group_id=camera_group_id,
            camera_ids=camera_ids,
            calibration_task_config=calibration_task_config or CalibrationTaskConfig(),
            mocap_task_config=mocap_task_config or MocapTaskConfig(),
        )

        return cls(
            camera_group_id=camera_group_id,
            camera_configs=camera_configs,
            camera_node_params=camera_node_params,
            aggregation_node_params=aggregation_node_params,
            calibration_task_config=calibration_task_config or CalibrationTaskConfig(),
            mocap_task_config=mocap_task_config or MocapTaskConfig(),
        )


class PosthocPipelineLaunchConfig(PipelineLaunchConfigABC):
    """
    Launch configuration for posthoc pipelines.
    Works with recorded VIDEO files from disk.
    """

    pipeline_type: PipelineType = Field(default=PipelineType.POSTHOC, frozen=True)

    # Posthoc-specific: video paths and nodes
    recording_path: Path
    video_paths: dict[CameraIdString, Path]
    video_node_params: dict[CameraIdString, VideoNodeParams]
    aggregation_node_params: AggregationNodeParams

    # Optional frame range for processing
    start_frame: int = Field(default=0, ge=0)
    end_frame: int | None = Field(default=None, ge=0)

    @property
    def source_node_params(self) -> dict[CameraIdString, ProcessNodeParams]:
        """Get the source node params (video nodes for posthoc)."""
        return self.video_node_params

    @property
    def aggregation_node_params(self) -> AggregationNodeParams:
        """Get aggregation node parameters."""
        return self.aggregation_node_params

    @classmethod
    def create(
        cls,
        *,
        recording_path: Path | str,
        video_paths: dict[CameraIdString, Path | str],
        calibration_task_config: CalibrationTaskConfig | None = None,
        mocap_task_config: MocapTaskConfig | None = None,
        start_frame: int = 0,
        end_frame: int | None = None,
    ) -> "PosthocPipelineLaunchConfig":
        """
        Factory method for creating posthoc pipeline configuration.

        Args:
            recording_path: Base path to recording directory
            video_paths: Dictionary mapping camera IDs to video file paths
            calibration_task_config: Optional calibration settings
            mocap_task_config: Optional mocap settings
            start_frame: Starting frame for processing
            end_frame: Optional ending frame (processes all if None)

        Returns:
            Configured posthoc launch config
        """
        # Convert strings to Paths
        recording_path = Path(recording_path)
        video_paths_typed = {
            camera_id: Path(video_path) if isinstance(video_path, str) else video_path
            for camera_id, video_path in video_paths.items()
        }

        # Validate video files exist
        for camera_id, video_path in video_paths_typed.items():
            if not video_path.exists():
                raise FileNotFoundError(f"Video file not found for camera {camera_id}: {video_path}")

        camera_ids = list(video_paths_typed.keys())

        # Derive camera group ID from recording path
        camera_group_id = recording_path.stem

        # Create node params for each video
        video_node_params = {
            camera_id: VideoNodeParams(
                video_path=video_path,
                camera_id=camera_id,
                start_frame=start_frame,
                end_frame=end_frame,
                calibration_task_config=calibration_task_config or CalibrationTaskConfig(),
                mocap_task_config=mocap_task_config or MocapTaskConfig(),
            )
            for camera_id, video_path in video_paths_typed.items()
        }

        # Create aggregation node params
        aggregation_node_params = AggregationNodeParams(
            camera_group_id=camera_group_id,
            camera_ids=camera_ids,
            calibration_task_config=calibration_task_config or CalibrationTaskConfig(),
            mocap_task_config=mocap_task_config or MocapTaskConfig(),
        )

        return cls(
            camera_group_id=camera_group_id,
            recording_path=recording_path,
            video_paths=video_paths_typed,
            video_node_params=video_node_params,
            aggregation_node_params=aggregation_node_params,
            calibration_task_config=calibration_task_config or CalibrationTaskConfig(),
            mocap_task_config=mocap_task_config or MocapTaskConfig(),
            start_frame=start_frame,
            end_frame=end_frame,
        )

    @classmethod
    def from_recording_directory(
        cls,
        *,
        recording_path: Path | str,
        calibration_task_config: CalibrationTaskConfig | None = None,
        mocap_task_config: MocapTaskConfig | None = None,
        video_subfolder: str | None = "synchronized_videos",
        video_extension: str = ".mp4",
        start_frame: int = 0,
        end_frame: int | None = None,
    ) -> "PosthocPipelineLaunchConfig":
        """
        Factory method to create config from a recording directory.
        Auto-discovers video files in the directory.

        Args:
            recording_path: Path to recording directory
            calibration_task_config: Optional calibration settings
            mocap_task_config: Optional mocap settings
            video_subfolder: Subfolder containing videos (None for root)
            video_extension: Video file extension to search for
            start_frame: Starting frame for processing
            end_frame: Optional ending frame

        Returns:
            Configured posthoc launch config
        """
        recording_path = Path(recording_path)
        if not recording_path.exists():
            raise FileNotFoundError(f"Recording directory not found: {recording_path}")

        if video_subfolder is None:
            videos_folder_path = recording_path
        else:
            videos_folder_path = recording_path / video_subfolder
            if not videos_folder_path.exists():
                raise FileNotFoundError(f"Video subfolder not found: {videos_folder_path}")

        # Find all video files in directory
        video_files = list(videos_folder_path.glob(f"*{video_extension}"))
        if not video_files:
            raise FileNotFoundError(f"No {video_extension} files found in {videos_folder_path}")

        # Build video_paths dict using filename stem as camera ID
        video_paths = {
            video_file.stem: video_file
            for video_file in video_files
        }

        return cls.create(
            recording_path=recording_path,
            video_paths=video_paths,
            calibration_task_config=calibration_task_config,
            mocap_task_config=mocap_task_config,
            start_frame=start_frame,
            end_frame=end_frame,
        )