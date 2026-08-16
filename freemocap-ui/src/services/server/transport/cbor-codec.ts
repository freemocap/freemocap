// transport/cbor-codec.ts
//
// Thin CBOR codec for the message model: decode one message's bytes and
// validate against the Zod union (message-contract.ts). cbor-x decodes CBOR
// byte strings to Uint8Array; we normalize defensively so every byte string is
// an owned Uint8Array (not a view over the input buffer, which the WebSocket
// layer may reuse).
//
// Status: step 1 of the cutover. Nothing consumes this yet.

import { decode } from "cbor-x";
import { parseMessage, type Message } from "./message-contract";

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
  return parseMessage(normalizeValue(decode(bytes)));
}
