import {Point3d} from "@/components/viewport3d/helpers/viewport3d-types";
import {TrackedObjectDefinition} from "@/services/server/server-helpers/tracked-object-definition";

/**
 * Virtual points — schema-driven midpoints synthesized from named landmarks.
 *
 * A virtual-point spec lists the names whose average produces the virtual
 * point's coordinates. Specs are keyed by `landmark_schema` so different
 * trackers can declare their own synthesized points without touching
 * rendering code. `resolvePoint` falls back cleanly when a virtual point
 * isn't defined for the active schema.
 */

type VirtualPointSpec = Record<string, string[]>;

// Key the specs on both the schema `name` and the broader `landmark_schema`
// descriptor — whichever matches first wins in `resolvePoint`.
const VIRTUAL_POINT_SPECS: Record<string, VirtualPointSpec> = {
    rtmpose_wholebody: {
        head_center: ['left_ear', 'right_ear'],
        neck_center: ['left_shoulder', 'right_shoulder'],
        hips_center: ['left_hip', 'right_hip'],
    },
    rtmpose_body: {
        head_center: ['left_ear', 'right_ear'],
        neck_center: ['left_shoulder', 'right_shoulder'],
        hips_center: ['left_hip', 'right_hip'],
    },
    // Legacy MediaPipe-style schemas
    mediapipe_body: {
        head_center: ['body.left_ear', 'body.right_ear'],
        neck_center: ['body.left_shoulder', 'body.right_shoulder'],
        hips_center: ['body.left_hip', 'body.right_hip'],
    },
};

function specForSchema(schema: TrackedObjectDefinition | null | undefined): VirtualPointSpec | null {
    if (!schema) return null;
    return (
        VIRTUAL_POINT_SPECS[schema.name] ??
        VIRTUAL_POINT_SPECS[schema.landmark_schema] ??
        null
    );
}

/**
 * Resolve a point name to a 3D position. Real tracked points are looked up
 * directly; virtual midpoint names (`head_center`, `neck_center`, etc.) are
 * computed from the active schema's virtual-point spec. Missing source
 * points yield `null`.
 */
export function resolvePoint(
    points: Map<string, Point3d>,
    name: string,
    schema?: TrackedObjectDefinition | null,
): Point3d | null {
    const direct = points.get(name);
    if (direct) return direct;

    const spec = specForSchema(schema);
    if (!spec) return null;

    const sources = spec[name];
    if (!sources) return null;

    let x = 0, y = 0, z = 0;
    for (const src of sources) {
        const p = points.get(src);
        if (!p) return null;
        x += p.x;
        y += p.y;
        z += p.z;
    }
    const n = sources.length;
    return {x: x / n, y: y / n, z: z / n};
}
