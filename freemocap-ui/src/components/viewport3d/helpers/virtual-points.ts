// virtual-points.ts
//
// Resolution of connection-schema endpoint names to 3D positions. The re-authored
// SkellyForge hydrates every landmark (and every segment origin) directly, so the
// normal path is a plain map lookup. The two legacy derived points below are kept
// only so a stale connection schema that still names them can keep rendering until
// it is regenerated against the new standard-human landmark names.

import type { Point3d } from "./viewport3d-types";

/**
 * Resolve a connection endpoint name to its position.
 *
 * Direct map lookup first; neck_center / hips_center (legacy derived points)
 * fall back to the midpoint of their source keypoints. Returns undefined when the
 * name is neither present nor one of the legacy derived points.
 */
export function resolvePoint(
    points: ReadonlyMap<string, Point3d>,
    name: string,
    _schema?: unknown,
): Point3d | undefined {
    const direct = points.get(name);
    if (direct) return direct;
    if (name === "neck_center") {
        return midpoint(points, "left_shoulder", "right_shoulder");
    }
    if (name === "hips_center") {
        return midpoint(points, "left_hip", "right_hip");
    }
    return undefined;
}

function midpoint(
    points: ReadonlyMap<string, Point3d>,
    a: string,
    b: string,
): Point3d | undefined {
    const pa = points.get(a);
    const pb = points.get(b);
    if (!pa || !pb) return undefined;
    return { x: (pa.x + pb.x) / 2, y: (pa.y + pb.y) / 2, z: (pa.z + pb.z) / 2 };
}
