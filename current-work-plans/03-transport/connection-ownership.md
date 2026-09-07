# WebSocket connection ownership

## Agreed target

One application connection per app window carries state, logs, progress and task failures.
One realtime connection per window carries camera-only images or images with matching mocap
observations and reconstructions. One playback connection per selected recording session carries
client-requested raw and annotated frame ranges and recording playback data. Closing a viewer
does not cancel a pipeline. Pipeline cancellation remains an explicit task operation.

Reuse typed messages, encoding, decoding, rendering and connection lifecycle machinery. Live delivery
selects fresh frames with bounded pending work; playback follows client requests and caches.
Application-owned producers broadcast events; individual connections must not drain shared event
queues independently. Connection failures must not set the application kill flag.

## Checkpoint 1: lifecycle cleanup, ready for app QA

- Provider initialization, subscriptions and disposal have one effect owner.
- Teardown closes the decoder worker; disposed effects cannot deliver asynchronous decoder results.
- Log storage is initialized lazily. Its persistence timer starts in the effect and stops at cleanup.
- Manual reconnect cancels scheduled retries. Socket callbacks check their owning socket; disconnect
  detaches callbacks and stops heartbeat/retry timers.
- Each frontend module instance has a client identifier; each connection attempt has a separate
  connection identifier, included in the URL. Backend open/close logs include this URL, and live
  delivery reports include the connection identifier. A reload creates a new client identifier;
  it is diagnostic identity, not a persistent window or recording identity.
- TypeScript checks, one socket lifecycle regression test and seven backend delivery tests pass.

App QA: use one app window, start cameras, reload several times, then enable realtime mocap.
Check that closed connections stop producing delivery summaries and only the current connection
remains active. Open a second window deliberately to confirm separate client identifiers and
independent frame delivery. The earlier duplicate connections' origin is not yet proven.

## Remaining checkpoints

### Self-describing frame reconciliation

Client model, camera and convention caches compare validated contents on each frame, retaining
references only when contents agree. Revision counters do not gate replacement. The server also
checks its memoized skeleton configuration when deciding whether to rebuild its composition.
Bone rendering rebuilds when definition contents change, including changes that keep the same IDs
and counts. Instance IDs are retained through live frame resolution and bone presentation.

Live viewport workers hold missing model instances and keypoint snapshots for up to one second,
using monotonic time and an expiry timer that runs even if frames stop arriving. Model definition
changes, disconnect and viewport teardown clear presentation state. Playback bypasses this timer,
so a paused recording does not disappear. Held values remain in the worker presentation store;
transport measurements and recording output are not filled with held poses.

Validation: content-reconciliation and timed-expiry frontend tests pass, TypeScript checks pass,
and nine server frame-relay/camera-only tests pass. App QA still required: connect cameras before
starting mocap, check bones appear, briefly interrupt tracking, interrupt it beyond one second,
restore tracking, and confirm paused playback stays visible. Per-segment interpolation and smoothing
are not part of this grace period.

1. Confirm lifecycle behavior in the app. Resolve any duplicate connections using the identifiers.
2. Extract realtime delivery from application events. Establish shared event ownership for logs and
   progress, scoped failure handling, and deterministic cancellation/awaiting of connection tasks.
3. Consolidate playback sources under one recording session connection; separate cache ownership
   from socket ownership while retaining client-driven ranges and deterministic decoding.
4. Measure camera-only, realtime mocap and playback performance again, including simultaneous use.

Current application/realtime traffic still shares `/websocket/connect`; playback still opens per-source
connections. Endpoint separation and failure-isolation changes have not landed in checkpoint 1.
The pipeline's roughly 15 FPS processing rate remains an unresolved performance issue independently
of the corrected destructive multi-consumer output reads. Geometry matching remains deferred.
