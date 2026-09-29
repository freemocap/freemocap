import {z} from 'zod';

// The saved Forge model, consumed in its original form. No replacement geometry
// is inferred from the current live model or reconstructed from bone names.
const Vec3 = z.tuple([z.number(), z.number(), z.number()]);
export const FittedSkeletonSchema = z.object({
    model_id: z.string(), sensor_group: z.string(),
    geometry: z.object({
        names: z.array(z.string()), parents: z.array(z.number().int()),
        display_names: z.array(z.array(z.string())), display: z.array(z.array(Vec3)),
        references: z.array(z.number()), attachments: z.array(Vec3),
    }).passthrough(),
    converged: z.boolean(), report: z.string(),
}).passthrough();
export type FittedSkeleton = z.infer<typeof FittedSkeletonSchema>;
export interface FittedSkeletonDefinition {source: string; definition: FittedSkeleton}
export interface FittedSkeletonFrame {
    source: string;
    origins: Float32Array;
    quaternions: Float32Array;
    /** Actual axial lengths; zero for segments whose reference is not axial. */
    lengths: Float32Array;
    /** Invalid samples are hidden independently; never replaced with invented poses. */
    validSegments: Uint8Array;
}
