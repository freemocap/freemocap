import {z} from 'zod';

export const OnnxPreparationSchema = z.object({
    pipeline_id: z.string(),
    status: z.enum(['unavailable', 'idle', 'queued', 'running', 'stopping', 'ready', 'activated', 'failed', 'cancelled']),
    phase: z.string(),
    elapsed_seconds: z.number().finite().nonnegative(),
    model_name: z.string().nullable(),
    message: z.string().nullable(),
    error: z.string().nullable(),
    can_prepare: z.boolean(),
    can_cancel: z.boolean(),
    requested_provider: z.string().nullable(),
    active_provider: z.string().nullable(),
});
export type OnnxPreparation = z.infer<typeof OnnxPreparationSchema>;
