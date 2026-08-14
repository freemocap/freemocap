# Stream Schema + Sample (the data contract)

**Describes (types):** `freemocap/core/streaming/standard_stream/` — `stream_schema.py`,
`stream_sample.py`, `coordinate_convention.py`. The **wire framing / encoder / WS** that carries these
lives in [../03-transport/backend-encoder-ws.md](../03-transport/backend-encoder-ws.md) — this doc owns
the *shapes*, that one owns the *transport*.
**Salvage:** [`archive/streaming-compatibility-specs/01-canonical-data-model.md`](../archive/streaming-compatibility-specs/01-canonical-data-model.md),
[`09-standard-stream-protocol.md`](../archive/streaming-compatibility-specs/09-standard-stream-protocol.md),
[`archive/phase-1-work-plans/01-standard-stream-contract.md`](../archive/phase-1-work-plans/01-standard-stream-contract.md),
[`03-canonical-frame-extensions.md`](../archive/phase-1-work-plans/03-canonical-frame-extensions.md).

## What this covers
The LSL-shaped contract: a **schema** (channels, channel groups, joint hierarchy, T-pose, convention,
units, per-subject dimension) sent once + change, then timestamped **samples** per frame.

## Key facts (committed code — verify against the in-flight tweaks before finalizing)
- Schema is built from the composed `StandardHuman` (`StreamSchema.from_standard_human`), keyed to the
  live camera set; carries **measured segment lengths** with a default-then-update lifecycle (anthropometric
  seeds until the estimators converge).
- **Six channel groups** (F1): the segment rotations (world + local) and the keypoint/position groups.
- Samples: binary, `wxyz` rotations, keyed by frame number; golden-byte parity with the TS decoder
  ([../04-ui/ui-integration.md](../04-ui/ui-integration.md)).

## Open / in-flight
`stream_schema.py` / `stream_sample.py` are being actively tweaked ("length seeds"); reconcile before
authoring the final channel table. The per-frame schema-resend behaviour is **B2** in the plan (debounce).

## Reconciliation notes
Counts 60/76; `wxyz`; convention block = the [00-foundation/conventions.md](../00-foundation/conventions.md)
facts, single-sourced (the schema *states* them, doesn't redefine them).
