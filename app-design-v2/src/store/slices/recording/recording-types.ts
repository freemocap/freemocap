import { z } from 'zod';

export const RecordingInfoSchema = z.object({
    isRecording: z.boolean(),
    recordingDirectory: z.string(),
    recordingName: z.string().nullable(),
    startedAt: z.string().nullable(),
    duration: z.number().nullable()
});

export type RecordingInfo = z.infer<typeof RecordingInfoSchema>;
