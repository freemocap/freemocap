// transport/cbor-codec.ts
//
// Thin CBOR codec for the message model: decode one message's bytes and
// validate against the Zod union (message-contract.ts). cbor-x decodes CBOR
// byte strings to Uint8Array; we normalize defensively so every byte string is
// an owned Uint8Array (not a view over the input buffer, which the WebSocket
// layer may reuse).
//
// Status: consumed by TransportService (the kind-keyed dispatcher).

import { decode } from "cbor-x";
import { parseMessage, FrameMessageSchema, CURRENT_VERSION, type Message } from "./message-contract";
import { snapshotEqual } from './snapshot-equality';
import { equalBytes } from './content-equality';

function toOwnedBytes(value: unknown): Uint8Array | null {
  if (value instanceof Uint8Array) return new Uint8Array(value);
  if (value instanceof ArrayBuffer) return new Uint8Array(value);
  return null;
}

function normalizeValue(value: unknown): unknown {
  const bytes = toOwnedBytes(value);
  if (bytes !== null) return bytes;
  if (Array.isArray(value)) return value.map(normalizeValue);
  if (value !== null && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [key, v] of Object.entries(value as Record<string, unknown>)) {
      out[key] = normalizeValue(v);
    }
    return out;
  }
  return value;
}

/** Decode one CBOR message's bytes and validate against the union.
 *  Returns null for an unknown kind or an unsupported version (fail soft —
 *  the dispatcher logs once + skips). Throws for a malformed known-kind
 *  message at the current version (fail loud — a defect). */
export function decodeMessage(bytes: Uint8Array): Message | null {
  return new MessageDecoder().decode(bytes);
}

const dynamicFrameSchema = FrameMessageSchema.omit({models: true, cameras: true, convention: true});
type StaticField = 'models' | 'cameras' | 'convention';
const staticFields: readonly StaticField[] = ['models', 'cameras', 'convention'];
function freezeMetadata(value: unknown): unknown {
  if (value !== null && typeof value === 'object') {
    for (const child of Object.values(value)) freezeMetadata(child);
    Object.freeze(value);
  }
  return value;
}

/** Connection-owned caches; every packet still contains complete, independently usable data. */
export class MessageDecoder {
  private readonly metadata = new Map<StaticField, {raw: unknown; validated: unknown}>();
  private readonly numericalBytes: Uint8Array[] = [];
  reset(): void {this.metadata.clear(); this.numericalBytes.length = 0;}

  decode(bytes: Uint8Array): Message | null {
    const raw = decode(bytes);
    if (raw?.kind !== 'frame' || raw?.version !== CURRENT_VERSION) return parseMessage(normalizeValue(raw));
    // Metadata is compared before repeated validation/cloning; changed contents are
    // always validated, even when the sender leaves model_sequence unchanged.
    const retained: Partial<Record<StaticField, unknown>> = {};
    const updates = new Map<StaticField, {raw: unknown; validated: unknown}>();
    for (const key of staticFields) {
      const previous = this.metadata.get(key);
      const entry = previous && snapshotEqual(previous.raw, raw[key]) ? previous
        : {raw: raw[key], validated: freezeMetadata(FrameMessageSchema.shape[key].parse(raw[key]))};
      retained[key] = entry.validated;
      updates.set(key, entry);
    }
    let byteIndex = 0;
    const ownedBytes: Uint8Array[] = [];
    const own = (value: unknown): unknown => {
      if (value instanceof Uint8Array) {
        const previous = this.numericalBytes[byteIndex++];
        const data = previous && equalBytes(value, previous) ? previous : new Uint8Array(value);
        ownedBytes.push(data);
        return data;
      }
      if (Array.isArray(value)) {for (let i = 0; i < value.length; i++) value[i] = own(value[i]);}
      else if (value !== null && typeof value === 'object') {
        for (const key of Object.keys(value)) (value as Record<string, unknown>)[key] = own((value as Record<string, unknown>)[key]);
      }
      return value;
    };
    // The decoded object tree is private. Own numerical bytes without rebuilding
    // that tree; never retain unaligned views into the caller's encoded packet.
    for (const key of Object.keys(raw)) {
      if (staticFields.includes(key as StaticField)) continue;
      // Images are handed to transfer consumers; never cache or share their ownership.
      raw[key] = key === 'image' && raw[key] instanceof Uint8Array ? new Uint8Array(raw[key]) : own(raw[key]);
    }
    const dynamic = dynamicFrameSchema.parse(raw);
    for (const [key, entry] of updates) this.metadata.set(key, entry);
    this.numericalBytes.splice(0, this.numericalBytes.length, ...ownedBytes);
    return {...dynamic, ...retained} as Message;
  }
}
