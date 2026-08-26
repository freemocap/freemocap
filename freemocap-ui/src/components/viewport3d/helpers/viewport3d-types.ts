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

/** Viewport layer visibility toggles. */
export interface ViewportVisibility {
    environment: boolean;
    keypoints: boolean;
    skeleton: boolean;
    face: boolean;
    connections: boolean;
    cameras: boolean;
    centerOfMass: boolean;
    centerOfMassSphere: boolean;
    centerOfMassProjection: boolean;
    centerOfMassConnection: boolean;
    centerOfMassXcom: boolean;
    centerOfMassXcomConnection: boolean;
    rigidBodyBones: boolean;
    /** Per-segment orientation triads (x/y/z axes at each segment origin). */
    segmentAxes: boolean;
}

export const DEFAULT_VISIBILITY: ViewportVisibility = {
    environment: true,
    keypoints: true,
    skeleton: true,
    face: true,
    connections: true,
    cameras: true,
    centerOfMass: true,
    centerOfMassSphere: true,
    centerOfMassProjection: true,
    centerOfMassConnection: true,
    centerOfMassXcom: true,
    centerOfMassXcomConnection: true,
    rigidBodyBones: true,
    segmentAxes: true,
};

/** Live stats from each renderer. */
export interface ViewportStats {
    keypoints: number;
    skeleton: number;
    facePoints: number;
    connections: number;
    cameras: number;
    centerOfMass: number;
}

// ---------------------------------------------------------------------------
// Inspection (hover / click-to-pin a named point or bone).
// ---------------------------------------------------------------------------

/** The three inspectable entity kinds in the 3D viewport. */
export type InspectionKind = "keypoint" | "landmark" | "segment";

/** A hovered or pinned inspectable entity. */
export interface InspectionTarget {
    kind: InspectionKind;
    name: string;
}


