# Standard-Stream Protocol (the wire framing)

**Describes:** the wire contract — schema-once-then-samples — as framed by the send path
([backend-encoder-ws.md](backend-encoder-ws.md)) and consumed by the UI decoder
([../04-ui/ui-integration.md](../04-ui/ui-integration.md)). The **types** live in
[../01-data-model/stream-contract.md](../01-data-model/stream-contract.md); this doc owns the *framing*.

## What this covers
The on-wire behaviour: a text **schema** frame on connect (and on every data-model change), then binary
**sample** frames — one per frame, each carrying every block the current schema declares (images,
overlays, and reconstruction together).

## Framing

- **First-byte demux.** `SAMPLE_HEADER = 10`, `BLOCK_HEADER = 11`, `SAMPLE_FOOTER = 12` (distinct from
  SkellyCam's legacy image protocol 0/1/2). A receiver demuxes on byte 0; a JSON text frame is the schema.
- **Sample layout** (little-endian, sizes locked by a test so the decoder stays in sync):
  `SAMPLE_HEADER` + N × (`BLOCK_HEADER` + `BLOCK_DATA`) + `SAMPLE_FOOTER`. Blocks are **self-describing**:
  the block header carries `block_kind`, `dtype_code`, `cols`, `camera_id`, `overlay_layer`,
  `num_elements`, and `data_byte_length`. Consumers resolve blocks **by kind** against the schema.
- **Block dtypes.** `dtype_code`: `FLOAT32 = 0` (all point / rotation / scalar blocks) and `UINT8 = 1`
  (raw bytes — the `IMAGE_JPEG` block). `data_byte_length` is authoritative for a block's data size; the
  `num_elements × cols × 4` identity holds only for float32 blocks. The header layout (and its locked
  sizes) is unchanged by adding uint8 — `dtype_code` and `data_byte_length` already exist.
- **Names live in the schema, not the sample.** Mapping a block's rows back to names is the schema's job.

## Schema lifecycle (single source of truth for the data model)

- The schema is sent first, and **resent whenever the data model changes** — a realtime pipeline starting
  or stopping, the detector changing, the camera set changing. Detection is a single **composite
  signature** over the active producers (see below), not a set of per-cause checks.
- The consumer **replaces** its schema on each arrival and decodes subsequent samples against it. Because
  the send path is single-writer and sends rebuild→schema→samples in order, a sample never arrives before
  the schema it conforms to. "camera-only" and "camera + reconstruction" are just two schemas.

## Producer-composed content

The schema's channel groups and each sample's blocks are composed from **channel producers** — one per
coherent data slice (image, keypoints, segments, overlays, derived). Each producer declares its groups +
static schema metadata, a structural `signature()` (the change-detection input), and a per-frame `fill()`.
The schema is the union of active producers' groups; a sample is the concatenation of their filled blocks.
A new data type is a new producer — the framing and demux do not change. Full model:
[../01-data-model/stream-contract.md](../01-data-model/stream-contract.md#the-producer-model).

## Flow control

**Newest-wins, drop-stale. No acks gate the stream.** The server always sends the freshest frame; a slow
client receives fewer, newer samples. There is no ack window and no in-flight bound. The upstream
`frameAcknowledgment` message survives only to carry `displayImageSizes` (SkellyCam downscaling) — it does
not gate sending.

## Reconciliation notes
Single-source the convention block from [../00-foundation/conventions.md](../00-foundation/conventions.md).
Third-party protocol conformance (LSL/VMC) is [hub-and-adapters.md](hub-and-adapters.md); those adapters
consume the reconstruction channel groups and ignore `IMAGE_JPEG`.
