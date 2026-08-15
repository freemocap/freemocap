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

import { ChannelKind, type StreamSchema } from "@/services/server/transport/types";

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
}

/** The local basis slot a segment's long axis (its EXACT axis) occupies. */
export type BoneLongAxis = "x" | "y" | "z";

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

    return { nameToIndex, byName, instances, byNameLength, byNameLongAxis };
}

/**
 * Per-frame instance transform (pure — the only per-frame math, unit-tested).
 *
 * Computes a 4×4 column-major matrix that places a unit-length (+Z) geometry
 * at `origin`, oriented by the world quaternion, with its long axis mapped
 * onto the segment's declared long-axis basis slot (`longAxis`) and scaled to
 * `length` (and by the radius-independent `crossSection` on the transverse
 * axes — D6's radius is a fixed parameter, never derived from length).
 *
 * The VRM local-frame convention declares the long axis on +Y for body/hand
 * segments and +Z for face segments; the unit geometry is always +Z, so a
 * per-axis constant rotation Q maps geometry +Z onto the declared slot.
 *
 * @param origin      proximal joint (segment origin), mm
 * @param quatWXYZ    world-frame quaternion [w, x, y, z]
 * @param length      segment long-axis length; NaN/0 hides the instance
 * @param crossSection transverse radius (mm) — same for 1 mm and 500 mm bones
 * @param longAxis    the segment's EXACT axis basis name ("x" | "y" | "z")
 * @returns a 16-float column-major matrix, or null when the segment is hidden
 */
export function computeBoneMatrix(
    origin: readonly [number, number, number],
    quatWXYZ: readonly [number, number, number, number],
    length: number,
    crossSection: number,
    longAxis: BoneLongAxis,
): number[] | null {
    if (!Number.isFinite(length) || length <= 0) return null;
    for (let i = 0; i < 3; i++) if (!Number.isFinite(origin[i])) return null;
    for (let i = 0; i < 4; i++) if (!Number.isFinite(quatWXYZ[i])) return null;

    const [ow, ox, oy, oz] = quatWXYZ;

    // A point p_local maps to:  R · S · Q · p_local + origin.
    // Q rotates the unit geometry's +Z onto the declared long-axis slot.
    // S scales the long axis by `length` and the transverse axes by
    // `crossSection`. R is the segment's world rotation (wxyz).
    // Column-major storage is m[col*4 + row]; columns 0..2 = R·S·Q,
    // column 3 = translation origin.
    const sx = crossSection;
    const sy = crossSection;
    const sz = length;

    // Q (row-major 3×3, right-handed, determinant +1). The geometry's +Z
    // (its long axis) maps onto the declared long-axis slot; the remaining
    // axes keep the frame right-handed.
    const Q: readonly number[] =
        longAxis === "z" ? [1, 0, 0, 0, 1, 0, 0, 0, 1]
        : longAxis === "y" ? [1, 0, 0, 0, 0, 1, 0, -1, 0]   // ẑ → ŷ, ŷ → -ẑ
        :                    [0, 0, 1, 0, 1, 0, -1, 0, 0];  // ẑ → x̂, x̂ → -ẑ

    // R (wxyz → rotation matrix):
    const r00 = 1 - 2 * (oy * oy + oz * oz);
    const r01 = 2 * (ox * oy - ow * oz);
    const r02 = 2 * (ox * oz + ow * oy);
    const r10 = 2 * (ox * oy + ow * oz);
    const r11 = 1 - 2 * (ox * ox + oz * oz);
    const r12 = 2 * (oy * oz - ow * ox);
    const r20 = 2 * (ox * oz - ow * oy);
    const r21 = 2 * (oy * oz + ow * ox);
    const r22 = 1 - 2 * (ox * ox + oy * oy);

    const m = new Array<number>(16);
    for (let col = 0; col < 3; col++) {
        // v = Q · (S · e_col): the scale applies to the GEOMETRY's axes
        // (geometry z = long axis → length), then Q rotates them onto the
        // segment's declared long-axis slot.
        const s0 = col === 0 ? sx : 0;
        const s1 = col === 1 ? sy : 0;
        const s2 = col === 2 ? sz : 0;
        const v0 = Q[0] * s0 + Q[1] * s1 + Q[2] * s2;
        const v1 = Q[3] * s0 + Q[4] * s1 + Q[5] * s2;
        const v2 = Q[6] * s0 + Q[7] * s1 + Q[8] * s2;
        // R · v
        m[col * 4 + 0] = r00 * v0 + r01 * v1 + r02 * v2;
        m[col * 4 + 1] = r10 * v0 + r11 * v1 + r12 * v2;
        m[col * 4 + 2] = r20 * v0 + r21 * v1 + r22 * v2;
        m[col * 4 + 3] = 0;
    }
    // column 3 (translation)
    m[12] = origin[0]; m[13] = origin[1]; m[14] = origin[2]; m[15] = 1;

    return m;
}
