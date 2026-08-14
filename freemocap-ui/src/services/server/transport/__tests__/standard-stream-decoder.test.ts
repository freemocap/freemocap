// standard-stream-decoder.test.ts
//
// F3 — cross-language golden-byte parity for the standard-stream decoder.
// This project has no unit-test framework (Vitest is NOT installed); tests run
// framework-free via esbuild + node, matching the existing
// src/store/slices/cameras/cameras-reconcile.test.ts pattern.
//
// Run:
//   node_modules/.bin/esbuild src/services/server/transport/__tests__/standard-stream-decoder.test.ts \
//     --bundle --platform=node --format=esm --outfile=.tmp-stream-decoder-test.mjs \
//   && node .tmp-stream-decoder-test.mjs
//
// The golden fixtures (__fixtures__/schema_golden.json + sample_golden.bin)
// are copies of the Python F2a fixtures and must decode to the same values the
// Python side pins in freemocap/tests/test_stream_sample_encoder.py. Regenerate
// them (Python) with:
//   uv run python -m freemocap.tests.streaming_fixtures.regenerate_golden

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { decodeSchema, decodeSample } from "../StandardStreamDecoder";
import { createSchemaRegistry } from "../SchemaRegistry";
import { RollingWindowStore } from "../RollingWindowStore";
import { ChannelKind, OverlayLayer } from "../types";

// Tiny framework-free assert.
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

// The run command is issued from the freemocap-ui directory, so resolve the
// fixtures relative to cwd (bundling moves the output file to repo root).
const FIXTURES = join(
  process.cwd(),
  "src",
  "services",
  "server",
  "transport",
  "__fixtures__",
);

const schemaJson = readFileSync(join(FIXTURES, "schema_golden.json"), "utf-8");
const sampleBytes = new Uint8Array(readFileSync(join(FIXTURES, "sample_golden.bin")));
const sampleBuf = sampleBytes.buffer.slice(
  sampleBytes.byteOffset,
  sampleBytes.byteOffset + sampleBytes.byteLength,
) as ArrayBuffer;

// ── 1. schema JSON round-trip ──────────────────────────────────────────

function testSchemaRoundTrip(): void {
  const schema = decodeSchema(schemaJson);
  assertEq(schema.stream_id, "golden-stream-id", "stream_id");
  assertEq(schema.channels.length, 7, "seven channel groups");
  assertEq(schema.channels[0].kind, ChannelKind.KEYPOINTS_3D, "channel 0 kind");
  assertEq(schema.channels[1].kind, ChannelKind.LANDMARKS_3D, "channel 1 kind");
  assertEq(schema.channels[2].kind, ChannelKind.SEGMENT_ORIGINS, "channel 2 kind");
  assertEq(schema.channels[3].kind, ChannelKind.ROTATIONS_LOCAL, "channel 3 kind");
  assertEq(schema.channels[4].kind, ChannelKind.ROTATIONS_WORLD, "channel 4 kind");
  assertEq(schema.channels[5].kind, ChannelKind.DERIVED_POINTS, "channel 5 kind");
  assertEq(schema.channels[6].kind, ChannelKind.OVERLAY_2D, "channel 6 kind");
  assertEq(schema.channels[0].names.length, 59, "59 rtmpose tracker keypoints");
  assertEq(schema.channels[1].names.length, 76, "76 landmarks");
  assertEq(schema.channels[2].names.length, 60, "60 segments");
  assertEq(schema.max_persons, 1, "max_persons");
  assertEq(schema.camera_ids.length, 2, "two cameras");
  assertEq(schema.segment_parents["hips"], null, "hips has no parent");
  assertEq(schema.segment_parents["spine"], "hips", "spine parent is hips");
  // segment_lengths: one entry per segment name (60), default anthropometric values.
  assertEq(Object.keys(schema.segment_lengths).length, 60, "60 segment lengths");
  // hips: length_ratio 0.145 × NOMINAL_SUBJECT_HEIGHT_MM (1750).
  assertClose(schema.segment_lengths["hips"], 253.75, 1e-3, "hips default length");
  console.log("PASS: testSchemaRoundTrip");
}

// ── 2. golden sample decode to pinned values ───────────────────────────

function testGoldenSampleDecode(): void {
  const schema = decodeSchema(schemaJson);
  const sample = decodeSample(sampleBuf, schema);

  assertEq(sample.frameNumber, 42, "frame number 42");
  assertClose(sample.timestamp, 123.456, 1e-3, "timestamp 123.456");
  assertEq(sample.blocks.length, 8, "6 groups + 2 camera overlays = 8 blocks");

  const registry = createSchemaRegistry();
  registry.register(schema);
  const resolved = registry.resolve(sample);

  // KEYPOINTS_3D — tracker-named nose position
  assert(resolved.keypoints !== null, "resolved keypoints present");
  const kpNames = resolved.keypoints!.names;
  const noseKpIdx = kpNames.indexOf("nose");
  assert(noseKpIdx !== -1, "nose in tracker keypoint names");
  const nx = resolved.keypoints!.data[noseKpIdx * 3];
  const ny = resolved.keypoints!.data[noseKpIdx * 3 + 1];
  const nz = resolved.keypoints!.data[noseKpIdx * 3 + 2];
  assertEq(nx, 0.0, "keypoints nose.x");
  assertEq(ny, 0.0, "keypoints nose.y");
  assertEq(nz, 1600.0, "keypoints nose.z");

  // LANDMARKS_3D — hips_center position
  assert(resolved.landmarks !== null, "resolved landmarks present");
  const lmNames = resolved.landmarks!.names;
  const hipsIdx = lmNames.indexOf("hips_center");
  assert(hipsIdx !== -1, "hips_center in landmark names");
  const hx = resolved.landmarks!.data[hipsIdx * 3];
  const hy = resolved.landmarks!.data[hipsIdx * 3 + 1];
  const hz = resolved.landmarks!.data[hipsIdx * 3 + 2];
  assertEq(hx, 0.0, "hips_center.x");
  assertEq(hy, 0.0, "hips_center.y");
  assertEq(hz, 900.0, "hips_center.z");

  // SEGMENT_ORIGINS — left_upper_arm origin == left_shoulder
  assert(resolved.segmentOrigins !== null, "segment origins present");
  const segNames = resolved.segmentOrigins!.names;
  const luaIdx = segNames.indexOf("left_upper_arm");
  assert(luaIdx !== -1, "left_upper_arm in segment names");
  assertEq(resolved.segmentOrigins!.data[luaIdx * 3], -250.0, "left_upper_arm origin.x");

  // ROTATIONS_WORLD — spine wxyz quaternion
  assert(resolved.rotationsWorld !== null, "rotations world present");
  const spineIdx = resolved.rotationsWorld!.names.indexOf("spine");
  assert(spineIdx !== -1, "spine in rotation names");
  const sw = resolved.rotationsWorld!.data[spineIdx * 4];
  const sx = resolved.rotationsWorld!.data[spineIdx * 4 + 1];
  const sy = resolved.rotationsWorld!.data[spineIdx * 4 + 2];
  const sz = resolved.rotationsWorld!.data[spineIdx * 4 + 3];
  assertClose(sw, 0.7071, 1e-4, "spine world quat w");
  assertEq(sx, 0.0, "spine world quat x");
  assertEq(sy, 0.0, "spine world quat y");
  assertClose(sz, 0.7071, 1e-4, "spine world quat z");

  // DERIVED_POINTS — CoM and XCoM
  assert(resolved.derived.centerOfMass !== null, "center of mass present");
  assertClose(resolved.derived.centerOfMass![0], 5.0, 1e-4, "CoM.x");
  assertClose(resolved.derived.centerOfMass![1], -3.0, 1e-4, "CoM.y");
  assertClose(resolved.derived.centerOfMass![2], 950.0, 1e-4, "CoM.z");
  assert(resolved.derived.xcom !== null, "xcom present");
  assertClose(resolved.derived.xcom![0], 12.5, 1e-4, "XCoM.x");

  // Overlays — one DETECTIONS block per camera (cam-0 + cam-1)
  assertEq(resolved.overlays.length, 2, "two overlay blocks");
  const byCam = new Map(resolved.overlays.map((o) => [o.cameraId, o]));
  assert(byCam.has("cam-0"), "cam-0 overlay");
  assert(byCam.has("cam-1"), "cam-1 overlay");
  assertEq(byCam.get("cam-0")!.layer, OverlayLayer.DETECTIONS, "cam-0 overlay layer");
  const cam0 = byCam.get("cam-0")!;
  const noseIdx = cam0.names.indexOf("nose");
  assert(noseIdx !== -1, "nose in overlay names");
  assertEq(cam0.data[noseIdx * 3], 320.0, "cam-0 nose.x");
  assertEq(cam0.data[noseIdx * 3 + 1], 240.0, "cam-0 nose.y");
  console.log("PASS: testGoldenSampleDecode");
}

// ── 3. rolling-window eviction ─────────────────────────────────────────

function testRollingWindowEviction(): void {
  const store = new RollingWindowStore<number>({ maxFrames: 5 });
  for (let i = 1; i <= 7; i++) store.push(i);
  assertEq(store.length, 5, "only 5 retained of 7");
  const last = store.getLast();
  assertEq(last[0], 3, "oldest retained is 3 (1,2 evicted)");
  assertEq(last[4], 7, "newest is 7");
  console.log("PASS: testRollingWindowEviction");
}

// ── 4. rolling-window subscriber fire ──────────────────────────────────

function testRollingWindowSubscriber(): void {
  const store = new RollingWindowStore<number>({ maxFrames: 10 });
  const seen: number[] = [];
  const unsub = store.subscribe((n) => seen.push(n));
  store.push(42);
  store.push(43);
  assertEq(seen.length, 2, "two pushes two fires");
  assertEq(seen[0], 42, "first fire 42");
  assertEq(seen[1], 43, "second fire 43");
  unsub();
  store.push(44);
  assertEq(seen.length, 2, "no fire after unsubscribe");
  console.log("PASS: testRollingWindowSubscriber");
}

// ── 5. first-byte demux / tag validation ───────────────────────────────

function testFirstByteTags(): void {
  // The golden sample's first byte must be SAMPLE_HEADER (10), and the decoder
  // must reject a buffer whose first byte is wrong.
  assertEq(sampleBytes[0], 10, "first byte is SAMPLE_HEADER (10)");
  const bad = sampleBytes.slice();
  bad[0] = 3; // retired legacy keypoints header
  let threw = false;
  try {
    decodeSample(
      bad.buffer.slice(bad.byteOffset, bad.byteOffset + bad.byteLength) as ArrayBuffer,
      decodeSchema(schemaJson),
    );
  } catch {
    threw = true;
  }
  assert(threw, "decoder rejects wrong first-byte tag");
  console.log("PASS: testFirstByteTags");
}

// ── run ────────────────────────────────────────────────────────────────

testSchemaRoundTrip();
testGoldenSampleDecode();
testRollingWindowEviction();
testRollingWindowSubscriber();
testFirstByteTags();

console.log("\nAll standard-stream decoder tests passed.");
