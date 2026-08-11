# FMC-WS-4 — UI Wedge + Standard-Stream Consumption

> Build order: parallel with FMC-WS-2 once FMC-WS-1 is fixed. Realizes [05](../05-ui-integration-and-refactor.md).
> **Status: plan for agreement — no code until agreed.**

## Goal

Extract message-routing + connection-lifecycle from the `ServerContextProvider` God object into a standalone
connection/transport service, and have it consume the standard stream (schema then samples) → the 3D viewport.
This is **the wedge** ([05](../05-ui-integration-and-refactor.md)).

## Files (evolve)

- `freemocap-ui/src/services/server/ServerContextProvider.tsx` — the God object (routing + connection
  lifecycle **out**).
- **new:** a connection/transport service (plain TS) — owns `WebSocketConnection`, connect/reconnect/state, and
  a **routing table** features register into.
- `services/server/server-helpers/websocket-connection.ts` — folded into the service.
- `server-helpers/frame-processor/keypoints-binary-parser.ts` + `keypoints-protocol.ts` → the **standard-stream
  sample decoder**.
- `server-helpers/websocket-message-types.ts` — the `stream_schema` message type.

## The work

1. **Extract the connection/transport service** — socket ownership + connect/reconnect/state + a routing table
   (features register routes instead of editing one giant `handleMessage` switch). `ServerContextProvider`
   becomes a thin consumer.
2. **Standard-stream decoder (TS)** — parse `stream_schema` (register channels / convention / hierarchy) then
   `stream_sample`s (mirror FMC-WS-1's binary format; `w,x,y,z` rotations; NaN missing).
3. **Feed the viewport** — schema-defined channels → the existing keypoints/skeleton subscriber sets (unchanged
   for now; the rolling-window stores are [05](../05-ui-integration-and-refactor.md) Step 2, a later WS).
4. **Image path unchanged** — camera images still decode via the existing image path.

## Task checklist

1. [ ] Connection/transport service (socket + state + routing table).
2. [ ] `ServerContextProvider` consumes the service (no giant switch / no socket ownership).
3. [ ] TS standard-stream decoder (schema + sample), parity with FMC-WS-1.
4. [ ] Viewport fed from decoded channels.

## Tests

- **Cross-language golden:** FMC-WS-1's golden sample bytes → correct TS-decoded values.
- Schema registration drives channel names / convention.
- Reconnect re-requests the schema.

## Not in scope

Full God-object decomposition (3D fan-out → rolling-window stores, frame/canvas loop) —
[05](../05-ui-integration-and-refactor.md) Step 2, later. Rotation *rendering* (channels present, NaN).

## Micro-decisions to confirm

- Service shape (class vs module) + how features register routes.
- Cross-language golden-fixture format (share FMC-WS-1's exact bytes).
