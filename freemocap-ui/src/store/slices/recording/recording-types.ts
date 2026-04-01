import {z} from 'zod';

export const RecordingConfigSchema = z.object({
    // Recording behavior settings
    useDelayStart: z.boolean(),
    delaySeconds: z.number(),

    // Naming settings
    useTimestamp: z.boolean(),
    useIncrement: z.boolean(),
    currentIncrement: z.number(),
    baseName: z.string(),
    recordingTag: z.string(),

    // Folder settings
    createSubfolder: z.boolean(),
    customSubfolderName: z.string(),
});
const StatsSummarySchema = z.object({
    median: z.number(),
    mean: z.number(),
    std: z.number(),
    min: z.number(),
    max: z.number(),
});

export type StatsSummary = z.infer<typeof StatsSummarySchema>;

export const StopRecordingResponseSchema = z.object({
    recording_name: z.string(),
    recording_path: z.string(),
    number_of_cameras: z.number(),
    number_of_frames: z.number(),
    total_duration_sec: z.number(),
    mean_framerate: z.number(),
    mean_inter_camera_sync_ms: z.number(),
    framerate_stats: StatsSummarySchema,
    frame_duration_stats: StatsSummarySchema,
    inter_camera_grab_range_ms_stats: StatsSummarySchema,
});

export type RecordingCompletionData = z.infer<typeof StopRecordingResponseSchema>;

export const ComputedRecordingPathSchema = z.object({
    recordingName: z.string(),
    subfolderName: z.string(),
    fullRecordingPath: z.string(),
});

export const RecordingInfoSchema = z.object({
    isRecording: z.boolean(),
    recordingDirectory: z.string(),
    recordingName: z.string().nullable(),
    startedAt: z.string().nullable(),
    duration: z.number().nullable(),
    config: RecordingConfigSchema,
    computed: ComputedRecordingPathSchema,
    completionData: StopRecordingResponseSchema.nullable(),
});

export type RecordingConfig = z.infer<typeof RecordingConfigSchema>;
export type ComputedRecordingPath = z.infer<typeof ComputedRecordingPathSchema>;
export type RecordingInfo = z.infer<typeof RecordingInfoSchema>;
