import { z } from "zod";

export const FrontendFramePayloadSchema = z.object({
    type: z.literal('FrontendFramePayload'),
    jpeg_images: z.record(z.string().nullable()), // Allow dictionary-like structure
    camera_configs: z.record(z.any()), // Allow any shape for camera_configs
    multi_frame_metadata: z.any(), // Allow any value for multi_frame_metadata
    utc_ns_to_perf_ns: z.any(), // Allow any value for utc_ns_to_perf_ns
    multi_frame_number: z.number().int().default(0),
    latest_pipeline_output: z.record(z.string().nullable()), // Allow dictionary-like structure
});
