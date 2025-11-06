import { z } from 'zod';

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
});

export type RecordingConfig = z.infer<typeof RecordingConfigSchema>;
export type ComputedRecordingPath = z.infer<typeof ComputedRecordingPathSchema>;
export type RecordingInfo = z.infer<typeof RecordingInfoSchema>;
