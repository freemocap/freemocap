import { Color } from "three";

export type { Point3d } from "@/services/server/ServerContextProvider";

export interface PointStyle {
    color: Color;
    scale: number;
}
