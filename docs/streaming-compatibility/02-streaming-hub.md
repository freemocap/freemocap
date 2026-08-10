# 02 — Streaming Hub

The hub is the protocol-neutral core: it taps the canonical frame, and for each active output
it either **re-transports the standard stream** (same shape, different wire) or **adapts it** to
a foreign protocol. It owns lifecycle and supervision. It knows nothing about any specific
protocol's internals beyond its adapter.

## Where it lives

A `StreamingManager` owned by the top-level application object `FreemocapApplication`
(`freemocap/app/freemocap_application.py`), as a **sibling** to the existing
`realtime_pipeline_manager` and `posthoc_pipeline_manager`. It is created and torn down with the
app, and it projects its state into the app's `to_state_dict()` snapshot so the UI sees streaming
status over the existing WebSocket (see [05](05-ui-integration-and-refactor.md)).

## The tap — a pure consumer of the bus

FreeMoCap already hands frames between components over a typed pub/sub bus (`PubSubTopicManager`,
`freemocap/pubsub/`). The aggregator publishes one `AggregationNodeOutputMessage` per processed
frame on `AggregationNodeOutputTopic`. The hub subscribes like any other consumer:

```
subscription = pipeline.pubsub.get_subscription(AggregationNodeOutputTopic)
```

The aggregator runs in a **worker process** and publishes onto a multiprocessing queue; the
pub/sub relay fans messages out to **main-process** subscribers. The `StreamingManager` and its
threads therefore live in the **main process** (same process as the FastAPI server), consuming
relayed frames.

### The pure-consumer rule (non-negotiable)

An adapter receives a frame + derived views and **never** reaches back into pipeline state, holds
a live reference to a pipeline buffer, or calls back into the server. This is the rule that keeps
a future thread→process migration a one-line change instead of a rewrite. It erodes silently —
enforce it in review.

## Producing the standard stream

From each canonical frame the hub (and the UI's WebSocket relay) produce the **standard stream**:
a **schema** once (channel names, joint hierarchy, T-pose rest pose, convention, units — see
[01](01-canonical-data-model.md#the-stream-schema--samples)) and a **timestamped sample** per
frame. The standard stream is LSL-shaped by design, so it can be pushed through a real LSL outlet
without reshaping. The schema/sample encoder is a **shared** component: the WebSocket relay uses
it for the UI, and the hub uses it for the LSL route.

## The standard stream and the hub

The standard stream fans out to the UI *and* to the hub's third-party outputs:

```
 canonical frame ─▶ standard stream (schema + timestamped samples)
                         ├─▶ WebSocket ───────────────▶ React UI          ← main transport
                         └─▶ Streaming Hub
                                ├─▶ transport route ──▶ real LSL (TCP/UDP) → LabRecorder, …
                                └─▶ protocol adapter ─▶ VMC / VRChat / …    → third-party software
```

Two kinds of hub output:

- **Transport route** — the standard stream, *unchanged in shape*, over a different wire. The
  real LSL (TCP/UDP) route is the canonical example: because the standard stream already mirrors
  LSL's model, this is a near-mechanical pass-through.
- **Protocol adapter** — a *foreign* protocol derived from the standard stream: retarget +
  convention-convert + re-serialize. VMC is the canonical example.

The streaming protocols are **never** the transport between the Python server and the
Electron/React frontend. The UI's transport *is* the standard stream over WebSocket; VMC/OSC/etc.
are third-party outputs only. The browser renderer can't open raw UDP/TCP sockets, and we won't
add multicast discovery or clock-sync to move data between two processes we already ship together.

## The handoff — a single-slot mailbox, not a queue

Realtime pose has no use for a backlog: a receiver wants the *current* pose, never a queue of
stale ones. Between the tap and the outputs sits a **latest-frame slot** (drop-oldest) rather
than an unbounded queue:

- The tap writes the newest frame into the slot and bumps a monotonic sequence number.
- Each output waits on the slot with **its own timeout derived from its own `send_rate_hz`**,
  reads whatever is current, and emits.

This gives drop-oldest semantics *and* per-output rate decoupling for free — a 90 Hz VMC stream
and a 30 Hz LSL stream read the same slot at their own cadences, with no scheduler and no drift.
A slow or stalled output can never apply backpressure to the pipeline.

**`TBD` (trigger: Phase-1 implementation):** exact slot primitive (condition variable + sequence
number is the intended shape).

## Derived views

Foreign-protocol adapters consume **derived views**, not raw pipeline state. A derived view is a
transform computed once per frame and shared:

- **Coordinate conversions** — see [07](07-coordinate-conventions.md). Only foreign adapters whose
  target convention differs from the canonical one invoke these; same-shape transport routes carry
  the canonical convention unchanged.
- **The humanoid retarget** — see below.

At startup the hub takes the **union** of every active adapter's declared `required_views()` and
computes exactly those per frame, publishing an immutable bundle. No locks, no lazy-cache races,
no double computation — and you never pay for a humanoid retarget nobody asked for (e.g. an
LSL-only session).

### The humanoid retarget

VMC, Rokoko, and Unreal all want the same thing: "named bones with rotations relative to a
declared rest pose." That is computed **once**, as a shared derived view, from the canonical
skeleton + segment rotations ([01](01-canonical-data-model.md)). Each humanoid adapter then
collapses to a **bone-name map + a serializer**. This is what makes the third humanoid adapter
cheap; it is the core payoff of the hub design.

## Supervision and lifecycle

The `StreamingManager`:
- **Starts** a stream: validates config synchronously, constructs the transport/adapter, registers
  its `required_views`, spawns its thread. Setup failures raise immediately (see
  [04 — failure model](04-http-control-plane.md#failure-model)).
- **Tracks** each stream by `stream_id` with a state (`RUNNING` / `FAILED` / `STOPPED`) and, on
  failure, the stored exception + lightweight stats (frames sent, last-send time).
- **Stops** a stream: signals its thread, closes its transport, removes it.
- **Tears down** all streams on app shutdown.

A runtime error transitions **that stream** to `FAILED` and stops its thread; the capture session
and other streams continue. Scoped fail-loud — detail in
[04](04-http-control-plane.md#failure-model).
