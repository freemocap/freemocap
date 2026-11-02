from freemocap.core.blender.blender_export_config import BlenderExportConfig
from freemocap.core.recording.exports.requests import ExportOptions
from typing import Literal
from freemocap.core.reconstruction.alignment_config import MocapAlignmentConfig
from freemocap.core.reconstruction.posthoc_filtering import PosthocFilterConfig

from pydantic import BaseModel, ConfigDict, Field, model_validator
from skellytracker.core import TrackerConfig
from skellytracker.core.detectors.keypoint_detectors.mediapipe.mediapipe_model_manager import (
    MediapipePoseModelComplexity,
)
from skellytracker.core.sessions.execution_provider_name import ExecutionProviderName

from freemocap.core.tasks.triangulation.helpers.triangulation_config import TriangulationConfig
from freemocap.core.tasks.calibration.camera_matching.matching_models import CameraMatchingConfig
from freemocap.core.tracking.board_selection import CharucoBoardMode
from skellytracker.core.detectors.keypoint_detectors.charuco import CharucoBoardDefinition



class PosthocMocapPipelineConfig(BaseModel):
    anchor_segment_name: str = Field(default="pelvis", min_length=1, alias="anchorSegmentName")
    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode='before')
    @classmethod
    def migrate_export_settings(cls, value):
        """Accept historical saved settings; emit only the canonical field names."""
        if not isinstance(value, dict):
            return value
        names = ('export_options', 'exportOptions', 'scientific_exports', 'scientificExports')
        present = [name for name in names if name in value]
        if not present:
            return value
        options = ExportOptions.model_validate(value[present[0]])
        if any(ExportOptions.model_validate(value[name]) != options for name in present[1:]):
            raise ValueError('Conflicting export options in saved settings: ' + ', '.join(present))
        migrated = {key: item for key, item in value.items() if key not in names}
        migrated['export_options'] = options
        return migrated

    pipeline_implementation: Literal["typed_dataflow"] = Field(
        default="typed_dataflow", alias="pipelineImplementation",
        description="Typed data flow graph V1.")
    graph_execution_provider: Literal["auto", "cpu", "cuda"] = Field(
        default="auto", alias="graphExecutionProvider")
    graph_annotate: bool = Field(default=True, alias="graphAnnotate")

    start_stage: Literal['observations', 'triangulation', 'filtering', 'scale_fit', 'reconstruction'] = Field(
        default='observations', alias='startStage')
    # Keep unsupported finish points explicit until their save contracts
    # are implemented. Pydantic otherwise ignores stopStage and runs everything.
    stop_stage: Literal['observations', 'triangulation', 'filtering', 'scale_fit', 'reconstruction'] = Field(default='reconstruction', alias='stopStage',
        description='Last requested stage; early finishes require typed data flow graph V1.')
    base_run_id: int = Field(default=0, ge=0, alias='baseRunId')
    run_save_mode: Literal['overwrite', 'new_run'] = Field(default='overwrite', alias='runSaveMode')
    sensor_group: str | None = Field(default=None, alias='sensorGroup')

    camera_matching: CameraMatchingConfig = Field(default_factory=CameraMatchingConfig, alias="cameraMatching")
    body_alignment: MocapAlignmentConfig = Field(default_factory=MocapAlignmentConfig, alias="bodyAlignment")
    filter_config: PosthocFilterConfig = Field(default_factory=PosthocFilterConfig, alias="filterConfig")

    charuco_tracking_enabled: bool = Field(default=True, alias="charucoTrackingEnabled")
    board_mode: CharucoBoardMode = Field(default=CharucoBoardMode.AUTO, alias="boardMode")
    charuco_board: CharucoBoardDefinition = Field(
        default_factory=CharucoBoardDefinition.create_letter_size_5x3, alias="charucoBoard",
    )

    detector_type: Literal["rtmpose", "mediapipe", "rtmw_mediapipe_hands", "dlc"] = Field(
        default="rtmpose",
        alias="detectorType",
        description="Tracking preset: RTMW, MediaPipe, or RTMW with MediaPipe hands.",
    )
    dlc_model_path: str | None = Field(default=None, alias="dlcModelPath")
    dlc_confidence_threshold: float = Field(default=0.4, ge=0, le=1, alias="dlcConfidenceThreshold")
    # RTMPose settings
    rtmpose_model_name: Literal["rtmw-x-l_256x192", "rtmw-x-l_384x288", "rtmw-l-m_256x192"] = Field(
        default="rtmw-x-l_256x192",
        alias="rtmPoseModelName",
        description="RTMPose wholebody model variant. Only used when detector_type='rtmpose'.",
    )
    rtmpose_confidence_threshold: float = Field(
        default=0.4,
        alias="rtmPoseConfidenceThreshold",
        ge=0.0,
        le=1.0,
        description=(
            "Keypoint confidence threshold for RTMPose (raw SIMCC peak clipped to "
            "[0, 1]). 0.4 clears the model's no-person response band while keeping "
            "~96% of visible keypoints. Only used when detector_type='rtmpose'."
        ),
    )
    execution_provider: ExecutionProviderName | None = Field(
        default=None,
        alias="executionProvider",
        description="ONNX Runtime execution provider for RTMPose. None retains the selected pipeline automatic policy; an explicit choice raises if it cannot load.",
    )
    @model_validator(mode="after")
    def validate_provider_selection(self):
        if (self.execution_provider is not None and self.graph_execution_provider != "auto"
                and self.execution_provider != self.graph_execution_provider):
            raise ValueError("executionProvider and graphExecutionProvider disagree; use executionProvider")
        return self

    # MediaPipe settings (shared across pose/hands/face detectors)
    mediapipe_model_complexity: MediapipePoseModelComplexity = Field(
        default=MediapipePoseModelComplexity.HEAVY,
        alias="mediapipeModelComplexity",
        description="MediaPipe pose model size. Only used when detector_type='mediapipe'.",
    )
    mediapipe_detection_confidence: float = Field(
        default=0.5,
        alias="mediapipeDetectionConfidence",
        ge=0.0,
        le=1.0,
        description="Minimum detection confidence for all MediaPipe detectors.",
    )
    mediapipe_presence_confidence: float = Field(
        default=0.5,
        alias="mediapipePresenceConfidence",
        ge=0.0,
        le=1.0,
        description="Minimum presence confidence for all MediaPipe detectors.",
    )
    mediapipe_tracking_confidence: float = Field(
        default=0.5,
        alias="mediapipeTrackingConfidence",
        ge=0.0,
        le=1.0,
        description="Minimum tracking confidence for all MediaPipe detectors.",
    )
    mediapipe_num_hands: Literal[2] = Field(
        default=2,
        alias="mediapipeNumHands",
        description="Two-sided human presets detect one hand per side; the count is fixed at two.",
    )
    mediapipe_num_faces: int = Field(
        default=1,
        alias="mediapipeNumFaces",
        ge=1,
        le=4,
        description="Number of faces to detect. Only used when detector_type='mediapipe'.",
    )
    video_fps: float = Field(
        default=30.0,
        alias="videoFps",
        gt=0.0,
        description="Frames per second of the recorded video. Used to compute redetect_interval (redetect every 5 s). Set this from cv2.CAP_PROP_FPS before constructing the config for accurate cadence.",
    )
    tracker_config: TrackerConfig | None = Field(default=None)
    calibration_toml_path: str | None = Field(
        default=None,
        alias="calibrationTomlPath",
        description="Selected calibration TOML. Required for multicamera processing; no implicit file selection.",
    )

    triangulation_config: TriangulationConfig = Field(
        default_factory=TriangulationConfig,
        alias="triangulationConfig",
        description="Configuration for the triangulation step of the mocap pipeline.",
    )


    export_tall_csv: bool = Field(default=False, alias="exportTallCsv")
    export_options: ExportOptions = Field(default_factory=ExportOptions, alias='exportOptions')

    blender_import_route: Literal['auto', 'legacy_npy', 'parquet_segments', 'parquet_constraints'] = Field(default='auto', alias='blenderImportRoute')
    blender_package: str | None = Field(default=None, alias='blenderPackage')
    blender_development_build_hash: str | None = Field(default=None, alias='blenderDevelopmentBuildHash', pattern=r'^[0-9a-f]{64}$')
    blender_export: BlenderExportConfig = Field(default_factory=BlenderExportConfig, alias='blenderExportConfig')

    export_to_blender: bool = Field(
        default=True,
        alias="exportToBlender",
        description="If True, export the processed mocap recording to a .blend file after processing.",
    )
    blender_exe_path: str | None = Field(
        default=None,
        alias="blenderExePath",
        description="Path to the Blender executable. If None, auto-detect.",
    )
    auto_open_blend_file: bool = Field(
        default=True,
        alias="autoOpenBlendFile",
        description="If True, open the .blend file in Blender after export completes.",
    )

    @model_validator(mode="after")
    def _validate_stage_range(self) -> "PosthocMocapPipelineConfig":
        if self.detector_type == "dlc":
            if self.stop_stage != "observations" or self.export_to_blender:
                raise ValueError("DLC currently supports observation-only processing; select stopStage=observations and disable Blender export, with no anatomical model association")
            if self.graph_execution_provider not in ("cpu", "cuda"):
                raise ValueError("DLC requires graphExecutionProvider=cpu or cuda (FP32)")
            if self.execution_provider not in (None, "cpu", "cuda"):
                raise ValueError("DLC executionProvider must be CPU or CUDA (FP32)")
        stages = ('observations', 'triangulation', 'filtering', 'scale_fit', 'reconstruction')
        if stages.index(self.start_stage) > stages.index(self.stop_stage):
            raise ValueError('stopStage must not precede startStage')
        return self

    @model_validator(mode="after")
    def _build_tracker_config_from_detector_type(self) -> "PosthocMocapPipelineConfig":
        from freemocap.core.tracking.tracker_factory import tracker_config_for_settings
        expected_tracker = tracker_config_for_settings(self, video_fps=self.video_fps)
        if self.tracker_config is not None and self.tracker_config != expected_tracker:
            raise ValueError("tracker_config must match the selected tracking preset settings")
        if self.tracker_config is None:
            self.tracker_config = expected_tracker
        return self
