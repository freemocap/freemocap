from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from skellytracker.core import DetectionStageConfig, TrackerConfig
from skellytracker.core.detectors.keypoint_detectors.mediapipe.body.mediapipe_pose_detector import (
    MediapipePoseDetectorConfig,
)
from skellytracker.core.detectors.keypoint_detectors.mediapipe.face.mediapipe_face_detector import (
    MediapipeFaceDetectorConfig,
)
from skellytracker.core.detectors.keypoint_detectors.mediapipe.hands.mediapipe_hand_detector import (
    MediapipeHandDetectorConfig,
)
from skellytracker.core.detectors.keypoint_detectors.mediapipe.mediapipe_model_manager import (
    MediapipePoseModelComplexity,
)
from skellytracker.core.detectors.keypoint_detectors.rtmpose import RTMPoseDetectorConfig
from skellytracker.core.detectors.object_detectors.yolox import YoloxPersonDetectorConfig
from skellytracker.core.temporal_processing.temporal_processing_config import (
    BBoxPolicyConfig,
    BBoxSmoothingConfig,
    KeypointsWithinBBoxRatioConfig,
)



class PosthocMocapPipelineConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    detector_type: Literal["rtmpose", "mediapipe"] = Field(
        default="rtmpose",
        alias="detectorType",
        description="Which pose detector to use: 'rtmpose' (default, more accurate) or 'mediapipe' (faster, CPU-friendly).",
    )
    # RTMPose settings
    rtmpose_model_name: Literal["rtmw-x-l_256x192", "rtmw-x-l_384x288", "rtmw-l-m_256x192"] = Field(
        default="rtmw-x-l_256x192",
        alias="rtmPoseModelName",
        description="RTMPose wholebody model variant. Only used when detector_type='rtmpose'.",
    )
    rtmpose_confidence_threshold: float = Field(
        default=0.004,
        alias="rtmPoseConfidenceThreshold",
        ge=0.0,
        le=1.0,
        description="Keypoint confidence threshold for RTMPose. Only used when detector_type='rtmpose'.",
    )
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
    mediapipe_num_hands: int = Field(
        default=2,
        alias="mediapipeNumHands",
        ge=1,
        le=4,
        description="Number of hands to detect. Only used when detector_type='mediapipe'.",
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
        description="Path to calibration TOML. If None, the most-recent successful calibration is used.",
    )
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
    def _build_tracker_config_from_detector_type(self) -> "PosthocMocapPipelineConfig":
        if self.detector_type == "mediapipe":
            self.tracker_config = TrackerConfig(
                stages=[
                    DetectionStageConfig(
                        name="body",
                        keypoint_detectors=[
                            MediapipePoseDetectorConfig(
                                model_complexity=self.mediapipe_model_complexity,
                                num_poses=1,
                                min_pose_detection_confidence=self.mediapipe_detection_confidence,
                                min_pose_presence_confidence=self.mediapipe_presence_confidence,
                                min_pose_tracking_confidence=self.mediapipe_tracking_confidence,
                            ),
                            MediapipeHandDetectorConfig(
                                num_hands=self.mediapipe_num_hands,
                                min_hand_detection_confidence=self.mediapipe_detection_confidence,
                                min_hand_presence_confidence=self.mediapipe_presence_confidence,
                                min_hand_tracking_confidence=self.mediapipe_tracking_confidence,
                            ),
                            MediapipeFaceDetectorConfig(
                                num_faces=self.mediapipe_num_faces,
                                min_face_detection_confidence=self.mediapipe_detection_confidence,
                                min_face_presence_confidence=self.mediapipe_presence_confidence,
                                min_face_tracking_confidence=self.mediapipe_tracking_confidence,
                            ),
                        ],
                    )
                ]
            )
        else:
            redetect_interval = max(1, round(5.0 * self.video_fps))
            self.tracker_config = TrackerConfig(
                stages=[
                    DetectionStageConfig(
                        name="body",
                        object_detector=YoloxPersonDetectorConfig(),
                        keypoint_detectors=[
                            RTMPoseDetectorConfig(
                                model_name=self.rtmpose_model_name,
                                confidence_threshold=self.rtmpose_confidence_threshold,
                            )
                        ],
                        bbox_policy=BBoxPolicyConfig(
                            redetect_interval=redetect_interval,
                            keypoint_bbox_expansion=0.05,
                            fitness_checks=[KeypointsWithinBBoxRatioConfig(threshold=0.5)],
                            min_shrink_ratio_per_frame=0.995,
                            min_bbox_size_px=80.0,
                        ),
                        bbox_smoothing=BBoxSmoothingConfig(alpha=0.4),
                    )
                ]
            )
        return self
