# Streaming Hub + Protocol Adapters (LSL / VMC)

> **Scaffold (2026-08-14) — needs a source-read pass before full prose.** I have not yet read the
> adapter/bridge code in depth; the key facts below are from the archived spec + the `standard_stream`
> module list. Author fully after reading the sources.

**Describes (target):** `freemocap/core/streaming/standard_stream/` — `lsl_bridge.py`,
`coordinate_convention.py`, and the (planned) `StreamingManager` + adapter contract; the transports vs.
adapters split.
**Salvage:** [`archive/streaming-compatibility-specs/02-streaming-hub.md`](../archive/streaming-compatibility-specs/02-streaming-hub.md),
[`03-emitters.md`](../archive/streaming-compatibility-specs/03-emitters.md).

## What this covers
Fanning the one standard stream out to third-party motion-capture protocols (LSL, VMC, …): the adapter
contract, the LSL route, the VMC adapter, and the "start idle / ephemeral" lifecycle.

## To capture when authored
- Adapter contract (what an adapter declares it emits — positive definition only).
- The LSL pass-through route + coordinate-convention handling per target.
- Transports (carry the standard stream) vs. adapters (translate to a foreign protocol).

## Reconciliation notes
"Adapter" not "emitter" (title drift in the archive). Convention-per-target single-sourced from
[../00-foundation/conventions.md](../00-foundation/conventions.md).
