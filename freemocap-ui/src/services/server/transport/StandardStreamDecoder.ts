// StandardStreamDecoder.ts
//
// TS decoder for the standard-stream wire format. Mirrors EXACTLY:
//   freemocap/core/streaming/standard_stream/stream_schema.py  (stream_schema JSON)
//   freemocap/core/streaming/standard_stream/stream_sample.py  (stream_sample binary)
//
// Binary layout (little-endian, float32):
//   SAMPLE_HEADER (32 B):  message_type u1 @0 · [pad→8] timestamp f8 @8 ·
//                          frame_number i8 @16 · subject_id u4 @24 · num_blocks u4 @28
//   per block: BLOCK_HEADER (32 B): message_type u1 @0 · block_kind u1 @1 ·
//                          dtype_code u1 @2 · cols u1 @3 · camera_id S16 @4 ·
//                          overlay_layer u1 @20 · [pad→24] num_elements u4 @24 ·
//                          data_byte_length u4 @28
//              + BLOCK_DATA (row-major f32, num_elements×cols)
//   SAMPLE_FOOTER (32 B):  mirrors SAMPLE_HEADER
//
// Offsets locked by freemocap/tests/test_standard_stream_contract.py
// (test_header_sizes_are_locked: SAMPLE_HEADER_SIZE==32, BLOCK_HEADER_SIZE==32).
// The golden fixtures under __fixtures__/ are the cross-language parity anchors;
// regenerate them (Python) with:
//   uv run python -m freemocap.tests.streaming_fixtures.regenerate_golden
// a change in the output is a wire-format change.

import {
  ChannelKind,
  MessageType,
  OverlayLayer,
  type DecodedSample,
  type StreamSchema,
  type TypedArrayBlock,
} from "./types";

const CAMERA_ID_BYTES = 16;

export const SAMPLE_HEADER_SIZE = 32;
export const BLOCK_HEADER_SIZE = 32;
export const SAMPLE_FOOTER_SIZE = 32;

// SAMPLE_HEADER / SAMPLE_FOOTER field offsets (align=True numpy dtype).
const HEADER = {
  message_type: 0,
  timestamp: 8,
  frame_number: 16,
  subject_id: 24,
  num_blocks: 28,
} as const;

// BLOCK_HEADER field offsets.
const BLOCK = {
  message_type: 0,
  block_kind: 1,
  dtype_code: 2,
  cols: 3,
  camera_id: 4,
  overlay_layer: 20,
  num_elements: 24,
  data_byte_length: 28,
} as const;

/** Read a fixed-width null-padded ASCII field from a DataView. */
function readAsciiField(
  view: DataView,
  bufferOffset: number,
  fieldOffset: number,
  size: number,
): string {
  const bytes = new Uint8Array(view.buffer, bufferOffset + fieldOffset, size);
  let end = bytes.indexOf(0);
  if (end === -1) end = size;
  let s = "";
  for (let i = 0; i < end; i++) s += String.fromCharCode(bytes[i]);
  return s;
}

/** Parse `stream_schema` JSON text into a StreamSchema. */
export function decodeSchema(json: string): StreamSchema {
  return decodeSchemaObject(JSON.parse(json) as Record<string, any>);
}

/**
 * Normalize an already-parsed `stream_schema` object into a StreamSchema.
 * msgspec encodes enums as integers (IntEnum) and tuples as arrays, so the
 * wire is plain JSON. Only `kind` needs normalization.
 */
const CHANNEL_KINDS: ReadonlySet<number> = new Set<number>(Object.values(ChannelKind).filter((v) => typeof v === "number"));

function normalizeChannelKind(raw: number): ChannelKind {
  if (!CHANNEL_KINDS.has(raw)) {
    throw new Error(`decodeSchema: channel kind out of range (${raw})`);
  }
  return raw as ChannelKind;
}

export function decodeSchemaObject(raw: Record<string, any>): StreamSchema {
  if (raw.message_type !== "stream_schema") {
    throw new Error(`decodeSchema: expected message_type "stream_schema", got ${raw.message_type}`);
  }
  const rawChannels = raw.channels;
  if (!Array.isArray(rawChannels)) {
    throw new Error("decodeSchema: expected \"channels\" to be an array of channel groups");
  }
  const channels = rawChannels.map((group: Record<string, any>) => ({
    ...group,
    kind: normalizeChannelKind(group.kind),
  }));
  return { ...raw, channels } as StreamSchema;
}

/** Returns true if the buffer's first byte is a standard-stream SAMPLE_HEADER. */
export function isStandardStreamSample(buf: ArrayBuffer): boolean {
  if (buf.byteLength < 1) return false;
  return new Uint8Array(buf, 0, 1)[0] === MessageType.SAMPLE_HEADER;
}

/**
 * Decode one `stream_sample` binary buffer into a DecodedSample.
 *
 * Blocks are self-describing (kind/cols/num_elements/camera_id/overlay_layer).
 * Mapping block columns back to channel names is the SchemaRegistry's job, not
 * this decoder's — mirroring decode_sample() on the Python side.
 */
export function decodeSample(buf: ArrayBuffer, schema: StreamSchema): DecodedSample {
  if (buf.byteLength < SAMPLE_HEADER_SIZE + SAMPLE_FOOTER_SIZE) {
    throw new Error(`StandardStreamDecoder: buffer too small (${buf.byteLength} bytes)`);
  }
  const view = new DataView(buf);

  const headerType = view.getUint8(HEADER.message_type);
  if (headerType !== MessageType.SAMPLE_HEADER) {
    throw new Error(`StandardStreamDecoder: bad SAMPLE_HEADER message_type=${headerType}`);
  }
  const timestamp = view.getFloat64(HEADER.timestamp, true);
  const frameNumber = Number(view.getBigInt64(HEADER.frame_number, true));
  const subjectId = view.getUint32(HEADER.subject_id, true);
  const numBlocks = view.getUint32(HEADER.num_blocks, true);

  let cursor = SAMPLE_HEADER_SIZE;
  const blocks: TypedArrayBlock[] = [];

  for (let b = 0; b < numBlocks; b++) {
    if (cursor + BLOCK_HEADER_SIZE > buf.byteLength) {
      throw new Error(`StandardStreamDecoder: block ${b} header runs past end of buffer`);
    }
    const blockView = new DataView(buf, cursor, BLOCK_HEADER_SIZE);
    const blockType = blockView.getUint8(BLOCK.message_type);
    if (blockType !== MessageType.BLOCK_HEADER) {
      throw new Error(`StandardStreamDecoder: block ${b} bad BLOCK_HEADER message_type=${blockType}`);
    }
    const kind = blockView.getUint8(BLOCK.block_kind) as ChannelKind;
    const dtypeCode = blockView.getUint8(BLOCK.dtype_code);
    if (dtypeCode !== 0) {
      throw new Error(`StandardStreamDecoder: block ${b} unsupported dtype_code=${dtypeCode}`);
    }
    const cols = blockView.getUint8(BLOCK.cols);
    const cameraId = readAsciiField(blockView, cursor, BLOCK.camera_id, CAMERA_ID_BYTES);
    const overlayLayer = blockView.getUint8(BLOCK.overlay_layer) as OverlayLayer;
    const numElements = blockView.getUint32(BLOCK.num_elements, true);
    const dataByteLength = blockView.getUint32(BLOCK.data_byte_length, true);

    cursor += BLOCK_HEADER_SIZE;
    const expectedBytes = numElements * cols * 4; // float32
    if (dataByteLength !== expectedBytes) {
      throw new Error(
        `StandardStreamDecoder: block ${b} data_byte_length=${dataByteLength} != ${expectedBytes} (num_elements×cols×4)`,
      );
    }
    if (cursor + dataByteLength > buf.byteLength) {
      throw new Error(`StandardStreamDecoder: block ${b} data runs past end of buffer`);
    }

    const data = new Float32Array(buf, cursor, numElements * cols);
    cursor += dataByteLength;

    // Cross-check the block kind against the schema by KIND, not by position.
    // Blocks are self-describing; the schema is the authority on which kinds
    // are declared. A block whose kind no group declares is wire corruption.
    const declared = schema.channels.find((g) => g.kind === kind);
    if (!declared) {
      throw new Error(
        `StandardStreamDecoder: block ${b} kind=${kind} is not declared by any schema channel group`,
      );
    }

    blocks.push({ kind, data, numElements, cols, cameraId, overlayLayer });
  }

  if (cursor + SAMPLE_FOOTER_SIZE > buf.byteLength) {
    throw new Error("StandardStreamDecoder: footer runs past end of buffer");
  }
  const footerView = new DataView(buf, cursor, SAMPLE_FOOTER_SIZE);
  const footerType = footerView.getUint8(HEADER.message_type);
  if (footerType !== MessageType.SAMPLE_FOOTER) {
    throw new Error(`StandardStreamDecoder: bad SAMPLE_FOOTER message_type=${footerType}`);
  }
  const footerNumBlocks = footerView.getUint32(HEADER.num_blocks, true);
  if (footerNumBlocks !== numBlocks) {
    throw new Error(`StandardStreamDecoder: footer/header num_blocks mismatch`);
  }
  cursor += SAMPLE_FOOTER_SIZE;
  if (cursor !== buf.byteLength) {
    throw new Error(`StandardStreamDecoder: trailing bytes (${cursor} of ${buf.byteLength} consumed)`);
  }

  return { timestamp, frameNumber, subjectId, blocks };
}
