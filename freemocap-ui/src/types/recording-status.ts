export interface FileStatus {
    name: string;
    path: string | null;
    exists: boolean;
    size_bytes: number | null;
    modified_timestamp: string | null;
}

export interface StageStatus {
    name: string;
    complete: boolean;
    present_count: number;
    total_count: number;
    files: FileStatus[];
}

export interface RecordingStatus {
    has_blend_file: boolean;
    blend_file_path: string | null;
    has_annotated_videos: boolean;
    annotated_videos_path: string | null;
    blender_export_ready: boolean;
    missing_blender_inputs: string[];
    stages: StageStatus[];
    synchronized_video_count: number;
    annotated_video_count: number;
    calibration_toml_path: string | null;
    has_calibration_toml: boolean;
}

export interface RecordingStatusSummary {
    blender_export_ready: boolean;
    has_blend_file: boolean;
    has_annotated_videos: boolean;
    has_calibration_toml: boolean;
    stages_complete: number;
    stages_total: number;
}
