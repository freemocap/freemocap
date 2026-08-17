// transport/frame-types.ts
//
// Resolved (post-decode) frame shapes: what the dispatcher produces from one
// decoded FrameMessage and hands to the frame subscribers. These are NOT wire
// types — the wire types live in message-contract.ts. A channel whose rows are
// index-keyed on the wire is resolved here against the frame's own model, so the
// names arrays below are in the model's ordered segment order.

export interface PointsFrame {
    names: readonly string[];
    /** interleaved [x0,y0,z0, x1,y1,z1, …] — length names.length * 3. */
    data: Float32Array;
}

export interface RotationsFrame {
    boneNames: readonly string[];
    /** interleaved wxyz — length boneNames.length * 4. */
    worldQuaternions: Float32Array;
    localQuaternions: Float32Array;
}

export interface SegmentLengthsFrame {
    names: readonly string[];
    /** one length_mm per segment — length names.length. */
    data: Float32Array;
}

export interface DerivedPointsFrame {
    centerOfMass: [number, number, number] | null;
    xcom: [number, number, number] | null;
}

export enum OverlayLayer {
    DETECTIONS = 0,
    REPROJECTIONS = 1,
}

export interface OverlayFrame {
    cameraId: string;
    layer: OverlayLayer;
    frameNumber: number;
    names: readonly string[];
    /** interleaved [x,y,visibility, …] — length names.length * 3. */
    data: Float32Array;
}

/** Rolling-window channel keys accepted by TransportService.getRollingWindow. */
export type RollingChannelName =
    | "keypoints"
    | "segment_origins"
    | "rotations_world"
    | "derived_points";
