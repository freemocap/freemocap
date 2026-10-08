import {Color} from "three";

/** 3D point with x, y, z coordinates */
export interface Point3d {
    x: number;
    y: number;
    z: number;
}

export interface PointStyle {
    color: Color;
    scale: number;
}

/** Viewport layer visibility toggles. One key per toggle in the viewport panel. */
export interface ViewportVisibility {
    /** Solid rigid-body segments of the tracked model, colored by body side. */
    bones: boolean;
    /** Thin lines joining parent → child segment origins. */
    boneLines: boolean;
    /** Anatomical points on the tracked model. */
    landmarks: boolean;
    /** Per-segment x/y/z orientation triads. */
    segmentAxes: boolean;
    /** Face contour lines. */
    face: boolean;
    /** Triangulated 3D detector output, before model fitting. */
    rawKeypoints: boolean;
    /** Detector keypoints placed under the model's landmark names. */
    mappedKeypoints: boolean;
    /** Master switch for every center-of-mass element below. */
    centerOfMass: boolean;
    comMarker: boolean;
    comFloorPoint: boolean;
    comDropLine: boolean;
    xcom: boolean;
    xcomLine: boolean;
    /** Floor grid and origin axes. */
    floorGrid: boolean;
    /** Calibrated camera bodies and frustums. */
    cameras: boolean;
}

export type LayerKey = keyof ViewportVisibility;

export const DEFAULT_VISIBILITY: ViewportVisibility = {
    bones: true,
    boneLines: true,
    landmarks: true,
    segmentAxes: true,
    face: true,
    rawKeypoints: true,
    mappedKeypoints: true,
    centerOfMass: true,
    comMarker: true,
    comFloorPoint: true,
    comDropLine: true,
    xcom: true,
    xcomLine: true,
    floorGrid: true,
    cameras: true,
};

/** Live per-layer item counts, written by the renderers, shown in the viewport panel. */
export interface ViewportStats {
    rawKeypoints: number;
    landmarks: number;
    mappedKeypoints: number;
    face: number;
    boneLines: number;
    cameras: number;
    centerOfMass: number;
}

export type CountedLayerKey = keyof ViewportStats;

export const EMPTY_STATS: ViewportStats = {
    rawKeypoints: 0,
    landmarks: 0,
    mappedKeypoints: 0,
    face: 0,
    boneLines: 0,
    cameras: 0,
    centerOfMass: 0,
};

// ---------------------------------------------------------------------------
// Inspection (hover / click-to-pin a named point or bone).
// ---------------------------------------------------------------------------

/** The three inspectable entity kinds in the 3D viewport. */
export type InspectionKind = "keypoint" | "mapped keypoint" | "landmark" | "segment";

/** A hovered or pinned inspectable entity. */
export interface InspectionTarget {
    kind: InspectionKind;
    name: string;
}


