# Streaming Compatibility Layer

Engineering specification and strategy for FreeMoCap's **streaming compatibility layer** — a server
subsystem that gives FreeMoCap's own real-time stream a clean, self-describing (LSL-shaped) shape and
fans **that** out to third-party motion-capture protocols (LSL, VMC, and more), driven over HTTP and
surfaced in the UI.

> **Status:** specification. This folder describes the *target* system and the work to build it.
> Nothing here is implemented yet. Scope (what we build soon vs. later) is tracked in
> [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md).

## Read in this order

| # | Document | What it covers |
|---|---|---|
| 00 | [Overview](00-overview.md) | Problem, the one-standard-stream bet, glossary |
| 01 | [Canonical Data Model](01-canonical-data-model.md) | The canonical frame, schema + samples, segment quaternions (SkellyModels), multi-subject, rest pose |
| 02 | [Streaming Hub](02-streaming-hub.md) | Frame tap, producing the standard stream, transports vs. adapters, `StreamingManager` |
| 03 | [Transports & Protocol Adapters](03-emitters.md) | Adapter contract, the LSL route, the VMC adapter, inverted build order |
| 04 | [HTTP Control Plane](04-http-control-plane.md) | `/streaming/*` endpoints, stream lifecycle, failure model, start-idle, ephemeral |
| 05 | [UI Integration & Refactor](05-ui-integration-and-refactor.md) | Realtime-UI controls, `ServerContextProvider` decomposition, rolling-window stores, status feed |
| 06 | [Backend Refactor & Cleanup](06-backend-refactor-and-cleanup.md) | `websocket_server.py` breakup + standard-stream reshape, dead-code retirement |
| 07 | [Coordinate Conventions](07-coordinate-conventions.md) | Convention-as-schema-fact, per-target table |
| 08 | [Testing Strategy](08-testing-strategy.md) | Golden bytes, loopback, LSL pass-through, positive-capability, third-party conformance |
| 09 | [Standard Stream Protocol](09-standard-stream-protocol.md) | The precise wire contract: `stream_schema` + `stream_sample` |
| 10 | [Serialization & Tidy Format](10-serialization-and-tidy-format.md) | On-disk form: tidy long CSV/parquet vs SkellyForge parquet |
| 11 | [Kinematics Fold-In](11-kinematics-fold-in.md) | SkellyModels ↔ FreeMoCap `core/kinematics` ↔ `bs/kinematics_core` overlap + plan |
| 12 | [Standard Human Model](12-standard-human-model.md) | VRM rig, marker→bone retarget, derived joint centers (clavicle), twist policy |
| 13 | [Tracker → Canonical Mapping](13-tracker-to-canonical-mapping.md) | The keypoint→landmark mapping system (string / list-mean / weighted-sum) |
| — | [Implementation Plan](IMPLEMENTATION_PLAN.md) | Scope table, phased build order, dependencies, progress log |

## Conventions used in these docs

- **Scope tags** — every major feature is tagged **`[IN]`** (near-term), **`[LATER]`**, or
  **`[FUTURE]`** so aspiration is never confused with commitment. The authoritative scope table lives
  in [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md).
- **`TBD` markers** — open questions are written as explicit `TBD` with the *trigger* that resolves
  them (e.g. "pending the forward-axis confirmation"). They are never silently assumed away.
- **Positive definitions only** — a schema or adapter declares what it *is* / what it *emits*, never
  the infinite set of what it isn't or doesn't.
- **Single Source of Truth** — each decision is stated authoritatively in exactly one doc and
  cross-linked from the others. If you find the same decision explained twice, that's a bug in the docs.
