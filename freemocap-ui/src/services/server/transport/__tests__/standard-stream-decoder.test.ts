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
import { ChannelKind, DtypeCode, OverlayLayer, type StreamSchema } from "../types";

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
  assertEq(schema.channels.length, 10, "ten channel groups");
  assertEq(schema.channels[0].kind, ChannelKind.KEYPOINTS_3D, "channel 0 kind");
  assertEq(schema.channels[1].kind, ChannelKind.LANDMARKS_3D, "channel 1 kind");
  assertEq(schema.channels[2].kind, ChannelKind.SEGMENT_ORIGINS, "channel 2 kind");
  assertEq(schema.channels[3].kind, ChannelKind.ROTATIONS_LOCAL, "channel 3 kind");
  assertEq(schema.channels[4].kind, ChannelKind.ROTATIONS_WORLD, "channel 4 kind");
  assertEq(schema.channels[5].kind, ChannelKind.SEGMENT_LENGTHS, "channel 5 kind");
  assertEq(schema.channels[6].kind, ChannelKind.OVERLAY_2D, "channel 6 kind");
  assertEq(schema.channels[7].kind, ChannelKind.OVERLAY_REPROJECTIONS, "channel 7 kind");
  assertEq(schema.channels[8].kind, ChannelKind.DERIVED_POINTS, "channel 8 kind");
  assertEq(schema.channels[9].kind, ChannelKind.IMAGE_JPEG, "channel 9 kind");
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
  assertEq(sample.blocks.length, 12, "10 groups, overlay kinds ×2 cameras = 12 blocks");

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

  // Overlays — one DETECTIONS + one REPROJECTIONS block per camera
  assertEq(resolved.overlays.length, 4, "four overlay blocks (2 layers × 2 cams)");
  const detections = resolved.overlays.filter((o) => o.layer === OverlayLayer.DETECTIONS);
  const reprojections = resolved.overlays.filter((o) => o.layer === OverlayLayer.REPROJECTIONS);
  assertEq(detections.length, 2, "two DETECTIONS blocks");
  assertEq(reprojections.length, 2, "two REPROJECTIONS blocks");

  const byCam = new Map(detections.map((o) => [o.cameraId, o]));
  const cam0 = byCam.get("cam-0")!;
  const noseIdx = cam0.names.indexOf("nose");
  assert(noseIdx !== -1, "nose in overlay names");
  assertEq(cam0.data[noseIdx * 3], 320.0, "cam-0 nose.x");
  assertEq(cam0.data[noseIdx * 3 + 1], 240.0, "cam-0 nose.y");

  // REPROJECTIONS names are the 60 segment names.
  assertEq(reprojections[0].names.length, 60, "60 segment names in reprojections");
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

// ── 6. uint8 (IMAGE_JPEG) block + misaligned-float robustness ───────────

interface RawBlock {
  kind: ChannelKind;
  dtypeCode: DtypeCode;
  cols: number;
  numElements: number;
  data: Uint8Array;
}

/** Build a minimal standard-stream sample buffer by hand (there is no TS
 *  encoder). Mirrors the 32-byte header layout in StandardStreamDecoder. */
function buildSample(frameNumber: number, blocks: RawBlock[]): ArrayBuffer {
  let total = 32 + 32; // SAMPLE_HEADER + SAMPLE_FOOTER
  for (const b of blocks) total += 32 + b.data.byteLength;
  const buf = new ArrayBuffer(total);
  const view = new DataView(buf);
  view.setUint8(0, 10); // SAMPLE_HEADER
  view.setFloat64(8, 0, true);
  view.setBigInt64(16, BigInt(frameNumber), true);
  view.setUint32(24, 0, true);
  view.setUint32(28, blocks.length, true);
  let cur = 32;
  for (const b of blocks) {
    view.setUint8(cur + 0, 11); // BLOCK_HEADER
    view.setUint8(cur + 1, b.kind);
    view.setUint8(cur + 2, b.dtypeCode);
    view.setUint8(cur + 3, b.cols);
    view.setUint32(cur + 24, b.numElements, true);
    view.setUint32(cur + 28, b.data.byteLength, true);
    cur += 32;
    new Uint8Array(buf, cur, b.data.byteLength).set(b.data);
    cur += b.data.byteLength;
  }
  view.setUint8(cur + 0, 12); // SAMPLE_FOOTER
  view.setFloat64(cur + 8, 0, true);
  view.setBigInt64(cur + 16, BigInt(frameNumber), true);
  view.setUint32(cur + 24, 0, true);
  view.setUint32(cur + 28, blocks.length, true);
  return buf;
}

const uint8TestSchema = {
  stream_id: "t",
  stream_name: "t",
  coordinate_convention: {
    units: "mm", handedness: "right", up_axis: "+z",
    forward_axis: "+x", rotation_frame: "local", rotation_form: "quaternion",
  },
  channels: [
    { kind: ChannelKind.SEGMENT_LENGTHS, names: ["hips"], columns: ["length_mm"], units: "mm" },
    { kind: ChannelKind.IMAGE_JPEG, names: ["image"], columns: ["jpeg_bytes"], units: "jpeg" },
  ],
  connections: [], joint_hierarchy: {}, segment_parents: {}, rest_pose: null,
  segment_lengths: {}, camera_ids: [], camera_image_sizes: {}, max_persons: 1,
  message_type: "stream_schema",
} as unknown as StreamSchema;

function testUint8AndMisalignedFloatDecode(): void {
  // An IMAGE_JPEG uint8 block of ODD length (3), followed by a float32
  // SEGMENT_LENGTHS block whose data therefore lands on a non-4-aligned offset
  // → exercises both the uint8 decode path and the alignment-safe float copy.
  const jpeg = new Uint8Array([0xff, 0xd8, 0xff]);
  const lenBytes = new Uint8Array(4);
  new DataView(lenBytes.buffer).setFloat32(0, 42.5, true);
  const buf = buildSample(99, [
    { kind: ChannelKind.IMAGE_JPEG, dtypeCode: DtypeCode.UINT8, cols: 1, numElements: 3, data: jpeg },
    { kind: ChannelKind.SEGMENT_LENGTHS, dtypeCode: DtypeCode.FLOAT32, cols: 1, numElements: 1, data: lenBytes },
  ]);
  const sample = decodeSample(buf, uint8TestSchema);
  assertEq(sample.frameNumber, 99, "image-sample frame number");
  assertEq(sample.blocks.length, 2, "two blocks");

  const img = sample.blocks[0];
  assertEq(img.kind, ChannelKind.IMAGE_JPEG, "block0 kind IMAGE_JPEG");
  assertEq(img.dtypeCode, DtypeCode.UINT8, "block0 dtype UINT8");
  assert(img.data instanceof Uint8Array, "block0 data is Uint8Array");
  assertEq(img.data.length, 3, "block0 byte length 3");
  assertEq(img.data[0], 0xff, "block0 byte 0");
  assertEq(img.data[1], 0xd8, "block0 byte 1");

  const seg = sample.blocks[1];
  assertEq(seg.kind, ChannelKind.SEGMENT_LENGTHS, "block1 kind SEGMENT_LENGTHS");
  assert(seg.data instanceof Float32Array, "block1 data is Float32Array (copied when misaligned)");
  assertClose(seg.data[0], 42.5, 1e-6, "block1 float value survives misalignment");
  console.log("PASS: testUint8AndMisalignedFloatDecode");
}

// ── run ────────────────────────────────────────────────────────────────

testSchemaRoundTrip();
testGoldenSampleDecode();
testRollingWindowEviction();
testRollingWindowSubscriber();
testFirstByteTags();
testUint8AndMisalignedFloatDecode();

console.log("\nAll standard-stream decoder tests passed.");
