export type CalibrationSource = 'most_recent' | 'specified';

export interface CameraNodeConfig {
    charuco_tracking_enabled: boolean;
    skeleton_tracking_enabled: boolean;
}

export interface RealtimeAggregatorNodeConfig {
    calibration_toml_source: CalibrationSource;
    calibration_toml_path: string | null;
    triangulation_enabled: boolean;
    filter_enabled: boolean;
    skeleton_enabled: boolean;
}

export interface RealtimePipelineConfig {
    camera_node_config: CameraNodeConfig;
    aggregator_config: RealtimeAggregatorNodeConfig;
}

export const defaultRealtimePipelineConfig: RealtimePipelineConfig = {
    camera_node_config: {
        charuco_tracking_enabled: true,
        skeleton_tracking_enabled: true,
    },
    aggregator_config: {
        calibration_toml_source: 'most_recent',
        calibration_toml_path: null,
        triangulation_enabled: true,
        filter_enabled: false,
        skeleton_enabled: true,
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
