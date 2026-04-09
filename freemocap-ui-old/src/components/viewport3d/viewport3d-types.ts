import {Color} from "three";

export type { Point3d } from "@/services/server/ServerContextProvider";

export interface PointStyle {
    color: Color;
    scale: number;
}

/** Rigid body pose for a single bone segment, received from Python backend. */
export interface RigidBodyPose {
    bone_key: string;
    position: [number, number, number];       // (x, y, z) origin at parent joint
    orientation: [number, number, number, number]; // (w, x, y, z) quaternion
    length: number;                            // meters
}
