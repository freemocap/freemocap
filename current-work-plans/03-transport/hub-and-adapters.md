# Streaming Hub + Protocol Adapters (LSL / VMC)

**Describes (target):** the fan-out of the one message stream to third-party motion-capture protocols
(LSL, VMC, …): the adapter contract, the LSL route, the VMC adapter, and the "start idle / ephemeral"
lifecycle. **Not built yet** — this is the spec for the [LATER] adapter workstreams in
[IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md).

## What this covers

- **Adapter contract** — what an adapter declares it emits (positive definition only).
- **Transports vs. adapters** — transports carry the message stream; adapters translate to a foreign
  protocol.
- The LSL pass-through route + coordinate-convention handling per target.
- The VMC adapter (VRM 1.0→0.x names + expressions).

## Lifecycle

"Start idle" + "ephemeral" (server-side config not persisted). The control surface is
[./http-control-plane.md](./http-control-plane.md).
