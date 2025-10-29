import { z } from 'zod';

// Zod schemas for CharucoObservation data
export const CharucoPointSchema = z.object({
    id: z.number(),
    x: z.number(),
    y: z.number(),
});

export const ArucoMarkerSchema = z.object({
    id: z.number(),
    corners: z.array(z.tuple([z.number(), z.number()])).length(4),
});

export const CharucoObservationSchema = z.object({
    message_type: z.literal('charuco_observation'),
    camera_id: z.string(),
    frame_number: z.number(),
    charuco_corners: z.array(CharucoPointSchema),
    aruco_markers: z.array(ArucoMarkerSchema),
    metadata: z.object({
        n_charuco_detected: z.number(),
        n_charuco_total: z.number(),
        n_aruco_detected: z.number(),
        n_aruco_total: z.number(),
        has_pose: z.boolean(),
        image_width: z.number(),
        image_height: z.number(),
    }),
});

export type CharucoPoint = z.infer<typeof CharucoPointSchema>;
export type ArucoMarker = z.infer<typeof ArucoMarkerSchema>;
export type CharucoObservation = z.infer<typeof CharucoObservationSchema>;
