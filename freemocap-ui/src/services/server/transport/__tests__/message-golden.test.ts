// transport/__tests__/message-golden.test.ts
//
// Step 1 — cross-language parity for the message-model CBOR codec.
// Framework-free via esbuild + node (Vitest is NOT installed), matching
// standard-stream-decoder.test.ts.
//
// Run (from freemocap-ui):
//   node_modules/.bin/esbuild src/services/server/transport/__tests__/message-golden.test.ts --bundle --platform=node --format=esm --outfile=.tmp-message-golden-test.mjs && node .tmp-message-golden-test.mjs
//
// The golden fixtures (message_{convention,model,frame}_golden.bin) are produced
// by freemocap/tests/streaming_fixtures/regenerate_message_golden.py (cbor2) and
// must decode to the values that script pinned. A value mismatch OR a float
// precision loss (e.g. a float16 downcast) is a contract defect.

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { decodeMessage } from "../cbor-codec";
import { encode } from "cbor-x";
import type { Message } from "../message-contract";

function assert(cond: unknown, message: string): asserts cond {
  if (!cond) throw new Error("ASSERT: " + message);
}
function assertEq<T>(actual: T, expected: T, message: string): void {
  if (actual !== expected) {
    throw new Error(message + " (expected " + String(expected) + ", got " + String(actual) + ")");
  }
}
function assertClose(actual: number, expected: number, eps: number, message: string): void {
  if (Math.abs(actual - expected) > eps) {
    throw new Error(message + " (expected ~" + expected + ", got " + actual + ")");
  }
}

const FIXTURES = join(process.cwd(), "src", "services", "server", "transport", "__fixtures__");
const fixture = (name: string): Uint8Array =>
  new Uint8Array(readFileSync(join(FIXTURES, name)));

function expectMessage<T extends Message["kind"]>(name: string, kind: T): Extract<Message, { kind: T }> {
  const msg = decodeMessage(fixture(name));
  assert(msg !== null, name + " decodes to a message");
  assertEq(msg!.kind, kind, name + " kind");
  return msg as Extract<Message, { kind: T }>;
}

function toFloat32Array(bytes: Uint8Array): number[] {
  return Array.from(new Float32Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 4));
}

// ── convention ─────────────────────────────────────────────────────────
{
  const m = expectMessage("message_convention_golden.bin", "convention");
  assertEq(m.version, 0, "convention version");
  assertEq(m.sequence, 0, "convention sequence");
  assertEq(m.units, "mm", "units");
  assertEq(m.handedness, "right", "handedness");
  assertEq(m.up_axis, "+z", "up_axis");
  assertEq(m.forward_axis, "+x", "forward_axis");
  assertEq(m.rotation_frame, "local", "rotation_frame");
  assertEq(m.rotation_form, "quaternion", "rotation_form");
  console.log("PASS: convention");
}

// ── model ─────────────────────────────────────────────────────────────
{
  const m = expectMessage("message_model_golden.bin", "model");
  assertEq(m.segments.length, 2, "two segments");
  assertEq(m.segments[0], "hips", "segment 0");
  assertEq(m.segments[1], "spine", "segment 1");
  assertEq(m.axes["hips"], "y", "hips axis");
  assertEq(m.axes["spine"], "y", "spine axis");
  assertEq(m.lengths["hips"], 100, "hips length");
  assertEq(m.lengths["spine"], 200, "spine length");
  assertEq(m.connections.length, 1, "one connection");
  assertEq(m.connections[0][0], "hips", "connection proximal");
  assertEq(m.connections[0][1], "spine", "connection distal");
  assertEq(m.parents["hips"], null, "hips parent null");
  assertEq(m.parents["spine"], "hips", "spine parent");
  assertEq(m.hierarchy["hips"][0], "spine", "hips child");
  assertEq(m.hierarchy["spine"].length, 0, "spine leaf");
  assertEq(m.orientations["hips"][0], 1, "hips orientation w");
  // Non-exact float pins "no float16 downcast" on scalar floats.
  assertClose(m.orientations["spine"][0], 0.7071067811865476, 1e-12, "spine orientation x (float64)");
  assertClose(m.orientations["spine"][3], 0.7071067811865476, 1e-12, "spine orientation z (float64)");
  assertEq(m.rest_positions["hips"][2], 0, "hips rest z");
  assertEq(m.rest_positions["spine"][2], 100, "spine rest z");
  console.log("PASS: model");
}

// ── frame ─────────────────────────────────────────────────────────────
{
  const m = expectMessage("message_frame_golden.bin", "frame");
  assertEq(m.frame_number, 99, "frame_number");
  assertEq(m.timestamp, 1.5, "timestamp");
  assertEq(m.subjects.length, 1, "one subject");
  assertEq(m.subjects[0].subject_id, 0, "subject_id");
  assertEq(m.subjects[0].channels.length, 2, "two channels");

  const seg = m.subjects[0].channels[0];
  assertEq(seg.kind, "SEGMENT_ORIGINS", "channel 0 kind");
  assertEq(seg.names.length, 2, "channel 0 names");
  assertEq(seg.columns.length, 3, "channel 0 columns");
  const segData = toFloat32Array(seg.data);
  assertEq(segData.length, 6, "channel 0 data length (2x3)");
  assertEq(segData[0], 0, "channel 0 data[0]");
  assertEq(segData[5], 100, "channel 0 data[5]");

  const rot = m.subjects[0].channels[1];
  assertEq(rot.kind, "ROTATIONS_WORLD", "channel 1 kind");
  assertEq(rot.columns.length, 4, "channel 1 columns");
  const rotData = toFloat32Array(rot.data);
  assertEq(rotData.length, 8, "channel 1 data length (2x4)");
  assertEq(rotData[0], 1, "channel 1 data[0]");
  assertEq(rotData[7], 1, "channel 1 data[7]");

  assert(m.image !== undefined, "image present");
  assertEq(m.image![0], 0xff, "image byte 0");
  assertEq(m.image![1], 0xd8, "image byte 1");
  assertEq(m.image![2], 0xff, "image byte 2");
  console.log("PASS: frame");
}

// ── fail-soft: unknown kind / unsupported version ─────────────────────
{
  const unknown = decodeMessage(encode({ kind: "unknown_kind", version: 0, timestamp: 0, sequence: 0 }));
  assertEq(unknown, null, "unknown kind -> null");
  const future = decodeMessage(encode({ kind: "convention", version: 999, timestamp: 0, sequence: 0 }));
  assertEq(future, null, "unsupported version -> null");
  console.log("PASS: fail-soft (unknown kind / unsupported version)");
}

console.log("ALL MESSAGE-GOLDEN ASSERTIONS PASSED");
