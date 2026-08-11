# FMC-WS-1 — Standard-Stream Contract (types + codecs)

> The linchpin: the wire contract as code, **unit-testable in isolation, with no pipeline or WebSocket wiring**
> (that is FMC-WS-2). Realizes [09 — Standard Stream Protocol](../09-standard-stream-protocol.md).
> **Status: ✅ implemented — `freemocap/core/streaming/standard_stream/`; 8 contract tests green.**

## Goal

Define `stream_schema` (StreamInfo) + `stream_sample` (binary) as Python types with encode/decode codecs, plus
golden-byte + round-trip tests. Nothing behavioral changes; existing paths keep working untouched. FMC-WS-2/3/4/5
build against these types.

## Where it lives (decided)
        
A new module `freemocap/core/streaming/standard_stream/`:
- `stream_schema.py` — the schema (StreamInfo) types + JSON codec.
- `stream_sample.py` — the sample wire format (numpy dtypes) + binary encode/decode.
- `coordinate_convention.py` — the `CoordinateConvention` value type ([07](../07-coordinate-conventions.md)).
- `lsl_bridge.py` — schema→StreamInfo channels + sample→flat-vector (pass-through parity).
- `__init__.py` — public API.

Transport-agnostic (the WS relay *and* the LSL route consume it). **Schema uses `msgspec`.** SkellyForge can
share these types for the disk sidecar / tidy format ([10](../10-serialization-and-tidy-format.md)) if it makes
sense — we can shuffle later.

## What it evolves from (real files)

| Today | Becomes |
|---|---|
| `api/websocket/tracker_schema_message.py` — `TrackerSchemasMessage` / `TrackerDefinition` `{name, tracked_points, connections}` | the richer `stream_schema` |
| `api/websocket/binary_keypoints_protocol.py` — numpy-dtype header/block/footer framing | the `stream_sample` framing |
| `core/viz/frontend_keypoints_serializer.py::build_keypoints_payload` | the sample **encoder** |
| `core/viz/frontend_payload.py::FrontendPayload` (CoM/xcom) | a `POINTS` block (derived points) |
| `FrontendPayload` 2D overlays (`skeleton_overlays`, per camera) | `OVERLAY_2D` blocks (per camera, **in** the stream) |

## The schema — `schema.py`

`msgspec.Struct` (matches today's `TrackerSchemasMessage`). Fields:
- `stream_id: str` (unique), `stream_name: str` (label — not unique)
- `coordinate_convention: CoordinateConvention` (units, handedness, up/forward axis, rotation frame+form)
- `channels: list[ChannelGroup]` — **ordered**; each `{kind: POINTS|ROTATIONS|OVERLAY_2D, names: [...], columns: [...], units: str}`
- `connections: list[tuple[str,str]]`, `joint_hierarchy: dict[str, list[str]]`
- `rest_pose` — T-pose landmark positions + per-segment reference orientations (identity == rest)
- `sample_layout` — derived from `channels` (block order, dtype, cols) so the decoder needs no per-frame names

Names are **landmarks** (canonical); convention/hierarchy/rest-pose sourced from `AnatomicalStructure`
([13](../13-tracker-to-canonical-mapping.md), [12](../12-standard-human-model.md)).

## The sample — `sample.py`

Evolve the aligned-numpy-dtype framing from `binary_keypoints_protocol.py`:
```
SAMPLE_HEADER   message_type u1 · timestamp f8 (primary) · frame_number i8 · subject_id · num_blocks u4
per block:      BLOCK_HEADER (message_type u1 · block_kind u1 [POINTS|ROTATIONS|OVERLAY_2D] ·
                dtype u1=FLOAT32 · cols u1 · camera_id S16 (empty unless OVERLAY_2D) · num_elements u4 ·
                data_byte_length u4) + BLOCK_DATA (row-major float32, NO names)
SAMPLE_FOOTER   mirrors header
```
- POINTS cols = `x, y, z, reprojection_error`; ROTATIONS cols = `w, x, y, z` (matches bs/); missing → `NaN`.
- **OVERLAY_2D** — the per-camera 2D projection of the tracked landmarks (`x, y, visibility`), **one block per
  camera** (keyed by `camera_id`), matching the 3D data but 2D-only. Camera *images* stay a separate stream (FMC-WS-2).
- **Drop `embed_names`** — names live in the schema.

## Codecs

- `encode_schema(schema) -> bytes` (JSON) / `decode_schema(bytes) -> schema`
- `encode_sample(values, layout) -> bytes` / `decode_sample(bytes, schema) -> dict[block, ndarray]`
- LSL helpers (thin, for FMC-WS-5 / the LSL route): `schema_to_streaminfo_channels(schema)`,
  `sample_to_flat_vector(sample)` — verify the pass-through parity.

## Task checklist

1. [x] `CoordinateConvention` type + canonical default (mm / right / +Z; forward-axis `TBD`) — `coordinate_convention.py`.
2. [x] Schema types + JSON codec — `stream_schema.py` (`StreamSchema`, `ChannelGroup`, `RestPose`, `encode/decode_schema`).
3. [x] Sample dtypes + `encode_sample` (dropped `embed_names`; added timestamp / subject / rotations / `OVERLAY_2D`) — `stream_sample.py`.
4. [x] `decode_sample` + `decode_schema`.
5. [x] Contract guards: header-size lock (32/28), encode determinism, full round-trip. *(A frozen byte-golden
       fixture can be captured later for cross-repo/TS parity — FMC-WS-4.)*
6. [x] Module docstrings as the SSOT for the wire contract (link [09](../09-standard-stream-protocol.md)).

## Tests (the FMC-WS-6 slice for FMC-WS-1)

- `test_schema_roundtrip` — encode→decode reconstructs channels / hierarchy / rest-pose / convention.
- `test_sample_golden_bytes` — a fixed frame → exact expected bytes.
- `test_sample_roundtrip` — reconstruct values incl. `w,x,y,z` order + NaN-missing.
- `test_lsl_flatten_parity` — sample blocks flatten to the StreamInfo channel order.

## Explicitly NOT in FMC-WS-1

No `AggregationNodeOutputMessage` changes (FMC-WS-3), no WebSocket wiring (FMC-WS-2), no UI (FMC-WS-4), no rotation
*values* (FMC-WS-5). Pure contract + codecs.

## Decisions (resolved)

- **Module:** `core/streaming/standard_stream/`. **Schema:** `msgspec`.
- **SkellyForge type-sharing:** do what makes sense; shuffle later if needed. 
