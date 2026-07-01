import {Color} from "three";

/** 3D point with x, y, z coordinates */
export interface Point3d {
    x: number;
    y: number;
    z: number;
}

/** Per-frame centroidal-kinematics bundle (mirrors backend BodyKinematicsState). */
export interface BodyKinematics {
    center_of_mass: Point3d;
    com_velocity: Point3d | null;
    center_of_pressure: Point3d | null;
    xcom: Point3d | null;
    cmp: Point3d | null;
    ellipsoid_semi_axes: Point3d | null;
    ellipsoid_axis_x: Point3d | null;
    ellipsoid_axis_y: Point3d | null;
    ellipsoid_axis_z: Point3d | null;
    cop_is_estimated: boolean;
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
    bodyKinematics: boolean;
    reactionMassEllipsoid: boolean;
    centroidalMomentPivot: boolean;
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
    bodyKinematics: true,
    reactionMassEllipsoid: true,
    centroidalMomentPivot: true,
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
