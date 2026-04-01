import z from "zod";

// Individual point schema
export const MediapipePointSchema = z.object({
    name: z.string(),
    x: z.number(),
    y: z.number(),
    z: z.number(),
    visibility: z.number(),
});

// Metadata schema
export const MediapipeMetadataSchema = z.object({
    n_body_detected: z.number(),
    n_right_hand_detected: z.number(),
    n_left_hand_detected: z.number(),
    n_face_detected: z.number(),
    image_width: z.number(),
    image_height: z.number(),
});

// Single camera observation schema
export const MediapipeOverlaySchema = z.object({
    message_type: z.literal("mediapipe_overlay"),
    camera_id: z.string(),
    frame_number: z.number(),
    body_points: z.array(MediapipePointSchema),
    right_hand_points: z.array(MediapipePointSchema),
    left_hand_points: z.array(MediapipePointSchema),
    face_points: z.array(MediapipePointSchema),
    metadata: MediapipeMetadataSchema,
});

// Multi-camera message schema (matches CharucoOverlayDataMessage structure)
export const MediapipeOverlayDataMessageSchema = z.record(z.string(), MediapipeOverlaySchema);

// Type exports
export type MediapipePoint = z.infer<typeof MediapipePointSchema>;
export type MediapipeMetadata = z.infer<typeof MediapipeMetadataSchema>;
export type MediapipeObservation = z.infer<typeof MediapipeOverlaySchema>;
export type MediapipeOverlayDataMessage = z.infer<typeof MediapipeOverlayDataMessageSchema>;
