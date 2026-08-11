# Phase 1 — The LSL-Shaped Standard Stream · Work Plans

> Transition from Phase 0 (spec) to Phase 1 (build). This subfolder holds **increasingly specific** work plans
> for Phase 1. **No code is written until the super-specific `NN-<workstream>.md` plan is agreed.**
> Parent spec: [09](../09-standard-stream-protocol.md), [06](../06-backend-refactor-and-cleanup.md),
> [05](../05-ui-integration-and-refactor.md), [01](../01-canonical-data-model.md).

## What Phase 1 delivers (definition of done)

FreeMoCap's own realtime stream is reshaped into the **LSL-shaped standard stream** — a `stream_schema` sent
once + timestamped `stream_sample`s — and the UI consumes it. Real end-to-end: the WebSocket send path
produces it, the UI decodes it, and it is the same shape the LSL route + adapters reuse later. **Image data
stays a separate stream** (linked by frame number).

Phase 1 is done when:
- The standard-stream **contract** (schema + sample) exists as code + codecs, with golden + round-trip tests.
- The **backend** produces schema + samples from the canonical frame (WS send-path reshaped).
- The **canonical frame** carries convention (schema), a subject dimension, confidence/error, and **declared**
  rotation channels.
- The **UI** consumes the standard stream via an extracted connection/transport service (the wedge).
- Rotations are either declared-NaN or populated live — see the [sequencing decision](#key-sequencing-decision-needs-a-call).

## Workstreams

| WS | Scope | Realizes | Depends on |
|---|---|---|---|
| **WS-1 — Standard-stream contract** | schema + sample **types + wire codecs**, no wiring yet | [09](../09-standard-stream-protocol.md) | — (linchpin) |
| **WS-2 — Backend encoder + WS reshape** | produce schema/samples from the canonical frame; reshape `websocket_server.py` send path | [06](../06-backend-refactor-and-cleanup.md) | WS-1, WS-3 |
| **WS-3 — Canonical-frame extensions** | convention-in-schema, subject dimension, confidence/error, rotation-channel declaration | [01](../01-canonical-data-model.md) | WS-1 |
| **WS-4 — UI wedge + consumption** | extract connection/transport service; decode schema+samples → 3D viewport | [05](../05-ui-integration-and-refactor.md) | WS-1 |
| **WS-5 — Kinematics engine fold-in → rotations** | copy/adapt `bs/kinematics_core` into SkellyForge; standard-human rig; live per-segment quaternions → fill rotation channels | [11](../11-kinematics-fold-in.md), [12](../12-standard-human-model.md), [13](../13-tracker-to-canonical-mapping.md) | WS-1 (channel) |
| **WS-6 — Tests & verification** | golden bytes, round-trip, LSL-model parity, UI decode parity | [08](../08-testing-strategy.md) | threads all |

## Dependency graph & sequence

```
WS-1 (contract) ──┬──▶ WS-3 (frame ext) ──▶ WS-2 (encoder + WS reshape) ──▶ WS-4 (UI consume)
                  └──▶ WS-4 can build against the fixed contract in parallel
WS-5 (kinematics fold-in) ── parallel track ──▶ fills the rotation channels WS-3 declared
WS-6 (tests) ── throughout
```

Recommended order: **WS-1 → WS-3 → WS-2 → WS-4**, with **WS-5** parallel and **WS-6** continuous.

## Key sequencing decision — DECIDED: (A) positions-first

Phase 1 ships the stream reshape with rotation channels **declared but NaN**; **WS-5** (the large kinematics
fold-in + standard-human rig) lands live rotations into those channels as a **parallel track**. This keeps the
slice unblocked and proves the whole pipeline fast; VMC (which needs rotations) waits for WS-5. *(Option B —
rotations on the Phase-1 critical path — was rejected.)*

## Plan hierarchy convention

- `README.md` (this) — decomposition + sequence + definition of done.
- `NN-<workstream>.md` — one **super-specific** plan per workstream: exact files to create/evolve, concrete
  types + wire format, an ordered task checklist, and its tests. **Code starts only after the relevant `NN-`
  plan is agreed.**

## Status

- [x] Sequencing decision made — **(A) positions-first**; rotations via WS-5 (parallel).
- [x] All Phase-1 super-specific plans drafted (WS-1…WS-5).
- [x] **WS-1 implemented** — `core/streaming/standard_stream/` (contract + codecs), 8 tests green.
- [ ] WS-3 → WS-2 → WS-4 (WS-5 parallel).

Plans: [WS-1 contract](01-standard-stream-contract.md) · [WS-3 frame extensions](03-canonical-frame-extensions.md)
· [WS-2 backend encoder + WS reshape](02-backend-encoder-and-ws-reshape.md) · [WS-4 UI wedge](04-ui-wedge.md) ·
[WS-5 kinematics fold-in](05-kinematics-foldin-rotations.md).
