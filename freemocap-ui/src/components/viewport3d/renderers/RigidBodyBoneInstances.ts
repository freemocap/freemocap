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
    // Schema always declares SEGMENT_ORIGINS (60 segments); a missing group is a
    // schema defect (fail loudly, per project rules) — no silent empty table.
    if (names.length === 0) {
        throw new Error("buildBoneInstances: schema declares no SEGMENT_ORIGINS channel group");
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

    return { nameToIndex, byName, instances, byNameLength };
}

/**
 * Per-frame instance transform (pure — the only per-frame math, unit-tested).
 *
 * Computes a 4×4 column-major matrix that places a unit-length (+Z) geometry
 * at `origin`, oriented by the world quaternion, scaled to `length` along the
 * long axis (and by the radius-independent `crossSection` on the transverse
 * axes — D6's radius is a fixed parameter, never derived from length).
 *
 * @param origin      proximal joint (segment origin), mm
 * @param quatWXYZ    world-frame quaternion [w, x, y, z]
 * @param length      segment long-axis length; NaN/0 hides the instance
 * @returns a 16-float column-major matrix, or null when the segment is hidden
 */
export function computeBoneMatrix(
    origin: readonly [number, number, number],
    quatWXYZ: readonly [number, number, number, number],
    length: number,
    crossSection: number,
): number[] | null {
    if (!Number.isFinite(length) || length <= 0) return null;
    for (let i = 0; i < 3; i++) if (!Number.isFinite(origin[i])) return null;
    for (let i = 0; i < 4; i++) if (!Number.isFinite(quatWXYZ[i])) return null;

    const [ow, ox, oy, oz] = quatWXYZ;

    // A point p_local maps to:  R(p_local ⊙ scale) + origin.
    // Column-major storage is  m[col*4 + row].
    // columns 0..2 = R * scale (rotation rows applied to scaled axes),
    // column 3   = translation origin.
    const sx = crossSection;
    const sy = crossSection;
    const sz = length;

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
    // column 0 (x axis scaled by sx)
    m[0] = r00 * sx; m[1] = r10 * sx; m[2] = r20 * sx; m[3] = 0;
    // column 1 (y axis scaled by sy)
    m[4] = r01 * sy; m[5] = r11 * sy; m[6] = r21 * sy; m[7] = 0;
    // column 2 (z axis — long axis — scaled by sz)
    m[8] = r02 * sz; m[9] = r12 * sz; m[10] = r22 * sz; m[11] = 0;
    // column 3 (translation)
    m[12] = origin[0]; m[13] = origin[1]; m[14] = origin[2]; m[15] = 1;

    return m;
}
