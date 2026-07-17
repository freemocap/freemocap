import {DetectorType, MediapipeModelComplexity, RTMPoseModelName} from "@/store/slices/mocap";

export interface CharucoBoardConfigForPipeline {
    squares_x: number;
    squares_y: number;
    square_length_mm: number;
}

export interface CameraNodeConfig {
    charuco_tracking_enabled: boolean;
    skeleton_tracking_enabled: boolean;
    charuco_detector_config?: { board: CharucoBoardConfigForPipeline } | null;
    detector_type?: DetectorType;
    rtmpose_model_name?: RTMPoseModelName;
    rtmpose_confidence_threshold?: number;
    mediapipe_model_complexity?: MediapipeModelComplexity;
    mediapipe_detection_confidence?: number;
    mediapipe_presence_confidence?: number;
    mediapipe_tracking_confidence?: number;
    mediapipe_num_hands?: number;
    mediapipe_num_faces?: number;
}

export interface RealtimeAggregatorNodeConfig {
    calibration_toml_path: string | null;
    triangulation_enabled: boolean;
    filter_enabled: boolean;
    skeleton_enabled: boolean;
    center_of_mass_enabled: boolean;
    skeleton_fitting_enabled: boolean;
}

export interface RealtimePipelineConfig {
    camera_node_config: CameraNodeConfig;
    aggregator_config: RealtimeAggregatorNodeConfig;
}

export const defaultRealtimePipelineConfig: RealtimePipelineConfig = {
    camera_node_config: {
        charuco_tracking_enabled: true,
        skeleton_tracking_enabled: true,
        detector_type: "rtmpose",
        rtmpose_model_name: "rtmw-x-l_256x192",
        rtmpose_confidence_threshold: 0.0025,
        mediapipe_model_complexity: "lite",
        mediapipe_detection_confidence: 0.5,
        mediapipe_presence_confidence: 0.5,
        mediapipe_tracking_confidence: 0.5,
        mediapipe_num_hands: 2,
        mediapipe_num_faces: 1,
    },
    aggregator_config: {
        calibration_toml_path: null,
        triangulation_enabled: true,
        filter_enabled: false,
        skeleton_enabled: true,
        center_of_mass_enabled: true,
        skeleton_fitting_enabled: true,
    },
};

// ==================== API Request/Response ====================

export interface PipelineApplyRequest {
    realtime_config: RealtimePipelineConfig;
}

export interface PipelineApplyResponse {
    camera_group_id: string;
    pipeline_id: string;
}

// ==================== Redux State ====================

export interface PipelineState {
    pipelineConfig: RealtimePipelineConfig;
    cameraGroupId: string | null;
    pipelineId: string | null;
    isConnected: boolean;
    isLoading: boolean;
    error: string | null;
}
