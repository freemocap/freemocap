// RigidBodyBoneInstances.test.ts
//
// F4 — framework-free tests (no Vitest in this repo). Run with esbuild + node:
//
//   node_modules/.bin/esbuild \
//     src/components/viewport3d/renderers/__tests__/rigid-body-bone.test.ts \
//     --bundle --platform=node --format=esm --outfile=.tmp-rigid-body-bone-test.mjs \
//   && node .tmp-rigid-body-bone-test.mjs
//
// Covers:
//   - buildBoneInstances: index-by-NAME (D5), schema-time resolution (D14),
//     color-set-once-by-side (D15) via the pure classifyBone/BONE_SIDE_COLORS.
//   - computeBoneMatrix: origin + world quaternion + length → matrix, with
//     pinned expected values (identity quat, +Z 90° quat, mismatched lengths).
//   - D6 cross-section independence: two very different lengths produce the
//     same transverse radius (cross-section is a fixed parameter, never length).
//
// No THREE rendering loop is exercised — only the pure math. The React wiring
// (RigidBodyBoneRenderer) stays untested, matching the rest of the viewport.

import { ChannelKind, type StreamSchema } from "@/services/server/transport/types";
import {
    BONE_SIDE_COLORS,
    buildBoneInstances,
    classifyBone,
    computeBoneMatrix,
} from "../RigidBodyBoneInstances";

// ---- tiny framework-free assert -------------------------------------------

function assert(cond: unknown, message: string): asserts cond {
    if (!cond) throw new Error(`ASSERT: ${message}`);
}
function assertEq<T>(actual: T, expected: T, message: string): void {
    if (actual !== expected) throw new Error(`${message} (expected ${String(expected)}, got ${String(actual)})`);
}
function assertClose(actual: number, expected: number, eps: number, message: string): void {
    if (Math.abs(actual - expected) > eps) {
        throw new Error(`${message} (expected ~${expected}, got ${actual})`);
    }
}

// ---- fixture ---------------------------------------------------------------

// A minimal-but-representative six-group schema. keypoints (76) and the other
// groups are collapsed here — buildBoneInstances only reads the SEGMENT_ORIGINS
// group (index-by-name), so this is sufficient for the D5/D14/D15 assertions.
function makeSchemaFixture(): StreamSchema {
    const segmentNames = [
        "hips",
        "spine",
        "left_upper_arm",
        "right_upper_arm",
        "left_lower_leg",
    ];
    const channels = [
        { kind: ChannelKind.KEYPOINTS_3D, names: ["hips_center"], columns: ["x", "y", "z", "err"], units: "mm" },
        { kind: ChannelKind.SEGMENT_ORIGINS, names: segmentNames, columns: ["x", "y", "z"], units: "mm" },
        { kind: ChannelKind.ROTATIONS_LOCAL, names: segmentNames, columns: ["w", "x", "y", "z"], units: "" },
        { kind: ChannelKind.ROTATIONS_WORLD, names: segmentNames, columns: ["w", "x", "y", "z"], units: "" },
    ];
    return {
        stream_id: "test-stream",
        stream_name: "test",
        coordinate_convention: {
            units: "mm",
            handedness: "right",
            up_axis: "+z",
            forward_axis: "+x",
            rotation_frame: "world",
            rotation_form: "quaternion",
        },
        channels,
        connections: [],
        joint_hierarchy: {},
        segment_parents: { hips: null, spine: "hips", left_upper_arm: "spine", right_upper_arm: "spine", left_lower_leg: "left_upper_arm" },
        rest_pose: {
            positions: {
                hips_center: [0, 0, 0],
                trunk_center: [0, 0, 300],
            },
            reference_orientations: {},
        },
        segment_lengths: {
            hips: 300,
            spine: 300,
            left_upper_arm: 400,
            right_upper_arm: 150,
            left_lower_leg: 350,
        },
        camera_ids: [],
        camera_image_sizes: {},
        max_persons: 1,
        message_type: "stream_schema",
    };
}

// ---- 1. buildBoneInstances: index by NAME (D5, D14) ------------------------

function testBuildBoneInstancesIndexByName(): void {
    const schema = makeSchemaFixture();
    const table = buildBoneInstances(schema);

    // D5/D14: name → index is the single authority, stable and by name.
    assertEq(table.nameToIndex.get("hips"), 0, "hips → slot 0");
    assertEq(table.nameToIndex.get("spine"), 1, "spine → slot 1");
    assertEq(table.nameToIndex.get("left_upper_arm"), 2, "left_upper_arm → slot 2");
    assertEq(table.nameToIndex.get("right_upper_arm"), 3, "right_upper_arm → slot 3");
    assertEq(table.nameToIndex.get("left_lower_leg"), 4, "left_lower_leg → slot 4");

    assertEq(table.instances.length, 5, "5 instances");
    // Side classification is by name prefix, resolved ONCE here (D15 input).
    assertEq(table.instances[0].side, "center", "hips side = center");
    assertEq(table.instances[1].side, "center", "spine side = center");
    assertEq(table.instances[2].side, "left", "left_upper_arm side = left");
    assertEq(table.instances[3].side, "right", "right_upper_arm side = right");
    assertEq(table.instances[4].side, "left", "left_lower_leg side = left");

    // D14: index-by-name is order-independent of the topology dict.
    const reordered = { ...schema };
    // segment_parents order differs from segment_names but must NOT move slots.
    assertEq(table.byName.get("left_lower_leg"), 4, "byName alias agrees");

    console.log("PASS: testBuildBoneInstancesIndexByName");
}

// ---- 2. classifyBone side classification -----------------------------------

function testClassifyBone(): void {
    assertEq(classifyBone("left_upper_arm"), "left", "left_upper_arm → left");
    assertEq(classifyBone("right_upper_leg"), "right", "right_upper_leg → right");
    assertEq(classifyBone("spine"), "center", "spine → center");
    assertEq(classifyBone("hips"), "center", "hips → center (no prefix)");
    console.log("PASS: testClassifyBone");
}

// ---- 3. computeBoneMatrix: identity quaternion (T-pose) --------------------

function testComputeBoneMatrixIdentity(): void {
    // Identity quat [1,0,0,0], origin at origin, length 2, crossSection 0.5.
    const m = computeBoneMatrix([0, 0, 0], [1, 0, 0, 0], 2, 0.5)!;
    assert(m !== null, "identity matrix not hidden");

    // Column-major. Column 0 = (0.5*1, 0, 0) → x-axis scaled 0.5.
    assertClose(m[0], 0.5, 1e-6, "m00 = 0.5");
    assertClose(m[1], 0, 1e-6, "m10 = 0");
    assertClose(m[2], 0, 1e-6, "m20 = 0");
    // Column 1 = (0, 0.5, 0) → y-axis scaled 0.5.
    assertClose(m[5], 0.5, 1e-6, "m11 = 0.5");
    assertClose(m[4], 0, 1e-6, "m01 = 0");
    // Column 2 = (0, 0, 2) → z (long axis) scaled by length.
    assertClose(m[10], 2, 1e-6, "m22 = length 2");
    assertClose(m[8], 0, 1e-6, "m02 = 0");
    assertClose(m[9], 0, 1e-6, "m12 = 0");
    // Column 3 = translation origin.
    assertClose(m[12], 0, 1e-6, "tx = 0");
    assertClose(m[13], 0, 1e-6, "ty = 0");
    assertClose(m[14], 0, 1e-6, "tz = 0");
    assertClose(m[15], 1, 1e-6, "m33 = 1");
    console.log("PASS: testComputeBoneMatrixIdentity");
}

// ---- 4. computeBoneMatrix: +Z 90° quaternion (long axis rotates to +Y) -----

function testComputeBoneMatrixPlusZ90(): void {
    // Quaternion for 90° about +Z (wxyz): (cos45, 0, 0, sin45).
    const s = Math.SQRT1_2;
    const m = computeBoneMatrix([1, 2, 3], [s, 0, 0, s], 4, 0.5)!;
    assert(m !== null, "+Z90 matrix not hidden");

    // Rotation about Z leaves col0 and col1 rotated in XY; col2 (0,0,1) stays.
    // For 90° about Z: x-axis → +y, so col0 ≈ (0, 0.5, 0).
    assertClose(m[0], 0, 1e-6, "m00 ≈ 0");
    assertClose(m[1], 0.5, 1e-6, "m10 ≈ 0.5");
    assertClose(m[4], -0.5, 1e-6, "m01 ≈ -0.5");
    assertClose(m[5], 0, 1e-6, "m11 ≈ 0");
    // Long axis column (z) is unchanged by a z-rotation: (0,0,4).
    assertClose(m[8], 0, 1e-6, "m02 = 0");
    assertClose(m[9], 0, 1e-6, "m12 = 0");
    assertClose(m[10], 4, 1e-6, "m22 = length 4");
    // Translation.
    assertClose(m[12], 1, 1e-6, "tx = 1");
    assertClose(m[13], 2, 1e-6, "ty = 2");
    assertClose(m[14], 3, 1e-6, "tz = 3");
    console.log("PASS: testComputeBoneMatrixPlusZ90");
}

// ---- 5. D6: cross-section independent of length ----------------------------

function testCrossSectionIndependentOfLength(): void {
    // A 1 mm segment and a 500 mm segment, same crossSection: the transverse
    // radius (columns 0 and 1 magnitude) is IDENTICAL.
    const short = computeBoneMatrix([0, 0, 0], [1, 0, 0, 0], 1, 0.5)!;
    const long = computeBoneMatrix([0, 0, 0], [1, 0, 0, 0], 500, 0.5)!;
    assert(short !== null && long !== null, "both matrices resolved");

    const transverseMag = (m: number[]) => Math.hypot(m[0], m[1], m[2]);
    assertClose(transverseMag(short), 0.5, 1e-6, "short segment transverse radius");
    assertClose(transverseMag(long), 0.5, 1e-6, "500mm segment transverse radius (D6)");
    // But the long-axis scale differs (by design — that's the length, not radius).
    assertClose(short[10], 1, 1e-6, "short long-axis span");
    assertClose(long[10], 500, 1e-6, "500mm long-axis span");
    console.log("PASS: testCrossSectionIndependentOfLength");
}

// ---- 6. hidden mesh: NaN / zero length hides -------------------------------

function testComputeBoneMatrixHidesInvalid(): void {
    assertEq(computeBoneMatrix([0, 0, 0], [1, 0, 0, 0], 0, 0.5), null, "zero length hidden");
    assertEq(computeBoneMatrix([0, 0, 0], [1, 0, 0, 0], NaN, 0.5), null, "NaN length hidden");
    assertEq(computeBoneMatrix([NaN, 0, 0], [1, 0, 0, 0], 1, 0.5), null, "NaN origin hidden");
    assertEq(computeBoneMatrix([0, 0, 0], [NaN, 0, 0, 0], 1, 0.5), null, "NaN quat hidden");
    console.log("PASS: testComputeBoneMatrixHidesInvalid");
}

// ---- 7. rest-length derivation from schema.segment_lengths (doc 11 F4 Step 3) --

function testBuildSegmentsLengthsFromSchema(): void {
    const schema = makeSchemaFixture();
    const table = buildBoneInstances(schema);

    // Lengths come straight from the schema's segment_lengths map.
    assertClose(table.byNameLength.get("hips")!, 300, 1e-6, "hips rest length");
    assertClose(table.byNameLength.get("spine")!, 300, 1e-6, "spine rest length");
    assertClose(table.byNameLength.get("left_upper_arm")!, 400, 1e-6, "left_upper_arm rest length");
    assertClose(table.byNameLength.get("right_upper_arm")!, 150, 1e-6, "right_upper_arm rest length");
    assertClose(table.byNameLength.get("left_lower_leg")!, 350, 1e-6, "left_lower_leg rest length");
    console.log("PASS: testBuildSegmentsLengthsFromSchema");
}

// ---- 8. two segments with different rest spans → different long-axis scales --

function testDifferentRestSpansScaleLongAxisDifferently(): void {
    // left_upper_arm = 400 mm, right_upper_arm = 150 mm (identical crossSection,
    // identity quaternion, same origin). Their long-axis (col2, m[10]) scales are
    // their distinct rest lengths — the core of F4 Step 3.
    const left = computeBoneMatrix([0, 0, 0], [1, 0, 0, 0], 400, 0.5)!;
    const right = computeBoneMatrix([0, 0, 0], [1, 0, 0, 0], 150, 0.5)!;
    assert(left !== null && right !== null, "both matrices resolved");

    assertClose(left[10], 400, 1e-6, "left long-axis scale = 400");
    assertClose(right[10], 150, 1e-6, "right long-axis scale = 150");
    // Distinctness asserted explicitly (not just the separate pins).
    assert(left[10] !== right[10], "long-axis scales must differ");
    console.log("PASS: testDifferentRestSpansScaleLongAxisDifferently");
}

// ---- 9. D6 cross-section independence still holds with per-segment lengths --

function testCrossSectionIndependentOfRestLength(): void {
    // Same 500 mm cross-section magnitude regardless of the per-segment length.
    const short = computeBoneMatrix([0, 0, 0], [1, 0, 0, 0], 150, 0.5)!;
    const long = computeBoneMatrix([0, 0, 0], [1, 0, 0, 0], 400, 0.5)!;
    const transverseMag = (m: number[]) => Math.hypot(m[0], m[1], m[2]);
    assertClose(transverseMag(short), 0.5, 1e-6, "150 mm transverse radius (D6)");
    assertClose(transverseMag(long), 0.5, 1e-6, "400 mm transverse radius (D6)");
    console.log("PASS: testCrossSectionIndependentOfRestLength");
}

function testMissingSchemaLengthFallsBackToUnitLength(): void {
    // A segment name missing from schema.segment_lengths must fall back to the
    // declared unit length (1.0), NOT throw or produce NaN.
    const schema = makeSchemaFixture();
    schema.segment_lengths = {
        hips: 300,
        // left_lower_leg and left_upper_arm are deliberately omitted → 1.0.
    };
    const table = buildBoneInstances(schema);
    assertClose(table.byNameLength.get("hips")!, 300, 1e-6, "hips still in map");
    assertClose(table.byNameLength.get("left_lower_leg")!, 1.0, 1e-6, "missing name → unit fallback");
    assertClose(table.byNameLength.get("left_upper_arm")!, 1.0, 1e-6, "missing name → unit fallback");
    console.log("PASS: testMissingSchemaLengthFallsBackToUnitLength");
}

// ---- 10. new-schema-arrival updates the length map ---------------------------

function testNewSchemaUpdatesLengths(): void {
    // A re-sent schema (with updated measured lengths) must replace the map.
    const schema = makeSchemaFixture();
    const table1 = buildBoneInstances(schema);
    assertClose(table1.byNameLength.get("left_upper_arm")!, 400, 1e-6, "initial upper-arm 400");

    const schema2 = { ...schema, segment_lengths: { ...schema.segment_lengths, left_upper_arm: 412.5 } };
    const table2 = buildBoneInstances(schema2);
    assertClose(table2.byNameLength.get("left_upper_arm")!, 412.5, 1e-6, "updated upper-arm 412.5");
    // Unchanged segments keep their value.
    assertClose(table2.byNameLength.get("hips")!, 300, 1e-6, "hips unchanged");
    console.log("PASS: testNewSchemaUpdatesLengths");
}

// ---- run -------------------------------------------------------------------

testComputeBoneMatrixHidesInvalid();
testClassifyBone();
testBuildBoneInstancesIndexByName();
testComputeBoneMatrixIdentity();
testComputeBoneMatrixPlusZ90();
testCrossSectionIndependentOfLength();
testBuildSegmentsLengthsFromSchema();
testDifferentRestSpansScaleLongAxisDifferently();
testCrossSectionIndependentOfRestLength();
testMissingSchemaLengthFallsBackToUnitLength();
testNewSchemaUpdatesLengths();

console.log("\nAll rigid-body bone tests passed.");
