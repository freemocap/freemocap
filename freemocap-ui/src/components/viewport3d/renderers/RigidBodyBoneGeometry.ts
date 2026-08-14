// RigidBodyBoneGeometry.ts
//
// F4 — the unit-length elliptical cone + sphere mesh shared by every rigid-body
// bone instance. One geometry, scaled per-instance to the segment's long-axis
// length. The elliptical (X-squished) cross-section makes ROLL/twist visible: a
// circular cone rotated about its long axis is identical at every roll angle.
//
// All THREE imports here are safe in any runtime (node/jsdom/build) — this
// module builds only a BufferGeometry, no scene, no renderer, no cleanup.

import {
    BufferGeometry,
    CylinderGeometry,
    Float32BufferAttribute,
    SphereGeometry,
    Vector3,
} from "three";

/**
 * Roll-visibility squish factor on the local X axis (doc 06 §: ~0.55).
 * Kept exported so tests can assert the elliptical cross-section is real.
 */
export const BONE_SQUISH_X = 0.55;
export const CONE_RADIUS_BOTTOM = 1.0; // proximal "joint" end — wider
export const CONE_RADIUS_TOP = 0.6;     // distal end — narrower
export const CONE_HEIGHT = 1.0;         // unit height along +Z
export const SPHERE_RADIUS = 1.1;       // slightly wider than the cone base

/** Number of merge groups fed to mergeGeometries — asserted so the merge holds. */
export const BONE_NUM_MERGE_GROUPS = 2;

const _apex = new Vector3();

/**
 * Produces a cone spanning (0, 0, APEX_O) .. (0, 0, 1), elliptical on the
 * local X axis. Geometry template computed from a source cylinder with a
 * non-zero APEX_O, so the exact apex can never re-trigger normalization NaNs
 * behind an operation that guards on a zero delta. The translated positions
 * are baked into the attribute buffer, so the result is origin-agnostic.
 */
function makeEllipticalCone(): BufferGeometry {
    // APEX_O !== 0 is load-bearing: keep the apex off the origin so the cone
    // length is never degenerate (guards against NaN in any downstream pass).
    const APEX_O = 0.5;
    const n = 12;              // radial segments
    const cone = new CylinderGeometry(
        CONE_RADIUS_TOP,
        CONE_RADIUS_BOTTOM,
        CONE_HEIGHT,
        n,
        1,                     // heightSegments — a single ring is enough
        false,                 // openEnded? no — caps stay
    );

    const pos = cone.attributes.position as Float32BufferAttribute;
    for (let i = 0; i < pos.count; i++) {
        _apex.fromBufferAttribute(pos, i);
        // Squish X (roll visibility)
        _apex.x *= BONE_SQUISH_X;
        // Map cylinder Z in [-0.5, +0.5] to the span [APEX_O, 1] via y = -2z.
        _apex.z = APEX_O - 2 * _apex.z;
        pos.setXYZ(i, _apex.x, _apex.y, _apex.z);
    }
    if (cone.boundingSphere) cone.boundingSphere = null;

    return cone;
}

/**
 * Build the shared unit-length elliptical cone + proximal sphere mesh.
 * The cone spans (+Z) from a (configurable but fixed) apex to length 1;
 * the sphere sits at the proximal end (Z = 0).
 */
export function createBoneMeshGeometry(): BufferGeometry {
    const cone = makeEllipticalCone();
    const sphere = new SphereGeometry(SPHERE_RADIUS, 8, 6);

    // Merge the cone + proximal sphere into one non-indexed BufferGeometry.
    // The sphere's center is at Z=0 — its distal half overlaps the cone's apex,
    // which is exactly the proximal-joint blend we want.
    return mergeBufferGeometries([cone, sphere]);
}

/**
 * Merge a set of buffer geometries into one (all attribute buffers preserved,
 * non-indexed). Mirrors three's `mergeGeometries` without the
 * `three/examples/jsm/...` import so this module stays testable in node.
 */
export function mergeBufferGeometries(geometries: BufferGeometry[]): BufferGeometry {
    const nonIndexed = geometries.map((g) => g.index ? g.toNonIndexed() : g);

    // Attribute names are the union of each geometry's attributes.
    const attrNames = new Set<string>();
    for (const g of nonIndexed) {
        for (const name of Object.keys(g.attributes)) attrNames.add(name);
    }

    const merged = new BufferGeometry();
    for (const name of attrNames) {
        const arrays: ArrayLike<number>[] = [];
        let itemSize = 0;
        for (const g of nonIndexed) {
            const attr = g.attributes[name];
            if (!attr) continue;
            const typed = attr as Float32BufferAttribute;
            // Push the backing typed array + that geometry's itemSize.
            arrays.push(typed.array);
            if (itemSize === 0) itemSize = typed.itemSize;
        }
        if (arrays.length === 0) continue;

        // Concatenate typed arrays (Float32/BufferAttribute storage is
        // uniform in practice for position/normal/uv).
        const total = arrays.reduce((acc, a) => acc + a.length, 0);
        const out = new Float32Array(total);
        let offset = 0;
        for (const a of arrays) {
            out.set(a as Float32Array, offset);
            offset += (a as Float32Array).length;
        }
        merged.setAttribute(name, new Float32BufferAttribute(out, itemSize));
    }

    // If every source had an index, we can preserve one — but mixed/absent
    // indices collapse to non-indexed above, so a merged index is unnecessary
    // for correctness and omitted for simplicity.
    return merged;
}
