import z from "zod";

// Individual tracked point (name matches an entry in the active tracker's schema)
export const SkeletonPointSchema = z.object({
    name: z.string(),
    x: z.number(),
    y: z.number(),
    z: z.number(),
    visibility: z.number(),
});

// Single-camera flat overlay payload. `points` are the tracker's raw 2D
// keypoint detections (small dots); `landmarks` are the fitted skeleton's
// segment-origin landmarks projected back into the camera (larger dots), with
// `connections` = the segment parent→child name pairs to draw between them.
export const SkeletonOverlaySchema = z.object({
    message_type: z.literal("skeleton_overlay"),
    camera_id: z.string(),
    frame_number: z.number(),
    tracker_id: z.string(),
    image_width: z.number(),
    image_height: z.number(),
    points: z.array(SkeletonPointSchema),
    landmarks: z.array(SkeletonPointSchema).optional(),
    connections: z.array(z.tuple([z.string(), z.string()])).optional(),
    // Debug: person bounding box in image pixel coords (xyxy). NaN = absent.
    bbox_x1: z.number().optional(),
    bbox_y1: z.number().optional(),
    bbox_x2: z.number().optional(),
    bbox_y2: z.number().optional(),
    bbox_from_detector: z.boolean().optional(),
});

// Multi-camera message shape (matches CharucoOverlayDataMessage structure)
export const SkeletonOverlayDataMessageSchema = z.record(z.string(), SkeletonOverlaySchema);

export type SkeletonPoint = z.infer<typeof SkeletonPointSchema>;
export type SkeletonObservation = z.infer<typeof SkeletonOverlaySchema>;
export type SkeletonOverlayDataMessage = z.infer<typeof SkeletonOverlayDataMessageSchema>;
