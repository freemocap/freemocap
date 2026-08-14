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
| **FMC-WS-1 — Standard-stream contract** | schema + sample **types + wire codecs**, no wiring yet | [09](../09-standard-stream-protocol.md) | — (linchpin) |
| **FMC-WS-2 — Backend encoder + WS reshape** | produce schema/samples from the canonical frame; reshape `websocket_server.py` send path | [06](../06-backend-refactor-and-cleanup.md) | FMC-WS-1, FMC-WS-3 |
| **FMC-WS-3 — Canonical-frame extensions** | convention-in-schema, subject dimension, confidence/error, rotation-channel declaration | [01](../01-canonical-data-model.md) | FMC-WS-1 |
| **FMC-WS-4 — UI wedge + consumption** | extract connection/transport service; decode schema+samples → 3D viewport | [05](../05-ui-integration-and-refactor.md) | FMC-WS-1 |
| **FMC-WS-5 — Kinematics engine fold-in → rotations** | copy/adapt `bs/kinematics_core` into SkellyForge; standard-human rig; live per-segment quaternions → fill rotation channels | [11](../11-kinematics-fold-in.md), [12](../12-standard-human-model.md), [13](../13-tracker-to-canonical-mapping.md) | FMC-WS-1 (channel) |
| **FMC-WS-6 — Tests & verification** | golden bytes, round-trip, LSL-model parity, UI decode parity | [08](../08-testing-strategy.md) | threads all |

## Dependency graph & sequence

```
FMC-WS-1 (contract) ──┬──▶ FMC-WS-3 (frame ext) ──▶ FMC-WS-2 (encoder + WS reshape) ──▶ FMC-WS-4 (UI consume)
                  └──▶ FMC-WS-4 can build against the fixed contract in parallel
FMC-WS-5 (kinematics fold-in) ── parallel track ──▶ fills the rotation channels FMC-WS-3 declared
FMC-WS-6 (tests) ── throughout
```

Recommended order: **FMC-WS-1 → FMC-WS-3 → FMC-WS-2 → FMC-WS-4**, with **FMC-WS-5** parallel and **FMC-WS-6** continuous.

## Key sequencing decision — **superseded 2026-08-11, recorded here 2026-08-13**

The canonical human was **front-loaded**: the stream shape cannot be designed without knowing what flows
through it. Rotations are populated live (not declared-NaN); the open half is the encoder (FMC-WS-2).
The detailed path is [`10-whole-project-alignment.md`](10-whole-project-alignment.md) — phases A–G —
and the current handoff is [`HANDOFF_2026-08-13.md`](HANDOFF_2026-08-13.md). (FMC-WS-5 was absorbed
into the standard-human sub-plan; the original positions-first text above is the record.)

## Plan hierarchy convention

- `README.md` (this) — decomposition + sequence + definition of done.
- `NN-<workstream>.md` — one **super-specific** plan per workstream: exact files to create/evolve, concrete
  types + wire format, an ordered task checklist, and its tests. **Code starts only after the relevant `NN-`
  plan is agreed.**

## Status

- [x] Sequencing decision made — **(A) positions-first**; rotations via FMC-WS-5 (parallel).
- [x] All Phase-1 super-specific plans drafted (FMC-WS-1…FMC-WS-5).
- [x] **FMC-WS-1 implemented** — `core/streaming/standard_stream/` (contract + codecs), 8 tests green.
- [x] **SF-SH-1 (standard-human model) implemented** — `skellyforge/skellymodels/standard_human/`
      (human_bones, aliases, blendshapes, model + validators).
- [x] **SF-SH-3 (kinematics engine) implemented** — `skellyforge/kinematics/`
      (quaternion_math, coordinate_frame_ops, rigid_body_kinematics).
- [x] **SF-SH-4 (orientation solver) implemented** — `skellyforge/kinematics/orientation_solver.py`
- [x] **ST-SH-2 (tracker→canonical mappings) implemented** — `skellytracker/core/io/tracker_mapping.py`
- [x] **SF-SH-5 (wire-up) implemented** — solver wired into freemocap aggregator, rotation fields on frame
- [x] **SF-SM Phase A complete (2026-08-13)** — segment model, solver, estimator; 94/94 skellyforge.
- [ ] **Phase B — the tracker-mapping completeness contract** (SF-SM Task 6) — current.
- [ ] FMC-WS-3 (adapter) → FMC-WS-2 (encoder) → FMC-WS-4 (UI wedge) — after the commit round.

Plans: [FMC-WS-1 contract](01-standard-stream-contract.md) · [FMC-WS-3 frame extensions](03-canonical-frame-extensions.md)
· [FMC-WS-2 backend encoder + WS reshape](02-backend-encoder-and-ws-reshape.md) · [FMC-WS-4 UI wedge](04-ui-wedge.md) ·
[FMC-WS-5 kinematics fold-in](05-kinematics-foldin-rotations.md) · [FMC-RB rigid-body renderer](06-rigid-body-bone-renderer.md) ·
[FMC-SR spec reconciliation](07-spec-reconciliation.md) · [SF-AL SkellyForge alignment](08-skellyforge-alignment.md).

> **Current workstream: [FMC-SR — Spec Reconciliation](07-spec-reconciliation.md)** — documentation only,
> no code. It executes the follow-up actions from [`AUDIT_2026-08-12`](../AUDIT_2026-08-12.md) and fixes the
> keypoint / landmark / segment vocabulary the remaining workstreams are written against. **Several
> statements in *this* file are among the things it corrects** — including the sequencing decision recorded
> above, which was superseded on 2026-08-11. Read FMC-SR before acting on anything here.
