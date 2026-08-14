// standard-stream-integration.test.ts
//
// F5b — the frontend half of the gate: golden schema + sample → decoder →
// registry resolve → renderer instance placement. Proves the wire end of the
// chain the manual full-loop run exercises live: connect → schema → samples →
// rigid-body bone instances placed in the viewport, with the dual channels
// (tracker keypoints + landmarks) both present.
//
// Framework-free (no Vitest). Run:
//   node_modules/.bin/esbuild \
//     src/components/viewport3d/renderers/__tests__/standard-stream-integration.test.ts \
//     --bundle --platform=node --format=esm --outfile=.tmp-standard-stream-integration-test.mjs \
//   && node .tmp-standard-stream-integration-test.mjs

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { decodeSample, decodeSchema } from "@/services/server/transport/StandardStreamDecoder";
import { createSchemaRegistry } from "@/services/server/transport/SchemaRegistry";
import {
    buildBoneInstances,
    computeBoneMatrix,
} from "../RigidBodyBoneInstances";

// ---- tiny framework-free assert -------------------------------------------

function assert(cond: unknown, message: string): asserts cond {
    if (!cond) throw new Error(`ASSERT: ${message}`);
}
function assertEq<T>(actual: T, expected: T, message: string): void {
    if (actual !== expected) {
        throw new Error(`${message} (expected ${String(expected)}, got ${String(actual)})`);
    }
}
function assertClose(actual: number, expected: number, eps: number, message: string): void {
    if (Math.abs(actual - expected) > eps) {
        throw new Error(`${message} (expected ~${expected}, got ${actual})`);
    }
}

// The run command is issued from the freemocap-ui directory (see the
// rigid-body-bone.test.ts header for the same convention).
const FIXTURES = join(process.cwd(), "src", "services", "server", "transport", "__fixtures__");

const schema = decodeSchema(readFileSync(join(FIXTURES, "schema_golden.json"), "utf-8"));
const sampleBytes = new Uint8Array(readFileSync(join(FIXTURES, "sample_golden.bin")));
const sample = decodeSample(
    sampleBytes.buffer.slice(sampleBytes.byteOffset, sampleBytes.byteOffset + sampleBytes.byteLength) as ArrayBuffer,
    schema,
);

const registry = createSchemaRegistry();
registry.register(schema);
const resolved = registry.resolve(sample);

// ── 1. the dual channels both resolve ────────────────────────────────────

function testDualChannelsResolve(): void {
    assert(resolved.keypoints !== null, "tracker keypoints resolved");
    const noseIdx = resolved.keypoints!.names.indexOf("nose");
    assert(noseIdx !== -1, "nose in tracker keypoints");
    assertEq(resolved.keypoints!.data[noseIdx * 3 + 2], 1600.0, "tracker nose z");

    assert(resolved.landmarks !== null, "landmarks resolved");
    const hipsIdx = resolved.landmarks!.names.indexOf("hips_center");
    assert(hipsIdx !== -1, "hips_center in landmarks");
    assertEq(resolved.landmarks!.data[hipsIdx * 3 + 2], 900.0, "landmark hips_center z");
    console.log("PASS: testDualChannelsResolve");
}

// ── 2. schema → 60 bone instances, placed from the wire data ─────────────

function testInstancesPlacedFromWire(): void {
    const table = buildBoneInstances(schema);
    assertEq(table.nameToIndex.size, 60, "60 bone instances indexed");
    assertEq(table.instances.length, 60, "60 instance descriptors");

    assert(resolved.segmentOrigins !== null, "segment origins resolved");
    assert(resolved.rotationsWorld !== null, "world rotations resolved");
    const origins = resolved.segmentOrigins!;
    const rotations = resolved.rotationsWorld!;

    let placed = 0;
    for (const name of origins.names) {
        const oIdx = origins.names.indexOf(name);
        const rIdx = rotations.names.indexOf(name);
        const origin: [number, number, number] = [
            origins.data[oIdx * 3],
            origins.data[oIdx * 3 + 1],
            origins.data[oIdx * 3 + 2],
        ];
        const quat: [number, number, number, number] = [
            rotations.data[rIdx * 4],
            rotations.data[rIdx * 4 + 1],
            rotations.data[rIdx * 4 + 2],
            rotations.data[rIdx * 4 + 3],
        ];
        const length = schema.segment_lengths[name];
        const matrix = computeBoneMatrix(origin, quat, length, 20.0);
        if (matrix === null) {
            // An unobserved segment (NaN row) — the renderer skips it; this is
            // the expected degradation path, not an error.
            continue;
        }
        placed += 1;
        for (const v of matrix) {
            assert(Number.isFinite(v), `finite matrix for ${name}`);
        }
        // The matrix translation column IS the segment origin.
        assertEq(matrix[12], origin[0], `${name} translation x`);
        assertEq(matrix[13], origin[1], `${name} translation y`);
        assertEq(matrix[14], origin[2], `${name} translation z`);
    }
    // The golden sample carries a handful of observed segments (the rest are
    // NaN rows by construction) — the gate is: every observed segment places.
    assert(placed >= 3, `placed ${placed} instances (expected the observed subset)`);
    console.log(`PASS: testInstancesPlacedFromWire (${placed} placed)`);
}

// ── 3. the wire quaternion drives the bone axes (wxyz convention) ────────

function testWireQuaternionDrivesBoneAxes(): void {
    // spine quat (0.7071, 0, 0, 0.7071) = 90° about +Z. A rotation about Z
    // fixes the Z axis itself, so the bone's length axis (column 2) stays +Z
    // while the transverse axis (column 0) rotates x̂ → ŷ.
    const origin: [number, number, number] = [0, 0, 0];
    const quat: [number, number, number, number] = [0.7071, 0, 0, 0.7071];
    const matrix = computeBoneMatrix(origin, quat, 100.0, 1.0);
    assert(matrix !== null, "matrix computed");
    // column 0 (x axis): (0, 1, 0)
    assertClose(matrix![0], 0.0, 1e-3, "col0 x");
    assertClose(matrix![1], 1.0, 1e-3, "col0 y");
    assertClose(matrix![2], 0.0, 1e-3, "col0 z");
    // column 2 (length axis, scaled by length): (0, 0, 100)
    assertClose(matrix![8], 0.0, 1e-3, "col2 x");
    assertClose(matrix![9], 0.0, 1e-3, "col2 y");
    assertClose(matrix![10], 100.0, 1e-3, "col2 z (length)");
    console.log("PASS: testWireQuaternionDrivesBoneAxes");
}

// ── run ───────────────────────────────────────────────────────────────────

testDualChannelsResolve();
testInstancesPlacedFromWire();
testWireQuaternionDrivesBoneAxes();

console.log("\nAll standard-stream integration tests passed.");
