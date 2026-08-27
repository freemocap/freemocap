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

/** One model's fitted size this frame: the whole thing, and every segment of it.
 *
 *  A model is dimensionless, so this is where millimetres come from. Every segment has a
 *  length whether or not it was visible — a segment nobody could see is sized by
 *  `fittedScaleMm`, which is what lets the feet stay the right length under a desk. */
export interface SegmentLengthsFrame {
    names: readonly string[];
    /** one fitted length_mm per segment — length names.length. */
    data: Float32Array;
    /** this model's fitted size (mm) in the unit it names, or null if unmeasured. */
    fittedScaleMm: number | null;
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
    /** Which model these rows belong to. Set on REPROJECTIONS (they are one model's
     *  segment origins); absent on DETECTIONS, which are raw per-detector measurements
     *  not yet attributed to a reconstruction. */
    modelId?: string;
    frameNumber: number;
    names: readonly string[];
    /** interleaved [x,y,visibility, …] — length names.length * 3. */
    data: Float32Array;
    /** Full-resolution (rotated) image size this overlay is in, when the wire
     *  carries it on the channel (independent of calibration). */
    imageSize?: [number, number];
}


/** Everything one tracked model looks like THIS FRAME.
 *
 *  A frame carries several — a tracked person and a tracked charuco board are two — so
 *  consumers iterate these rather than reading "the" skeleton. Every row here is named
 *  against THIS model's own symbol tables, never another's.
 *
 *  Deliberately does NOT carry the `ModelDefinition`: that is static between
 *  `model_sequence` bumps and travels on its own change-detected channel. Inlining it here
 *  meant structured-cloning 61 segments + 124 landmarks + 60 connections across the Web
 *  Worker boundary thirty times a second, which cost most of the frame budget. Join to the
 *  definition by `modelId`.
 */
export interface ResolvedModelFrame {
    modelId: string;
    /** This occurrence's fitted size (mm) in the unit its model names, or null. */
    fittedScaleMm: number | null;
    /** Segment origins, index-keyed against the model's segments. */
    segmentOrigins: PointsFrame | null;
    /** Landmarks placed by the FIT — the reconstructed object, not the raw measurement. */
    landmarks: PointsFrame | null;
    rotations: RotationsFrame | null;
    segmentLengths: SegmentLengthsFrame | null;
    derived: DerivedPointsFrame;
}
