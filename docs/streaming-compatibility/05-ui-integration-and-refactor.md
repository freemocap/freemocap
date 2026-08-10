# 05 — UI Integration & Refactor

The Streaming feature lands in the React/Electron UI, and it is the wedge that begins decomposing
the `ServerContextProvider` God object. Both are in near-term scope. This work also carries the
frontend half of the standard-stream reshape (schema + timestamped samples).

## Streaming controls live in the Realtime UI

Streaming is **not** a standalone control panel. It integrates into the existing **Realtime UI** as
a **dropdown of per-endpoint toggles** — one toggle per available transport/adapter (LSL, VMC, …) —
each expanding, via the **existing modal system**, into that stream's specific config form. The
form and the toggle list are driven by `GET /streaming/protocols`; start/stop map to the toggles.

Under the hood it still follows the UI's per-feature idiom:
- **State + thunks:** a Redux slice at `src/store/slices/streaming/` with thunks that call the HTTP
  API via `fetch`, like `mocap-thunks.ts` / `pipelines-thunks.ts` / `calibration-thunks.ts`.
- **Endpoints:** added to `ServerUrls.endpoints` in `src/constants/server-urls.ts` (the single place
  server URLs are defined).

## The status feed (over the standard-stream WebSocket)

Streaming state reaches the UI over the **existing WebSocket**, not over any streaming protocol (see
[02](02-streaming-hub.md#the-standard-stream-and-the-hub)):

- The `StreamingManager` projects its state into `FreemocapApplication.to_state_dict()`, the
  authoritative `app_state` snapshot pushed to the client. Streaming lifecycle/state rides that same
  snapshot.
- **`TBD` (trigger: Phase 1):** whether high-frequency per-stream stats warrant a dedicated
  `streaming_status` message in addition to the `app_state` snapshot. Default: snapshot only.

**Known concern — audit `app_state` before relying on it** `[IN]`: verify the `app_state` snapshot
is actually wired end-to-end and current. There may be stale `app_state`/`settings` fields that
nothing consumes; **flag any that isn't connected end-to-end for removal** (a later cleanup stage,
tracked in [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md)). Don't build streaming status on a
field that turns out to be dead.

## The wedge: decomposing `ServerContextProvider`

`ServerContextProvider.tsx` (~600 lines) is a God object that currently holds, in one component:

1. **Connection lifecycle** — `WebSocketConnection` ownership, connect/disconnect/reconnect, state,
   `updateServerConnection(host, port)`.
2. **Message routing** — the large inbound `handleMessage` switch over binary + JSON messages.
3. **Frame loop** — `requestAnimationFrame` decode/ack loop, `FrameProcessor`, `CanvasManager`.
4. **3D-data fan-out** — hand-rolled subscriber sets for keypoints / skeleton / CoM / xcom /
   body-kinematics.
5. **Stores** — `FramerateStore`, `LogStore`.
6. **Tracker schemas** — `trackerSchemas` / `activeTrackerId`.
7. **Redux glue** — dispatching connection / pipelines / calibration actions.

### Step 1 — the wedge (Phase 1) `[IN]`

Extract **message routing (2) + connection lifecycle (1)** into a standalone **connection/transport
service** (plain TypeScript, not a React component):

- The service owns the `WebSocketConnection`, the connect/reconnect/state machine, and a **routing
  table** mapping inbound message types to handlers.
- It is where the frontend consumes the **standard stream**: the `schema` message registers the
  channel/keypoint/convention descriptor; subsequent `sample` messages are routed by it. Features
  (including Streaming) **register a route** instead of editing a giant switch.
- `ServerContextProvider` becomes a **thin consumer** — it no longer owns the socket or the routing
  switch.

### Step 2 — complete the decomposition (Phase 3) `[IN]`

With the transport service in place, move the remaining concerns out into focused modules:

- **3D-data fan-out (4) → rolling-window time-series stores.** Instead of bare subscriber callbacks,
  route the 3D samples into time-series **stores that retain a rolling window per keypoint/channel**,
  so trails and time-series views come for free later. This must stay **fast and memory-bounded**:
  the window length is a **settable value defaulting to ~100 frames**, and it reuses the existing
  (well-optimized) time-series store machinery. This aligns naturally with the standard stream's
  schema-then-samples shape — the schema defines the channels, the stores accumulate the samples.
- **Frame loop + canvas (3)** → a rendering-orchestration module.
- **Stores (5) and tracker schemas (6)** → their own focused providers/services. The tracker-schema
  handling folds into the standard stream's `schema` message.

The provider ends as a thin composition root. Order matters: the wedge ships with the vertical
slice; the rest follows once the standard stream is proven.

## Known issue: inbound settings and stale UI after a crash

**`[IN]`** *(document now, don't fix yet.)* The current WebSocket carries **inbound** client→server messages (frame acks, display sizes,
"settings"). Two questions to resolve during the reshape, **documented now, not fixed now**:

- **Is the inbound "settings sync" actually used end-to-end, and do we want it?** Options range from
  keeping a minimal inbound channel (acks/display-sizes only) to making the data WebSocket **one-way**
  and moving all control to HTTP. `TBD` (trigger: audit during the wedge).
- **Server-crash → stale UI.** When the server dies mid-operation, the UI can be left in a broken
  state (e.g. a "stop recording" button stuck on, not recoverable even after the server restarts),
  because observed state isn't reconciled on reconnect. We are **not fixing this now**, but the
  standard-stream reshape + the `app_state` audit are the right moment to make reconnect
  authoritative — noted so it isn't forgotten.

## Why this order

Doing the full decomposition first would delay streaming with no user-visible payoff; piling
streaming onto the God object would deepen the debt the team wants gone. Using streaming (and the
standard-stream reshape) as the wedge threads both: ship the feature *and* make the first clean cut,
with the larger decomposition sequenced behind the proof.
