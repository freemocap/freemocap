import {z} from 'zod';

/** Snapshot of the current startup operation; elapsed values are not estimates. */
export const RealtimeStartupStatusSchema = z.object({
    status: z.enum(['idle', 'running', 'stopping', 'ready', 'failed', 'stopped']),
    phase: z.string().min(1),
    elapsed_seconds: z.number().finite().nonnegative(),
    phase_elapsed_seconds: z.number().finite().nonnegative(),
    pipeline_id: z.string().nullable(),
    message: z.string().nullable(),
    error: z.string().nullable(),
    delayed: z.boolean().default(false),
    preview_ready: z.boolean().default(false),
});

export type RealtimeStartupStatus = z.infer<typeof RealtimeStartupStatusSchema>;
