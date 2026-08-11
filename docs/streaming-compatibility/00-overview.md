# 00 — Overview

## The problem

FreeMoCap reconstructs live 3D skeletons from multi-camera capture. Today that live data has
exactly one destination: FreeMoCap's own Electron/React UI, reached over a bespoke WebSocket
binary protocol (`freemocap/api/websocket/`). Users repeatedly want the same live skeleton
*elsewhere* — driving a VTuber avatar, recording alongside EEG in a research rig, animating a
character in a game engine, feeding another lab's analysis tool.

Each of those targets speaks a different wire protocol, with different coordinate conventions,
different data shapes, and different audiences. Building a one-off bridge for each is a
combinatorial trap.

## The goal

A **streaming compatibility layer**: a server subsystem that can be told, over HTTP, to start
streaming the live skeleton in one or more third-party protocols simultaneously, and is
**cheap to extend** with new protocols later.

The organizing move is to give FreeMoCap's *own* real-time stream a clean, self-describing
shape and make **that** the thing every other protocol derives from.

## The bet: one standard stream, many transports

The central architectural bet is a **single standard stream** in the middle, with thin
transports and adapters around it.

The standard stream borrows Lab Streaming Layer's (LSL) data model: **send a schema once,
then stream timestamped samples.** The schema (a StreamInfo-like descriptor) declares the
static facts — channel/landmark names, joint hierarchy, T-pose rest pose, coordinate
convention, units. Each per-frame sample carries only **`data + timestamp`**. This is
implemented over the existing WebSocket for the UI — and because it mirrors LSL's model,
pushing it out through a real LSL outlet is a near-mechanical pass-through.

```
 canonical frame (in-process)
        │   serialized as →   SCHEMA (once)  +  SAMPLES (per frame: data + timestamp)
        ▼
   ┌────────────────────── THE STANDARD STREAM ──────────────────────┐
   │  (schema + timestamped samples, LSL-shaped)                      │
   └─────────────────────────────────────────────────────────────────┘
        ├─▶ WebSocket ─────────────────▶ React UI          ← the main transport
        └─▶ Streaming Hub
               ├─▶ real LSL (TCP/UDP) ─▶ LabRecorder, …     ← near-free: same shape, LSL's transport
               └─▶ protocol adapters ──▶ VMC / VRChat / …   ← derive from the standard: retarget + re-serialize
        │
        └─▶ (canonical frame also feeds the 3D viewport / BVH export in-process)
```

Everything hard — coordinate conversion, humanoid retargeting, per-segment rotation — is
solved **once**, upstream of the transports. A same-shape transport (LSL) is a pass-through;
a foreign protocol (VMC) is a bone-name map + a byte layout. That asymmetry is the entire
point: adding a protocol stops being a research project.

Three properties make the bet pay off:

1. **One canonical frame → one standard stream** (Single Source of Truth). Static facts live
   in the schema, not in every sample. See [01 — Canonical Data Model](01-canonical-data-model.md).
2. **Pure-consumer adapters** that never reach back into pipeline state — so a future
   thread→process split stays a one-line change. See [02 — Streaming Hub](02-streaming-hub.md).
3. **Coordinate convention is a schema fact, converted once**, with each adapter declaring its
   target — because every integration bug in this space is a coordinate bug. See
   [07 — Coordinate Conventions](07-coordinate-conventions.md).

## How the documents fit together

- **The data** — the standard stream's shape: [01](01-canonical-data-model.md) (canonical
  frame, schema + samples, rotations, subjects, rest pose) and [07](07-coordinate-conventions.md)
  (conventions).
- **The machinery** — how it flows and gets transported: [02](02-streaming-hub.md) (tap,
  standard stream, hub, supervision) and [03](03-emitters.md) (the transports & adapters).
- **The surfaces** — how it's driven and observed: [04](04-http-control-plane.md) (HTTP) and
  [05](05-ui-integration-and-refactor.md) (UI).
- **The enabling refactors** — the God-object cleanups this work pulls into scope:
  [05](05-ui-integration-and-refactor.md) (frontend) and
  [06](06-backend-refactor-and-cleanup.md) (backend).
- **The process** — how we prove it and phase it: [08](08-testing-strategy.md) and
  [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md).

## What this is *not*

- **The streaming protocols are not the UI transport.** The UI's transport *becomes* the
  LSL-shaped standard stream (over WebSocket), and the LSL output route re-uses that same
  shape — but VMC/OSC/etc. are never links in the UI's data path. The browser can't open raw
  UDP/TCP sockets, and we won't add multicast discovery or clock-sync to move data between two
  processes we already ship together. See [02](02-streaming-hub.md#the-standard-stream-and-the-hub).
- **Not a revival of the disabled kinematics code.** The layer builds on the *live* substrate
  only. See [01](01-canonical-data-model.md#live-substrate-only).

## Guiding principles (inherited from the FreeMoCap codebase)

- **Fail loudly, no fallbacks.** Errors surface; they don't silently degrade. Applied to
  streaming as a *scoped* fail-loud model — a failed stream fails visibly without taking down
  the capture session. See [04](04-http-control-plane.md#failure-model).
- **Positive definitions only.** A schema or adapter declares what it *is* / what it *emits* —
  never the infinite set of things it isn't or doesn't.
- **Single Source of Truth.** Every decision, config flag, and canonical value has exactly one
  home.
- **Zero backwards-compatibility cruft.** There is one version of the system: the current one.
  These docs describe it as it will be, not as a migration from anything.

## Glossary

| Term | Meaning |
|---|---|
| **Canonical frame** | The one authoritative in-process per-frame structure (positions, rotations, subjects, quality). Built by extending the pipeline's existing aggregation output. |
| **Standard stream** | The serialized, LSL-shaped form of the canonical frame: a **schema** sent once + **timestamped samples** per frame. The central representation everything derives from. |
| **Schema (StreamInfo)** | The static descriptor sent once: channel/landmark names, joint hierarchy, T-pose rest pose, coordinate convention, units, sample layout. |
| **Sample** | One frame on the wire: `data + timestamp`, no static metadata. |
| **Hub** | The streaming subsystem's core: taps the canonical frame, produces the standard stream, routes it to transports/adapters. |
| **Transport route** | Pushing the standard stream over a wire *without changing its shape* (WebSocket for the UI; real LSL TCP/UDP for the LSL route). |
| **Protocol adapter (emitter)** | Derives a *foreign* protocol from the standard stream (e.g. VMC): retarget + re-serialize. A pure consumer. |
| **Segment quaternion** | A per-bone rotation relative to the declared rest pose. Owned by SkellyModels (a module within SkellyForge); see [01](01-canonical-data-model.md). |
| **Stream** | One running transport/adapter instance, addressed by a `stream_id`. Multiple run concurrently. |
| **Convention** | The tuple (units, handedness, up-axis, forward-axis, rotation form) describing a coordinate space — a **schema** fact, not a per-sample one. |
