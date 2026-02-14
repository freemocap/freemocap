/**
 * TypeScript types mirroring the backend FreeMoCapSettings Pydantic models.
 *
 * These represent the authoritative backend state pushed over WebSocket.
 * Field names use snake_case to match the JSON the backend sends.
 */

// ---------------------------------------------------------------------------
// Camera layer (mirrors skellycam CameraConfig + runtime status)
// ---------------------------------------------------------------------------

export interface BackendImageResolution {
    height: number;
    width: number;
}

export interface BackendCameraConfig {
    camera_id: string;
    camera_index: number;
    camera_name: string;
    use_this_camera: boolean;
    resolution: BackendImageResolution;
    color_channels: number;
    pixel_format: string;
    exposure_mode: string;
    exposure: number;
    framerate: number;
    rotation: number;
    capture_fourcc: string;
    writer_fourcc: string;
}

export type BackendCameraStatus = "disconnected" | "connected" | "error";

export interface BackendCameraState {
    config: BackendCameraConfig;
    status: BackendCameraStatus;
}

// ---------------------------------------------------------------------------
// Calibration config (mirrors CalibrationPipelineConfig)
// ---------------------------------------------------------------------------

export type CalibrationSolverMethod = "anipose" | "pyceres";

export interface BackendCalibrationConfig {
    calibration_recording_folder: string | null;
    charuco_board_x_squares: number;
    charuco_board_y_squares: number;
    charuco_square_length: number;
    solver_method: CalibrationSolverMethod;
    use_groundplane: boolean;
    pyceres_solver_config: Record<string, unknown>;
}

export interface BackendCalibrationSettings {
    config: BackendCalibrationConfig;
    is_recording: boolean;
    recording_progress: number;
    last_recording_path: string | null;
    has_calibration_toml: boolean;
}

// ---------------------------------------------------------------------------
// MoCap config (mirrors MocapPipelineConfig)
// ---------------------------------------------------------------------------

export interface BackendEstimatorConfig {
    max_samples: number;
    min_samples_for_full_confidence: number;
    iqr_confidence_sensitivity: number;
}

export interface BackendRealtimeFilterConfig {
    min_cutoff: number;
    beta: number;
    d_cutoff: number;
    fabrik_tolerance: number;
    fabrik_max_iterations: number;
    height_meters: number;
    noise_sigma: number;
    estimator_config: BackendEstimatorConfig;
    max_reprojection_error_px: number;
    max_velocity_m_per_s: number;
    max_rejected_streak: number;
}

export interface BackendMocapConfig {
    detector: Record<string, unknown>;
    skeleton_filter: BackendRealtimeFilterConfig;
}

export interface BackendMocapSettings {
    config: BackendMocapConfig;
    is_recording: boolean;
    recording_progress: number;
    last_recording_path: string | null;
}

// ---------------------------------------------------------------------------
// Pipeline config (mirrors RealtimePipelineConfig + runtime status)
// ---------------------------------------------------------------------------

export interface BackendRealtimePipelineConfig {
    camera_configs: Record<string, BackendCameraConfig>;
    calibration_config: BackendCalibrationConfig;
    mocap_config: BackendMocapConfig;
    calibration_detection_enabled: boolean;
    mocap_detection_enabled: boolean;
}

export interface BackendPipelineSettings {
    config: BackendRealtimePipelineConfig | null;
    is_connected: boolean;
    pipeline_id: string | null;
    camera_group_id: string | null;
    is_paused: boolean;
}

// ---------------------------------------------------------------------------
// Top-level settings blob
// ---------------------------------------------------------------------------

export interface FreeMoCapSettings {
    cameras: Record<string, BackendCameraState>;
    pipeline: BackendPipelineSettings;
    calibration: BackendCalibrationSettings;
    mocap: BackendMocapSettings;
}

// ---------------------------------------------------------------------------
// WebSocket message types
// ---------------------------------------------------------------------------

export interface SettingsStateMessage {
    message_type: "settings/state";
    settings: FreeMoCapSettings;
    version: number;
}

export interface SettingsPatchMessage {
    message_type: "settings/patch";
    patch: DeepPartial<FreeMoCapSettings>;
}

export interface SettingsRequestMessage {
    message_type: "settings/request";
}

export type SettingsMessage =
    | SettingsStateMessage
    | SettingsPatchMessage
    | SettingsRequestMessage;

// ---------------------------------------------------------------------------
// Utility: deep partial for patch payloads
// ---------------------------------------------------------------------------

export type DeepPartial<T> = {
    [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};
