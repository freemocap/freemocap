import {z} from 'zod';

export const OneEuroConfigSchema = z.object({
    enabled: z.boolean(), min_cutoff: z.number().positive(), beta: z.number().nonnegative(),
    d_cutoff: z.number().positive(),
});
export const TemporalConfigSchema = z.object({
    image_smoothing: OneEuroConfigSchema,
    spatial_smoothing: OneEuroConfigSchema,
    velocity_gate_enabled: z.boolean(),
    max_velocity_mm_per_s: z.number().positive(),
    reacquisition_timeout_s: z.number().positive(),
    gap_duration_s: z.number().min(0).max(2),
    prediction_duration_s: z.number().min(0).max(2),
    velocity_half_life_s: z.number().positive(),
    segment_retention_s: z.number().min(0).max(2),
    max_reprojection_error_px: z.number().positive(),
    segment_scale_window_frames: z.number().int().positive(),
});
export type TemporalConfig = z.infer<typeof TemporalConfigSchema>;
export type OneEuroConfig = z.infer<typeof OneEuroConfigSchema>;
export const TemporalStatusSchema = z.object({
    defaults: TemporalConfigSchema,
    requested: TemporalConfigSchema.nullable(),
    applied: TemporalConfigSchema.nullable(),
});
export type TemporalStatus = z.infer<typeof TemporalStatusSchema>;
export function sameTemporalConfig(left: TemporalConfig | null | undefined, right: TemporalConfig | null | undefined): boolean {
    if (!left || !right) return left === right;
    return JSON.stringify(TemporalConfigSchema.parse(left)) === JSON.stringify(TemporalConfigSchema.parse(right));
}
