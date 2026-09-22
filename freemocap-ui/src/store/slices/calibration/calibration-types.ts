import {z} from 'zod';
import {
    CalibratedCameraSchema,
    CameraExtrinsicsSchema,
    CameraIntrinsicsSchema,
} from '@/services/server/transport/message-contract';

export enum CalibrationBoardMode { AUTO = "auto", EXPLICIT = "explicit" }

export const CalibrationSolverMethodSchema = z.enum(['anipose']);
export type CalibrationSolverMethod = z.infer<typeof CalibrationSolverMethodSchema>;

export const CALIBRATION_SOLVER_LABELS: Record<CalibrationSolverMethod, string> = {
    [CalibrationSolverMethodSchema.enum.anipose]: 'Anipose',
};

export interface CharucoBoardConfig {
    squares_x: number;
    squares_y: number;
    square_length_mm: number;
}

export interface CalibrationConfig {
    boardMode: CalibrationBoardMode;
    charucoBoard: CharucoBoardConfig;
    minSharedViewsPerCamera: number;
    autoStopOnMinViewCount: boolean;
    solverMethod: CalibrationSolverMethod;
    useGroundplane: boolean;
}

export const CalibrationCameraDataSchema = CalibratedCameraSchema.pick({
    id: true,
    index: true,
    image_size: true,
    world_position: true,
    world_orientation: true,
}).extend({
    intrinsics: CameraIntrinsicsSchema,
    extrinsics: CameraExtrinsicsSchema,
    world_orientation: CalibratedCameraSchema.shape.world_orientation.length(3),
});
export type CalibrationCameraData = z.infer<typeof CalibrationCameraDataSchema>;

export const CalibrationAlignmentMethodSchema = z.enum(['charuco', 'person']);

export const CalibrationTransformTypeSchema = z.enum({
    ...CalibrationAlignmentMethodSchema.enum,
    manual: 'manual',
});
export const CalibrationTransformSchema = z.object({
    operation: CalibrationTransformTypeSchema,
    quaternion_wxyz: CameraExtrinsicsSchema.shape.quaternion_wxyz,
    translation_mm: CameraExtrinsicsSchema.shape.translation,
});
export type CalibrationTransform = z.infer<typeof CalibrationTransformSchema>;

export const CalibrationMetadataSchema = z.object({
    board: z.object({
        squares_x: z.number().int(),
        squares_y: z.number().int(),
        square_length_mm: z.number(),
        marker_length_ratio: z.number(),
        aruco_dictionary_enum: z.number().int(),
        aruco_marker_length_mm: z.number(),
    }),
    reprojection_error_px: z.number(),
    initial_cost: z.number(),
    final_cost: z.number(),
    n_iterations: z.number().int(),
    solver_time_seconds: z.number(),
    n_observations_used: z.number().int(),
    n_observations_rejected: z.number().int(),
    aligned: z.boolean(),
    solver_method: CalibrationSolverMethodSchema.nullable(),
    recording_info: z.object({
        recording_name: z.string(),
        recording_directory: z.string(),
        recording_uuid: z.string(),
        mic_device_index: z.number().int(),
        recording_start_timestamp: z.object({
            unix_timestamp_utc: z.number(),
            unix_timestamp_local: z.number(),
            unix_timestamp_utc_isoformat: z.string(),
            unix_timestamp_local_isoformat: z.string(),
            local_time_zone: z.string(),
            human_friendly_utc: z.string(),
            human_friendly_local: z.string(),
            day_of_week: z.string(),
            calendar_week: z.number().int(),
            day_of_year: z.number().int(),
            is_leap_year: z.boolean(),
            perf_counter_ns: z.number(),
        }),
    }).nullable(),
    alignment_method: CalibrationAlignmentMethodSchema.nullable(),
    alignment_recording_id: z.string().nullable(),
    alignment_result: z.object({
        origin: CalibrationCameraDataSchema.shape.world_position,
        rotation_matrix: CalibrationCameraDataSchema.shape.world_orientation,
        method: CalibrationAlignmentMethodSchema,
    }).nullable(),
    transformation_history: z.array(CalibrationTransformSchema),
});
export type CalibrationMetadata = z.infer<typeof CalibrationMetadataSchema>;

export const LoadedCalibrationSchema = z.object({
    path: z.string(),
    mtimeMs: z.number(),
    cameras: z.array(CalibrationCameraDataSchema),
    metadata: CalibrationMetadataSchema,
});
export type LoadedCalibration = z.infer<typeof LoadedCalibrationSchema>;

export const CalibrationUpdateRequestSchema = z.object({
    path: LoadedCalibrationSchema.shape.path,
    expected_mtime_ms: LoadedCalibrationSchema.shape.mtimeMs,
    transformations: z.array(CalibrationTransformSchema).min(1),
    recording_id: z.string().nullable().default(null),
}).strict();
export type CalibrationUpdateRequest = z.infer<typeof CalibrationUpdateRequestSchema>;

export const CalibrationSceneSchema = z.object({
    calibration: LoadedCalibrationSchema.nullable(),
    referenceTransform: z.array(z.number()).length(16).nullable(),
});
export type CalibrationScene = z.infer<typeof CalibrationSceneSchema>;
