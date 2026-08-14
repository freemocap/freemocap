# Standard-Stream Protocol (the wire framing)

**Describes:** the wire contract — schema-once-then-samples, acks — as framed by the send path
([backend-encoder-ws.md](backend-encoder-ws.md)) and consumed by the UI decoder
([../04-ui/ui-integration.md](../04-ui/ui-integration.md)). The **types** live in
[../01-data-model/stream-contract.md](../01-data-model/stream-contract.md); this doc owns the *framing*.
**Salvage:** [`archive/streaming-compatibility-specs/09-standard-stream-protocol.md`](../archive/streaming-compatibility-specs/09-standard-stream-protocol.md).

## What this covers
The precise on-wire behaviour: a text **schema** frame on connect (and on schema change), then binary
**sample** frames per solved frame; the client **acks** frame numbers to free the send window.

## Key facts (committed code — golden-byte tested)
- Schema: JSON text, sent first; re-sent on camera-set change or material segment-length change.
- Sample: binary, `wxyz` rotations, indexed against the last schema; keyed by frame number.
- Ack: client → server, frame number (also carries display image sizes). Frees the backpressure window.
- Golden-byte parity between the Python encoder and the TS decoder is a contract test.

## Open
Ack-window semantics are being fixed (**B1**). Third-party protocol conformance (LSL/VMC) is
[hub-and-adapters.md](hub-and-adapters.md).

> **Dual-channel decision (2026-08-14, settled):** the point data splits into tracker-named
> **`KEYPOINTS_3D`** (the measured keypoints) + a new **`LANDMARKS_3D`** (the 76 hydrated landmarks) —
> see the channel table in [../01-data-model/stream-contract.md](../01-data-model/stream-contract.md).
> Landed in Sweep 3; until then `KEYPOINTS_3D` carries the landmark names.

## Reconciliation notes
Single-source the convention block from [../00-foundation/conventions.md](../00-foundation/conventions.md).
