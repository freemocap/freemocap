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

/** Rigid body pose for a single bone segment, received from Python backend. */
export interface RigidBodyPose {
    bone_key: string;
    position: [number, number, number];
    orientation: [number, number, number, number]; // (w, x, y, z)
    scale: [number, number, number];               // (sx, sy, sz)
}

/** Viewport layer visibility toggles. */
export interface ViewportVisibility {
    environment: boolean;
    keypointsRaw: boolean;
    keypointsFiltered: boolean;
    rigidBodies: boolean;
    face: boolean;
    connections: boolean;
}

export const DEFAULT_VISIBILITY: ViewportVisibility = {
    environment: true,
    keypointsRaw: true,
    keypointsFiltered: true,
    rigidBodies: true,
    face: true,
    connections: true,
};

/** Live stats from each renderer. */
export interface ViewportStats {
    keypointsRaw: number;
    keypointsFiltered: number;
    rigidBodies: number;
    facePoints: number;
    connections: number;
}
