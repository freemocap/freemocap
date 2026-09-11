import z from "zod";

// Individual tracked point — the name rides the overlay inline (self-describing).
export const SkeletonPointSchema = z.object({
    name: z.string(),
    x: z.number(),
    y: z.number(),
    z: z.number(),
    visibility: z.number(),
});

// One detection stage's bounding box in image pixel coords (xyxy) — the crop the
// keypoint detector was actually given. `name` is the stage ("body", "charuco"), and
// `fromDetector` says whether the object detector produced this box THIS frame or it
// was carried forward from the tracked keypoints. That flag is the colour key: a box
// that is green every frame means the detector is re-running every frame.
export const BoxOverlaySchema = z.object({
    name: z.string(),
    x1: z.number(),
    y1: z.number(),
    x2: z.number(),
    y2: z.number(),
    confidence: z.number(),
    fromDetector: z.boolean(),
});

// Single-camera flat overlay payload. `points` are the tracker's raw 2D
// keypoint detections (small dots); `landmarks` are the fitted skeleton's
// segment-origin landmarks projected back into the camera (larger dots), with
// `connections` = the segment parent→child name pairs to draw between them;
// `boxes` are the detector crops those points were measured inside.
export const SkeletonOverlaySchema = z.object({
    camera_id: z.string(),
    frame_number: z.number(),
    image_width: z.number(),
    image_height: z.number(),
    points: z.array(SkeletonPointSchema),
    landmarks: z.array(SkeletonPointSchema).optional(),
    connections: z.array(z.tuple([z.string(), z.string()])).optional(),
    boxes: z.array(BoxOverlaySchema).optional(),
});

export type SkeletonPoint = z.infer<typeof SkeletonPointSchema>;
export type BoxOverlay = z.infer<typeof BoxOverlaySchema>;
export type SkeletonObservation = z.infer<typeof SkeletonOverlaySchema>;
