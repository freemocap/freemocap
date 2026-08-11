# 06 — Backend Refactor & Cleanup

Two backend concerns ride along with this effort: breaking up the WebSocket server God object and
reshaping its send path into the standard stream `[IN]`, and **aligning** the disabled kinematics code with
the new models (not deleting it) `[LATER]`.

## `websocket_server.py` breakup + standard-stream reshape `[IN]`

### Current shape

`freemocap/api/websocket/websocket_server.py` defines a `WebsocketServer` (~430 lines), instantiated
**per connection**, that runs four concurrent asyncio tasks plus a connect-time handshake, all in
one class:

1. `_frontend_image_relay` — waits for a processed frame, pulls the latest frontend payloads (images
   + keypoints binary), sends them, and manages **frame-ack backpressure** plus server/display
   **framerate** calculation.
2. `_logs_relay` — drains the log queue to the client.
3. `_client_message_handler` — receives frame acks + display sizes + "settings" from the client.
4. `_app_state_sender` — pushes the `app_state` snapshot on connect and on change.
5. `_send_tracker_schemas` — connect-time handshake; a shared `_send_lock` serializes all sends.

It mixes transport, backpressure policy, framerate math, log relaying, and app-state projection in a
single per-connection object.

### Target decomposition

Break the responsibilities into focused, individually-testable components the per-connection runner
composes:

- **Standard-stream encoder** — turns each canonical frame into the standard stream: the **schema**
  once (channel names, joint hierarchy, T-pose, convention, units — subsuming today's
  `_send_tracker_schemas` handshake) and a **timestamped sample** per frame. This is the **shared**
  component the hub's LSL route also uses ([02](02-streaming-hub.md#producing-the-standard-stream)),
  so the reshape and the breakup are one change, not two.
- **Send serializer** — owns the `_send_lock` and the one-writer invariant; the only thing that
  writes to the socket.
- **Frame relay** — waits on the frame source and sends samples; delegates policy to:
- **Backpressure/ack controller** — the ack-lag thresholds and reset logic, as a small policy object
  (no I/O), unit-testable against synthetic lag.
- **Framerate reporter** — server/display framerate calculation + throttled emission.
- **Log relay** and **app-state sender** — each its own component.
- **Client-message handler** — inbound acks/settings routing. **Open question (audit during this
  work):** is the inbound "settings sync" actually used end-to-end? Should the data WebSocket be
  **one-way** (control moves to HTTP), or keep a minimal inbound channel (acks/display-sizes)? This
  ties to the stale-UI-after-crash issue — see
  [05 — known issue](05-ui-integration-and-refactor.md#known-issue-inbound-settings-and-stale-ui-after-a-crash).

The per-connection `WebsocketServer` becomes a thin supervisor that wires these together and runs them
as tasks — mirroring, on the backend, the "thin composition root over focused modules" shape the
frontend gets in [05](05-ui-integration-and-refactor.md).

### Relationship to streaming

The standard-stream encoder is the **join point**: the UI's WebSocket relay and the hub's LSL route
consume the *same* encoder output. So this breakup is not merely parallel cleanup — reshaping the send
path into the standard stream is Phase 1 of the streaming work itself. Foreign-protocol adapters (VMC)
still have their own transports and never touch this WebSocket; only the *shape* is shared.

## Disabled kinematics — align, don't delete `[LATER]`

The disabled centroidal-kinematics path is switched off today, but it holds **good material worth keeping**
(the centroidal-CoM work in particular) — so it is **aligned to the new models, not deleted**:

- `StreamingKinematics` (`core/kinematics/online/streaming_kinematics.py`) — instantiated in the aggregator
  but its per-frame `update()` is commented out.
- `BodyKinematicsState` (`core/kinematics/body_kinematics_state.py`) — only produced by that disabled path,
  so it ships as `None` today.
- The inertia-ellipsoid / ground-reference modules (`core/kinematics/inertial/`).

**Plan:** align these to the folded-in kinematics engine + canonical model ([11](11-kinematics-fold-in.md))
rather than deleting them. **Keep unvalidated paths out of the realtime hot loop** until tested — a
disabled-but-aligned module is fine; an unvalidated one in the hot loop is not. Don't wire the always-`None`
`body_kinematics` field into the standard stream until its producer is validated
([01 — live substrate only](01-canonical-data-model.md#live-substrate-only)).

> Related cleanup surfaced by this work: any stale `app_state` / "settings" fields found not to be
> wired end-to-end during the reshape are flagged for removal (see
> [05](05-ui-integration-and-refactor.md#the-status-feed-over-the-standard-stream-websocket)).
