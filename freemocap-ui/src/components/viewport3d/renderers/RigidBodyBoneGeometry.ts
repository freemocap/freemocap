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
} from "three";

/**
 * Roll-visibility squish factor on the local X axis (doc 06 §: ~0.55).
 * Kept exported so tests can assert the elliptical cross-section is real.
 */
export const BONE_SQUISH_X = 0.55;
export const CONE_RADIUS_BOTTOM = 1.0; // proximal "joint" end (at the origin) — wider
export const CONE_RADIUS_TOP = 0.4;     // distal end — narrower (tapers toward the tip)
export const CONE_HEIGHT = 1.0;         // unit height along +Z (origin → distal)

/**
 * A unit tapered cone whose LONG AXIS is +Z, spanning Z∈[0, 1]: the WIDE
 * (proximal) end sits at the origin (Z=0, the joint), the NARROW tip at Z=1
 * (the distal end). Built from a THREE cylinder (whose long axis is +Y) and
 * re-oriented onto +Z, so per-instance scaling of Z by the segment length grows
 * the bone in ONE direction from its origin — never a double-ended spike.
 */
function makeConeAlongZ(): BufferGeometry {
    const n = 12; // radial segments
    // CylinderGeometry(radiusTop@+Y, radiusBottom@-Y, height): long axis +Y in
    // [-0.5, 0.5], wide end (radiusBottom) at -Y.
    const cone = new CylinderGeometry(
        CONE_RADIUS_TOP,
        CONE_RADIUS_BOTTOM,
        CONE_HEIGHT,
        n,
        1,      // heightSegments — a single ring is enough
        false,  // openEnded? no — caps stay
    );
    // +Y → +Z: the wide (-Y) end maps to -Z, the narrow (+Y) end to +Z; then
    // translate +Z by half the height so the wide/proximal end lands at Z=0 and
    // the narrow/distal tip at Z=1. rotate/translate carry the normals.
    cone.rotateX(Math.PI / 2);
    cone.translate(0, 0, CONE_HEIGHT / 2);
    return cone;
}

/**
 * Build the shared unit-length bone mesh: a tapered cone along +Z from the joint
 * (Z=0, the wide base) to the distal tip (Z=1, narrow), squished on X so
 * ROLL/twist is visible (a circular bone looks identical at every roll angle).
 * Per-instance, Z scales to the segment length and X/Y to a fixed cross-section
 * (D6).
 *
 * No joint sphere is merged in: the per-instance scale is non-uniform
 * (Z = length ≫ X/Y = cross-section), so a merged sphere would stretch into a
 * length-long spindle. The joint "blob" is the keypoint/landmark sphere already
 * drawn at each joint; a dedicated per-bone joint sphere would be a SEPARATE,
 * uniformly-scaled instanced mesh (a possible follow-up polish).
 */
export function createBoneMeshGeometry(): BufferGeometry {
    const cone = makeConeAlongZ();
    // Squish the transverse X for roll visibility, then recompute normals so the
    // lit material shades the (non-uniformly scaled) surface correctly.
    cone.scale(BONE_SQUISH_X, 1, 1);
    cone.computeVertexNormals();
    return cone;
}
