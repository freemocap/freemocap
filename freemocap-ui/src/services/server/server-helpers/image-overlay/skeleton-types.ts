import z from "zod";

// Individual tracked point (name matches an entry in the active tracker's schema)
export const SkeletonPointSchema = z.object({
    name: z.string(),
    x: z.number(),
    y: z.number(),
    z: z.number(),
    visibility: z.number(),
});

// Single-camera flat overlay payload. Shape is tracker-agnostic — the frontend
// looks up connections/styling by name against the `TrackedObjectDefinition`
// whose id is `tracker_id`.
export const SkeletonOverlaySchema = z.object({
    message_type: z.literal("skeleton_overlay"),
    camera_id: z.string(),
    frame_number: z.number(),
    tracker_id: z.string(),
    image_width: z.number(),
    image_height: z.number(),
    points: z.array(SkeletonPointSchema),
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
