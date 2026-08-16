// RigidBodyBoneInstances.ts
//
// F4 — pure, unit-testable functions that turn a StreamSchema into a per-bone
// instance map and compute the per-frame instance matrix. No THREE render loop
// here; the React component consumes these. The four FMC-SR §9 defects are
// fixed up front:
//   D5  — index segments by their SCHEMA-DECLARED NAMES, never by hierarchy
//         edges (a name→index map is built at schema time, per segment name).
//   D6  — the cross-section comes from a RADIUS parameter, independent of a
//         segment's long-axis length (a 1mm segment has the same radius as a
//         500mm one).
//   D14 — schema-time name→index resolution: every name resolves ONCE when the
//         schema arrives, never per-frame.
//   D15 — per-instance color set ONCE at schema time at build (never in the
//         hot path).

import { ChannelKind, type StreamSchema } from "@/services/server/transport/wire-types";

export type BoneSide = "left" | "right" | "center";

/** A single rigid body segment, resolved once at schema time. */
export interface BoneInstance {
    /** Stable instance-slot index into the InstancedMesh (name → index, D5/D14). */
    instanceIdx: number;
    /** The child segment's schema-declared name (the distal joint name). */
    name: string;
    /** Color side, from the segment name prefix. */
    side: BoneSide;
}

/**
 * Name→instance resolution, built ONCE at schema time (D5, D14). Maps each
 * schema-declared segment name to its stable instance slot. Because we resolve
 * by name, a change in the reported ordering of `segment_names` or
 * `segment_parents` does NOT change a bone's index — the name is the key.
 */
export type BoneNameToIndex = ReadonlyMap<string, number>;

/** Per-instance static info resolved once at schema/build time. */
export interface BoneInstanceTable {
    /** index-by-name (D5/D14) — the authoritative segment-name → slot map. */
    nameToIndex: BoneNameToIndex;
    /** name → instance index (alias for fast lookup; kept 1:1 with nameToIndex). */
    byName: ReadonlyMap<string, number>;
    /** Ordered instance descriptors (slot-stable). */
    instances: readonly BoneInstance[];
    /** name → rest length (mm), resolved ONCE at schema time (doc 11 F4 Step 3). */
    byNameLength: ReadonlyMap<string, number>;
    /** name → long-axis basis name (the segment's EXACT axis declaration;
     * body/hand = "y", face = "z"), resolved ONCE at schema time. */
    byNameLongAxis: ReadonlyMap<string, BoneLongAxis>;
    /** name → rest-frame orientation [w, x, y, z] from rest_pose.orientations:
     * the rotation mapping the segment's LOCAL frame to its world T-pose.
     * Resolved ONCE at schema time; composed before ROTATIONS_WORLD. */
    byNameRestOrientation: ReadonlyMap<string, readonly [number, number, number, number]>;
}

/** The local basis slot a segment's long axis (its EXACT axis) occupies. */
export type BoneLongAxis = "x" | "y" | "z";

/** wxyz → 3×3 rotation matrix (row-major, 9 floats). Matches skellyforge's
 * RotationQuaternion.to_rotation_matrix (Diebel 2006 eq. 125). */
function rotationMatrixFromQuaternion(q: readonly [number, number, number, number]): number[] {
    const [w, x, y, z] = q;
    return [
        1 - 2 * (y * y + z * z), 2 * (x * y - w * z),     2 * (x * z + w * y),
        2 * (x * y + w * z),     1 - 2 * (x * x + z * z), 2 * (y * z - w * x),
        2 * (x * z - w * y),     2 * (y * z + w * x),     1 - 2 * (x * x + y * y),
    ];
}

/** 3×3 matrix multiply, both row-major (9 floats each). */
function multiply3x3(a: readonly number[], b: readonly number[]): number[] {
    const out = new Array<number>(9);
    for (let row = 0; row < 3; row++) {
        for (let col = 0; col < 3; col++) {
            out[row * 3 + col] =
                a[row * 3] * b[col] + a[row * 3 + 1] * b[3 + col] + a[row * 3 + 2] * b[6 + col];
        }
    }
    return out;
}

/** The constant rotation mapping the unit geometry's +Z (long axis) onto the
 * segment's declared long-axis slot (its EXACT axis name). Row-major 3×3,
 * right-handed, determinant +1. */
function permuteMatrix(longAxis: BoneLongAxis): number[] {
    return longAxis === "z" ? [1, 0, 0, 0, 1, 0, 0, 0, 1]
        : longAxis === "y" ? [1, 0, 0, 0, 0, 1, 0, -1, 0]   // ẑ → ŷ, ŷ → -ẑ
        :                    [0, 0, 1, 0, 1, 0, -1, 0, 0];  // ẑ → x̂, x̂ → -ẑ
}

/**
 * Doc 11 F4 Step 3 — per-segment REST LENGTH, resolved ONCE at schema time.
 *
 * The long axis of each bone is scaled by the segment's *own* rest length. The
 * schema now carries that directly: ``schema.segment_lengths`` is a name → mm
 * map (built by the backend's ``from_standard_human`` with the anthropometric
 * ``length_ratio × height`` defaults on first send, then re-sent with the
 * measured values once the live estimators converge). We no longer derive
 * lengths from ``rest_pose.positions`` via a keypoint-pair axis table — the
 * lengths are first-class on the wire and stay consistent with the rest pose.
 */

/** Fallback rest length (mm) for a segment name missing from
 * ``schema.segment_lengths``. Belt-and-suspenders: the backend always emits an
 * entry per segment, so this only guards a stale/mismatched schema — it renders
 * the bone at unit span rather than NaN, never silently fabricating a length. */
export const DEFAULT_SEGMENT_LENGTH = 1.0;

/** Bone colors keyed by side (left = blue, right = red, center = green). */
export const BONE_SIDE_COLORS: Readonly<Record<BoneSide, readonly [number, number, number]>> = {
    left:   [0x44 / 255, 0x88 / 255, 0xff / 255],
    right:  [0xff / 255, 0x44 / 255, 0x44 / 255],
    center: [0x00 / 255, 0xaa / 255, 0x00 / 255],
};

/** Classify a canonical segment name by its `left_` / `right_` prefix. */
export function classifyBone(name: string): BoneSide {
    if (name.startsWith("left_")) return "left";
    if (name.startsWith("right_")) return "right";
    return "center";
}

/**
 * Rest-length per segment name, resolved ONCE at schema time (doc 11 F4 Step 3).
 *
 * Reads the lengths straight from ``schema.segment_lengths``. Each schema
 * SEGMENT_ORIGINS name maps to its schema length, falling back to
 * ``DEFAULT_SEGMENT_LENGTH`` for any name missing from the map (belt-and-
 * suspenders guard for a stale/mismatched schema — the backend always emits a
 * full map).
 */
export function buildSegmentLengths(
    schema: StreamSchema,
): ReadonlyMap<string, number> {
    const schemaLengths = schema.segment_lengths ?? {};
    const lengths = new Map<string, number>();

    for (const g of schema.channels) {
        if (g.kind === ChannelKind.SEGMENT_ORIGINS) {
            for (const name of g.names) {
                const value = schemaLengths[name];
                lengths.set(
                    name,
                    typeof value === "number" && Number.isFinite(value)
                        ? value
                        : DEFAULT_SEGMENT_LENGTH,
                );
            }
            break;
        }
    }
    return lengths;
}

/**
 * Build a per-instance table from a StreamSchema's `segment_names` +
 * `segment_parents` (D5: names, not hierarchy edges, are the index key).
 *
 * Instance ordering follows `segment_names` order (stable across the stream),
 * and every entry is resolved through the schema-declared name. The returned
 * `nameToIndex` map is the single name→slot authority used in the hot path.
 *
 * This is pure: callers own the material/InstancedMesh and apply colors once
 * at schema time (D15) — never per frame.
 */
export function buildBoneInstances(schema: StreamSchema): BoneInstanceTable {
    const names: string[] = [];
    for (const g of schema.channels) {
        if (g.kind === ChannelKind.SEGMENT_ORIGINS) {
            names.push(...g.names);
            break;
        }
    }
    // No SEGMENT_ORIGINS group → an image-only schema (camera-only mode, before a
    // realtime pipeline is live — the producer model legitimately emits these).
    // There are no segments to build: return an EMPTY table so the renderer draws
    // no bones until a reconstruction schema arrives. NOT a defect — do not throw
    // (a throw here, during the renderer's synchronous schema-effect setup, would
    // abort before the schema subscription is wired and never recover).
    if (names.length === 0) {
        return {
            nameToIndex: new Map(),
            byName: new Map(),
            instances: [],
            byNameLength: new Map(),
            byNameLongAxis: new Map(),
            byNameRestOrientation: new Map(),
        };
    }

    // Every segment's long-axis basis must be declared on the schema — the
    // unit bone geometry is oriented onto it. A missing map (or a missing
    // name) is a schema defect, not a renderer default.
    const schemaAxes = schema.segment_axes;
    if (!schemaAxes) {
        throw new Error("buildBoneInstances: schema declares no segment_axes — bone geometry has no long axis to orient onto");
    }
    const byNameLongAxis = new Map<string, BoneLongAxis>();
    for (const name of names) {
        const axis = schemaAxes[name];
        if (axis !== "x" && axis !== "y" && axis !== "z") {
            throw new Error(`buildBoneInstances: segment ${name} declares no valid long axis (got ${String(axis)})`);
        }
        byNameLongAxis.set(name, axis);
    }

    // Per-segment rest-frame orientation (rest_pose.orientations): the rotation
    // mapping the segment's LOCAL frame to its world T-pose. Without it the
    // world quaternions (measured relative to the rest frame) cannot be
    // applied to the unit geometry — a schema with segments but no rest
    // orientations is a defect, not a renderer default.
    const restOrientations = schema.rest_pose?.orientations;
    if (!restOrientations) {
        throw new Error("buildBoneInstances: schema declares no rest_pose.orientations — bone geometry has no rest frame to orient onto");
    }
    const byNameRestOrientation = new Map<string, readonly [number, number, number, number]>();
    for (const name of names) {
        const q = restOrientations[name];
        if (!q || q.length !== 4) {
            throw new Error(`buildBoneInstances: segment ${name} has no rest orientation (got ${JSON.stringify(q)})`);
        }
        byNameRestOrientation.set(name, q as [number, number, number, number]);
    }

    // D5: every bone index resolves via the name — segment_parents (the
    // topology) is NOT used for index assignment.
    const nameToIndex = new Map<string, number>();
    const byName = new Map<string, number>();
    const instances: BoneInstance[] = [];

    names.forEach((name, i) => {
        nameToIndex.set(name, i);
        byName.set(name, i);
        instances.push({ instanceIdx: i, name, side: classifyBone(name) });
    });

    const byNameLength = buildSegmentLengths(schema);

    return { nameToIndex, byName, instances, byNameLength, byNameLongAxis, byNameRestOrientation };
}

/**
 * Per-frame instance transform (pure — the only per-frame math, unit-tested).
 *
 * Computes a 4×4 column-major matrix placing a unit-length (+Z) geometry at
 * origin, oriented by the world quaternion, with its long axis mapped onto the
 * segment's declared long-axis slot and scaled to length (transverse axes by
 * the radius-independent crossSection — D6).
 *
 * Composition: world = R_world · R_rest · Q · S, where
 *   Q        permuteMatrix(longAxis) — geometry +Z onto the long-axis slot,
 *   R_rest   rotationMatrixFromQuaternion(restOrientation) — the segment's
 *            LOCAL frame to its world T-pose (rest_pose.orientations),
 *   R_world  rotationMatrixFromQuaternion(quatWXYZ) — world-rest → world-live
 *            (ROTATIONS_WORLD).
 * At T-pose R_world is identity, so geometry +Z lands on the segment's rest
 * long axis (a spine's +Y → world +Z, up) — the fix for the ~90° mis-orientation.
 *
 * @param origin          proximal joint (segment origin), mm
 * @param quatWXYZ        world-frame quaternion [w, x, y, z] (ROTATIONS_WORLD)
 * @param restOrientation per-segment rest-frame orientation [w, x, y, z]
 *                        (rest_pose.orientations): local frame → world T-pose
 * @param longAxis        the segment's EXACT axis basis name ("x" | "y" | "z")
 * @param length          segment long-axis length; NaN/0 hides the instance
 * @param crossSection    transverse radius (mm) — same for 1 mm and 500 mm bones
 * @returns a 16-float column-major matrix, or null when the segment is hidden
 */
export function computeBoneMatrix(
    origin: readonly [number, number, number],
    quatWXYZ: readonly [number, number, number, number],
    restOrientation: readonly [number, number, number, number],
    longAxis: BoneLongAxis,
    length: number,
    crossSection: number,
): number[] | null {
    if (!Number.isFinite(length) || length <= 0) return null;
    for (let i = 0; i < 3; i++) if (!Number.isFinite(origin[i])) return null;
    for (let i = 0; i < 4; i++) if (!Number.isFinite(quatWXYZ[i])) return null;
    for (let i = 0; i < 4; i++) if (!Number.isFinite(restOrientation[i])) return null;

    const R = rotationMatrixFromQuaternion(quatWXYZ);        // world-rest → world-live
    const Rrest = rotationMatrixFromQuaternion(restOrientation); // local → world T-pose
    const Q = permuteMatrix(longAxis);                       // geometry +Z → long-axis slot
    const Rtotal = multiply3x3(R, multiply3x3(Rrest, Q));    // geometry → world-live

    // Column-major storage: m[col*4 + row] = (Rtotal · S)[row][col] =
    // Rtotal[row][col] * s_col, since S is diagonal (scale applies to the
    // GEOMETRY's axes: geometry z = long axis → length).
    const m = new Array<number>(16);
    for (let col = 0; col < 3; col++) {
        const s = col === 0 ? crossSection : col === 1 ? crossSection : length;
        m[col * 4 + 0] = Rtotal[col] * s;
        m[col * 4 + 1] = Rtotal[3 + col] * s;
        m[col * 4 + 2] = Rtotal[6 + col] * s;
        m[col * 4 + 3] = 0;
    }
    // column 3 (translation)
    m[12] = origin[0]; m[13] = origin[1]; m[14] = origin[2]; m[15] = 1;

    return m;
}
