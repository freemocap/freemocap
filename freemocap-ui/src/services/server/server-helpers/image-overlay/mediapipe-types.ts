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
});

// Multi-camera message shape (matches CharucoOverlayDataMessage structure)
export const SkeletonOverlayDataMessageSchema = z.record(z.string(), SkeletonOverlaySchema);

// Type exports — names kept as "Mediapipe*" to minimize churn in callers that
// haven't been renamed yet. These are now tracker-agnostic.
export type MediapipePoint = z.infer<typeof SkeletonPointSchema>;
export type MediapipeObservation = z.infer<typeof SkeletonOverlaySchema>;
export type MediapipeOverlayDataMessage = z.infer<typeof SkeletonOverlayDataMessageSchema>;

// New preferred names for downstream code
export type SkeletonPoint = MediapipePoint;
export type SkeletonObservation = MediapipeObservation;
export const MediapipePointSchema = SkeletonPointSchema;
export const MediapipeOverlaySchema = SkeletonOverlaySchema;
export const MediapipeOverlayDataMessageSchema = SkeletonOverlayDataMessageSchema;
