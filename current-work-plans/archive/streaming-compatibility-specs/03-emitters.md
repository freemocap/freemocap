# 03 — Transports & Protocol Adapters (the spokes)

The hub turns the canonical frame into third-party output in one of two ways. Both are thin,
isolated, pure consumers of the [standard stream](02-streaming-hub.md#producing-the-standard-stream).

## Two kinds of hub output

- **Transport route** — carries the standard stream *unchanged in shape* over a different wire.
  The standard stream is LSL-shaped, so the real-LSL (TCP/UDP) route is a near-mechanical
  pass-through: same schema, same timestamped samples, LSL's own transport.
- **Protocol adapter** — derives a *foreign* protocol from the standard stream: retarget +
  convention-convert + re-serialize. VMC is the canonical example.

## The adapter contract

Every adapter declares its capabilities **positively** — what it needs and what it emits — so the
hub can validate configs and compute the right [derived views](02-streaming-hub.md#derived-views).
It never enumerates what it *doesn't* emit; a spec defines what a thing **is**, never the infinite
set of what it isn't.

```python
class MocapAdapter(ABC):
    name: str                          # "lsl", "vmc", ...
    target_convention: CoordinateConvention   # see 07 — declared, not hand-rolled
    send_rate_hz: float                # drives this output's own mailbox wait

    def required_fields(self) -> frozenset[str]: ...   # validated at stream creation
    def required_views(self) -> frozenset[ViewKind]: ...
    def emit(self, *, frame: CanonicalFrame, views: DerivedViews) -> None: ...
```

- `required_fields` / `required_views` are validated when a stream is created — a config that asks
  for a field the frame can't supply fails **loudly at setup**, not silently at runtime.
- What an adapter *emits* is documented positively (channels it publishes); the UI shows that, not
  a "what it discards" table.
- `emit` is pure: frame + views in, bytes out on the transport. No pipeline access.

## Build order (inverted): the standard stream first

The standard stream is the foundation, not an afterthought. Build in this order:

1. **The LSL-shaped standard stream** (Phase 1) — reshape FreeMoCap's own UI streaming into
   schema + timestamped samples over WebSocket. This is the central representation; the UI is its
   first consumer.
2. **The LSL transport route** (Phase 2) — a thin "protocol adder" that pushes the standard stream
   out through a real LSL outlet. Near-free, because the standard stream already mirrors LSL's
   model.
3. **The VMC adapter** (Phase 3) — the first *foreign* protocol, derived from the standard stream.
   Building it after the standard + LSL route means the shared abstraction is designed against two
   genuinely different shapes (same-shape transport vs. foreign adapter), not guessed.

This replaces an earlier "VMC first" ordering: leading with the standard stream makes the LSL route
nearly free and forces every foreign protocol to derive from one clean source.

## The LSL route

**`[IN]`** The highest-value output for FreeMoCap's research users, and the cheapest, because it *is* the
standard stream on LSL's transport.

- **Transport:** Lab Streaming Layer outlets via `pylsl`.
- **Shape:** the standard stream's schema → an LSL `StreamInfo`; each timestamped sample →
  `push_sample`. Because we deliberately mirror LSL's data model
  ([01](01-canonical-data-model.md#the-stream-schema--samples)), this is a pass-through, not a
  translation.
- **Carries everything:** positions, rotations, per-point confidence, reprojection error,
  per-camera timestamps — the full standard stream, since there's no lossy retarget.
- **Fixed dimensions:** an LSL `StreamInfo` has a fixed channel count. Subject/camera counts are fixed at
  outlet creation (max persons = 1 for now; cameras = # connected); a topology change tears down and rebuilds
  the outlet. Nothing is padded or excluded.
- **Consumers:** LabRecorder and any LSL inlet; clock-synced across machines by LSL itself.

## The VMC adapter

**`[IN]`** The first foreign protocol; a working, tested prototype exists in the `freemocap_vmc/` scratch repo
(OSC encoder, humanoid skeleton table, sender) and ports in with edits.

- **Transport:** OSC 1.0 messages over **UDP**. Stdlib-only encoder.
- **Shape:** `/VMC/Ext/*` messages — root transform + per-bone local rotations for a ~21-bone
  humanoid (optionally + finger bones), built from the shared
  [humanoid retarget](02-streaming-hub.md#the-humanoid-retarget) view.
- **Rotations are LOCAL to the parent**, and **identity must mean T-pose** — both from the shared
  retarget, so they're solved once. See
  [07 — the local-rotation trap](07-coordinate-conventions.md#the-local-rotation-trap-vmc-and-unreal).
- **Convention:** left-handed, +Y up, meters (converted from the canonical mm/right/+Z via the
  shared converter).
- **Packetization:** a full skeleton frame **does not fit in one UDP datagram** on a 1500-byte-MTU
  network (≈1640 bytes → 2 datagrams; with fingers ≈4064 → 3). MTU-aware bundle splitting.
  Loopback's 64 KB limit hides this until you go cross-machine — so it's tested cross-machine.
- **One avatar per `IP:port`.** VMC has no multi-actor addressing. Multi-subject is **one subject
  per stream** — two avatars = two VMC streams on two ports (see
  [04 — multiple streams](04-http-control-plane.md#multiple-concurrent-streams)).
- **Conformance = the reference implementations**, not the prose spec: "does it work against
  VirtualMotionCapture / EVMC4U / VSeeFace," since non-conforming software exists in the wild that
  works by accident. See [08](08-testing-strategy.md).
- **Windows trap:** sending to a closed local UDP port raises `ConnectionResetError` on a *later*
  call on that socket (ICMP port-unreachable surfaced late by Winsock). Handled per-socket,
  deliberately — a dead receiver must not corrupt the stream's error state.

## Dependencies (core, not optional)

Streaming's dependencies are **standard dependencies**, not optional extras. `pylsl` (and its
bundled `liblsl`) ships with FreeMoCap, because the LSL route is a first-class output and the
standard stream is defined against LSL's model. VMC needs no extra dependency (stdlib OSC over
UDP). There is no "requesting an adapter fails because an extra wasn't installed" path — if an
adapter is listed, its dependencies are present.

## Later adapters `[LATER]` / `[FUTURE]`

Once the adapter interface is extracted (after VMC), these become cheap:
- **VRChat OSC** `[LATER]` — reuses the OSC encoder; VRChat expects users to write their own
  sender. Euler angles, not quaternions.
- **Rokoko JSON** `[LATER]` — ~80 lines on top of the humanoid retarget; adds multi-actor + props.
  **`TBD` (trigger: read Rokoko's open-source plugins):** whether they accept a non-Rokoko source
  or gate on Studio licensing.
- **Xsens MVN, Qualisys RT, Unreal Live Link** `[FUTURE]`. Unreal is already reachable free today
  via VMC → VMC4UE + VRM4U, so a native Live Link route is low priority.
- **Skip NatNet and Vicon.**

## The adapter interface (extracted after VMC) `[IN]` (Phase 3)

With the standard stream, the LSL route, and the VMC adapter built, the shared abstraction is
visible and the registry gets built: a name→adapter registry with entry-point-style discovery and
positive capability declaration. Designing it earlier would be guessing; see
[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) Phase 3.
