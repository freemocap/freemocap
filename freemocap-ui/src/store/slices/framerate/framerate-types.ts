// framerate-types.ts
import {z} from 'zod';

// The actual framerate data structure used in the Redux store
export const FramerateDataSchema = z.object({
    mean: z.number(),
    std: z.number(),
    current: z.number(),
});

export type FramerateData = z.infer<typeof FramerateDataSchema>;

// If you have a different schema from the backend with more detailed stats,
// you can keep it separate for parsing/validation but transform it to FramerateData
export const DetailedFramerateSchema = z.object({
    mean_frame_duration_ms: z.number(),
    mean_frames_per_second: z.number(),
    frame_duration_max: z.number(),
    frame_duration_min: z.number(),
    frame_duration_mean: z.number(),
    frame_duration_stddev: z.number(),
    frame_duration_median: z.number(),
    frame_duration_coefficient_of_variation: z.number(),
    calculation_window_size: z.number(),
    framerate_source: z.string(),
});

export type DetailedFramerate = z.infer<typeof DetailedFramerateSchema>;

// Helper function to convert detailed framerate to simple framerate data
export function detailedToSimpleFramerate(detailed: DetailedFramerate): FramerateData {
    return {
        mean: detailed.mean_frames_per_second,
        std: detailed.frame_duration_stddev,
        current: detailed.mean_frames_per_second, // or calculate from mean_frame_duration_ms
    };
}
