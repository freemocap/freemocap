import {CameraMatchingOptions, defaultCameraMatchingOptions} from '@/types/camera-matching';
import type {TemporalConfig, TemporalStatus} from '@/types/temporal-config';
import {DetectorType, ExecutionProviderName, MediapipeModelComplexity, RTMPoseModelName} from "@/store/slices/mocap";

export interface CharucoBoardConfigForPipeline {
    squares_x: number;
    squares_y: number;
    square_length_mm: number;
    marker_length_ratio?: number;
    aruco_dictionary_enum?: number;
}

export type RealtimeDetectorType = DetectorType | 'rtmw_onnx_hands';

export interface CameraNodeConfig {
    charuco_tracking_enabled: boolean;
    skeleton_tracking_enabled: boolean;
    charuco_board?: CharucoBoardConfigForPipeline;
    detector_type?: RealtimeDetectorType;
    dlc_model_path?: string | null;
    dlc_geometry_path?: string | null;
    dlc_confidence_threshold?: number;
    rtmpose_model_name?: RTMPoseModelName;
    rtmpose_confidence_threshold?: number;
    mediapipe_model_complexity?: MediapipeModelComplexity;
    mediapipe_detection_confidence?: number;
    mediapipe_presence_confidence?: number;
    mediapipe_tracking_confidence?: number;
    mediapipe_num_hands?: 2;
    mediapipe_num_faces?: number;
}

export interface RealtimeSkeletonInferenceNodeConfig {
    max_batch_size?: number;
    /** null = auto-select the best available provider. */
    execution_provider?: ExecutionProviderName | null;
}

export interface RealtimeAggregatorNodeConfig {
    reference_transform: {matrix: number[]} | null;
    camera_matching: CameraMatchingOptions;
    calibration_toml_path: string | null;
    triangulation_enabled: boolean;
    realtime_filter_config?: TemporalConfig;
    anchor_segment_name: string;
    center_of_mass_enabled: boolean;
    skeleton_fitting_enabled: boolean;
}

export interface RealtimePipelineConfig {
    camera_node_config: CameraNodeConfig;
    skeleton_inference_node_config: RealtimeSkeletonInferenceNodeConfig;
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
    skeleton_inference_node_config: {
        execution_provider: null,
    },
    aggregator_config: {
        reference_transform: null,
        camera_matching: {...defaultCameraMatchingOptions},
        calibration_toml_path: null,
        triangulation_enabled: true,
        anchor_segment_name: "pelvis",
        center_of_mass_enabled: true,
        skeleton_fitting_enabled: true,
    },
};

// ==================== API Request/Response ====================

export interface PipelineApplyRequest {
    realtime_config: RealtimePipelineConfig;
}

export interface PipelineApplyResponse {
    resolved_config: RealtimePipelineConfig;
    camera_group_id: string;
    pipeline_id: string;
}

// ==================== Redux State ====================

export interface PipelineState {
    applyPending: boolean;
    applyRequestId: string | null;
    closeRequestId: string | null;
    temporalStatus: TemporalStatus | null;
    temporalLoading: boolean;
    temporalError: string | null;
    pipelineConfig: RealtimePipelineConfig;
    cameraGroupId: string | null;
    pipelineId: string | null;
    isConnected: boolean;
    isLoading: boolean;
    error: string | null;
}
