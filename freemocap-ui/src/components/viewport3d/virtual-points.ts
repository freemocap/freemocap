import { Point3d } from "@/components/viewport3d/viewport3d-types";

/**
 * Resolve a point name to a 3D position. Handles both raw landmark names
 * (looked up directly in the points map) and virtual midpoint names
 * (head_center, neck_center, hips_center) computed from paired landmarks.
 */
export function resolvePoint(points: Map<string, Point3d>, name: string): Point3d | null {
    switch (name) {
        case "head_center": {
            const l = points.get("body.left_ear");
            const r = points.get("body.right_ear");
            if (!l || !r) return null;
            return { x: (l.x + r.x) / 2, y: (l.y + r.y) / 2, z: (l.z + r.z) / 2 };
        }
        case "neck_center": {
            const l = points.get("body.left_shoulder");
            const r = points.get("body.right_shoulder");
            if (!l || !r) return null;
            return { x: (l.x + r.x) / 2, y: (l.y + r.y) / 2, z: (l.z + r.z) / 2 };
        }
        case "hips_center": {
            const l = points.get("body.left_hip");
            const r = points.get("body.right_hip");
            if (!l || !r) return null;
            return { x: (l.x + r.x) / 2, y: (l.y + r.y) / 2, z: (l.z + r.z) / 2 };
        }
        default:
            return points.get(name) ?? null;
    }
}
