// RigidBodyBoneInstances.ts
//
// Pure, unit-testable functions that turn a ModelDefinition (the model that
// rides every frame) into a per-bone instance map, and compute the per-frame
// instance matrix. No THREE render loop here; the React component consumes
// these. The four FMC-SR §9 defects are fixed up front:
//   D5  — index segments by their model-declared NAMES, never by hierarchy
//         edges (a name→index map is built once, per segment name).
//   D6  — the cross-section comes from a RADIUS parameter, independent of a
//         segment's length (a 1mm segment has the same radius as a 500mm one).
//   D14 — build-time name→index resolution: every name resolves ONCE when the
//         model arrives, never per-frame.
//   D15 — per-instance color set ONCE at build (never in the hot path).
//
// The bone's direction is its PRIMARY AXIS: the axis from the segment origin to
// its distal point (where the child connects, or the tip for a leaf). It is a
// signed basis axis ("x"/"y"/"z"/"-x"/… ) or a normalized 3-vector. There is no
// fixed slot mapping — the unit geometry's +Z is rotated onto the
// segment's actual primary-axis direction.

import type { ModelDefinition, PrimaryAxis } from "@/services/server/transport/message-contract";

export type BoneSide = "left" | "right" | "center";

export type BoneRegion = "body" | "hand" | "face" | "foot";

/** Classify a segment by name into a coarse region for cross-section sizing. */
export function classifyRegion(name: string): BoneRegion {
    const lc = name.toLowerCase();
    if (/eye|ear|nose|jaw|mouth/.test(lc)) return "face";
    if (/hand|thumb|index|middle|ring|pinky|finger/.test(lc)) return "hand";
    if (/foot|toe|metatarsal|tarsal|calcaneus|talus|navicular|cuboid|cuneiform|ankle/.test(lc)) return "foot";
    return "body";
}

/** Transverse cross-section radius (mm) per region: face < hand < body. */
export const REGION_CROSS_SECTION: Readonly<Record<BoneRegion, number>> = {
    body: 12,
    hand: 5,
    face: 3,
    foot: 5,
};

/** A single rigid body segment, resolved once at model time. */
export interface BoneInstance {
    /** Stable instance-slot index into the InstancedMesh (name → index, D5/D14). */
    instanceIdx: number;
    /** The child segment's model-declared name. */
    name: string;
    /** Color side, from the segment name prefix. */
    side: BoneSide;
}

export type BoneNameToIndex = ReadonlyMap<string, number>;

export interface BoneInstanceTable {
    /** index-by-name (D5/D14) — the authoritative segment-name → slot map. */
    nameToIndex: BoneNameToIndex;
    /** name → instance index (alias; kept 1:1 with nameToIndex). */
    byName: ReadonlyMap<string, number>;
    /** Ordered instance descriptors (slot-stable). */
    instances: readonly BoneInstance[];
    /** name → rest length as a FRACTION OF BODY HEIGHT, resolved ONCE at model time.
     *  The model is dimensionless; multiply by the frame's fitted `bodyHeightMm` for
     *  millimetres, or prefer the per-frame SEGMENT_LENGTHS channel, which carries the
     *  fitted length of every segment. */
    byNameLengthProportion: ReadonlyMap<string, number>;
    /** name → primary axis (the bone's origin→distal direction). */
    byNamePrimaryAxis: ReadonlyMap<string, PrimaryAxis>;
    /** name → rest-frame orientation [w, x, y, z]: the rotation mapping the
     *  segment's LOCAL frame to its world T-pose. Composed before ROTATIONS_WORLD. */
    byNameRestOrientation: ReadonlyMap<string, readonly [number, number, number, number]>;
    /** name → transverse cross-section radius (mm), sized by region. */
    byNameCrossSection: ReadonlyMap<string, number>;
}

/** Fallback rest length (mm) for a segment whose size is not known at all — no fitted
 *  length on the wire and no body height to scale its proportion by. */
export const DEFAULT_SEGMENT_LENGTH = 1.0;

/** Bone colors keyed by side (left = blue, right = red, center = green). */
export const BONE_SIDE_COLORS: Readonly<Record<BoneSide, readonly [number, number, number]>> = {
    left:   [0x44 / 255, 0x88 / 255, 0xff / 255],
    right:  [0xff / 255, 0x44 / 255, 0x44 / 255],
    center: [0x00 / 255, 0xaa / 255, 0x00 / 255],
};

/** Classify a segment name by its left_ / right_ prefix. */
export function classifyBone(name: string): BoneSide {
    if (name.startsWith("left_")) return "left";
    if (name.startsWith("right_")) return "right";
    return "center";
}

/** wxyz → 3×3 rotation matrix (row-major, 9 floats). Matches skellyforge's
 *  RotationQuaternion.to_rotation_matrix (Diebel 2006 eq. 125). */
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

function dot3(a: readonly number[], b: readonly number[]): number {
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function cross3(a: readonly number[], b: readonly number[]): number[] {
    return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    ];
}

function normalize3(v: readonly number[]): number[] {
    const n = Math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]);
    return [v[0] / n, v[1] / n, v[2] / n];
}

/** Rodrigues rotation about a unit axis by an angle (row-major 3×3). */
function rotationAboutAxis(axis: readonly number[], angle: number): number[] {
    const [x, y, z] = axis;
    const c = Math.cos(angle);
    const s = Math.sin(angle);
    const t = 1 - c;
    return [
        t * x * x + c,     t * x * y - s * z, t * x * z + s * y,
        t * x * y + s * z, t * y * y + c,     t * y * z - s * x,
        t * x * z - s * y, t * y * z + s * x, t * z * z + c,
    ];
}

/** Rotation mapping a onto b (shortest arc), both unit vectors (row-major). */
function rotationBetweenVectors(a: readonly number[], b: readonly number[]): number[] {
    const dot = Math.min(1, Math.max(-1, dot3(a, b)));
    if (dot > 1 - 1e-9) return [1, 0, 0, 0, 1, 0, 0, 0, 1]; // a ≈ b
    if (dot < -1 + 1e-9) {
        // a ≈ -b: 180° about any axis perpendicular to a.
        const ref = Math.abs(a[0]) < 0.9 ? [1, 0, 0] : [0, 1, 0];
        const axis = normalize3(cross3(a, ref));
        return rotationAboutAxis(axis, Math.PI);
    }
    const axis = normalize3(cross3(a, b));
    return rotationAboutAxis(axis, Math.acos(dot));
}

/** The primary axis as a unit direction vector. */
function primaryAxisDirection(axis: PrimaryAxis): number[] {
    if (typeof axis === "string") {
        switch (axis) {
            case "x":  return [1, 0, 0];
            case "-x": return [-1, 0, 0];
            case "y":  return [0, 1, 0];
            case "-y": return [0, -1, 0];
            case "z":  return [0, 0, 1];
            case "-z": return [0, 0, -1];
        }
    }
    return normalize3([axis[0], axis[1], axis[2]]);
}

/** The rotation mapping the unit geometry's +Z onto the segment's primary-axis
 *  direction (row-major 3×3). Signed axes and 3-vectors both flow through the
 *  same shortest-arc rotation. */
function rotationOntoPrimaryAxis(axis: PrimaryAxis): number[] {
    return rotationBetweenVectors([0, 0, 1], primaryAxisDirection(axis));
}

/**
 * Build a per-instance table from a ModelDefinition (D5: names, not hierarchy
 * edges, are the index key). Instance ordering follows the model's segment
 * order — which is also the channel row order, so a segment's instance slot IS
 * its row index into the frame's segment/rotation channel data.
 */
export function buildBoneInstances(model: ModelDefinition): BoneInstanceTable {
    const segments = model.segments;
    if (segments.length === 0) {
        return {
            nameToIndex: new Map(),
            byName: new Map(),
            instances: [],
            byNameLengthProportion: new Map(),
            byNamePrimaryAxis: new Map(),
            byNameRestOrientation: new Map(),
            byNameCrossSection: new Map(),
        };
    }

    const nameToIndex = new Map<string, number>();
    const byName = new Map<string, number>();
    const instances: BoneInstance[] = [];
    const byNameLengthProportion = new Map<string, number>();
    const byNamePrimaryAxis = new Map<string, PrimaryAxis>();
    const byNameRestOrientation = new Map<string, readonly [number, number, number, number]>();
    const byNameCrossSection = new Map<string, number>();

    segments.forEach((segment, i) => {
        nameToIndex.set(segment.name, i);
        byName.set(segment.name, i);
        instances.push({ instanceIdx: i, name: segment.name, side: classifyBone(segment.name) });
        byNameLengthProportion.set(
            segment.name,
            Number.isFinite(segment.length_proportion) && segment.length_proportion > 0
                ? segment.length_proportion
                : 0,
        );
        byNamePrimaryAxis.set(segment.name, segment.primary_axis);
        byNameRestOrientation.set(segment.name, segment.rest_orientation);
        byNameCrossSection.set(segment.name, REGION_CROSS_SECTION[classifyRegion(segment.name)]);
    });

    return { nameToIndex, byName, instances, byNameLengthProportion, byNamePrimaryAxis, byNameRestOrientation, byNameCrossSection };
}

/**
 * Per-frame instance transform (pure — the only per-frame math, unit-tested).
 *
 * Composition: world = R_world · Q · S, where
 *   Q        rotationOntoPrimaryAxis(primaryAxis) — geometry +Z onto the bone's
 *            primary-axis direction (origin→distal),
 *   R_world  rotationMatrixFromQuaternion(quatWXYZ) — the segment's absolute
 *            world orientation (local → world), already inclusive of the rest pose.
 *
 * @param origin          proximal joint (segment origin), mm
 * @param quatWXYZ        world-frame quaternion [w, x, y, z] (ROTATIONS_WORLD)
 * @param _restOrientation unused (kept for the legacy call signature)
 * @param primaryAxis     the segment's primary axis (signed axis or 3-vector)
 * @param length          segment length; NaN/0 hides the instance
 * @param crossSection    transverse radius (mm) — same for 1 mm and 500 mm bones
 * @returns a 16-float column-major matrix, or null when the segment is hidden
 */
export function computeBoneMatrix(
    origin: readonly [number, number, number],
    quatWXYZ: readonly [number, number, number, number],
    _restOrientation: readonly [number, number, number, number],
    primaryAxis: PrimaryAxis,
    length: number,
    crossSection: number,
): number[] | null {
    if (!Number.isFinite(length) || length <= 0) return null;
    for (let i = 0; i < 3; i++) if (!Number.isFinite(origin[i])) return null;
    for (let i = 0; i < 4; i++) if (!Number.isFinite(quatWXYZ[i])) return null;

    const R = rotationMatrixFromQuaternion(quatWXYZ);
    const Q = rotationOntoPrimaryAxis(primaryAxis);
    const Rtotal = multiply3x3(R, Q);

    // Column-major storage: m[col*4 + row] = (Rtotal · S)[row][col], S diagonal.
    const m = new Array<number>(16);
    for (let col = 0; col < 3; col++) {
        const s = col === 0 ? crossSection : col === 1 ? crossSection : length;
        m[col * 4 + 0] = Rtotal[col] * s;
        m[col * 4 + 1] = Rtotal[3 + col] * s;
        m[col * 4 + 2] = Rtotal[6 + col] * s;
        m[col * 4 + 3] = 0;
    }
    m[12] = origin[0]; m[13] = origin[1]; m[14] = origin[2]; m[15] = 1;

    return m;
}
