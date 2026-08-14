# 04 — HTTP Control Plane

The streaming layer is driven over HTTP: list what's available, start streams, inspect and stop
them. This follows FreeMoCap's existing router idiom exactly — no new plumbing.

## The idiom it follows

A new `streaming_router` registered in `freemocap/api/routers.py`'s `FREEMOCAP_ROUTERS` list,
mirroring `realtime_router` (`freemocap/api/http/realtime/realtime_router.py`):

- `APIRouter(prefix="/streaming", tags=["Streaming Compatibility"])`.
- Handlers reach the subsystem through the `get_freemocap_app()` singleton →
  `app.streaming_manager` (see [02](02-streaming-hub.md#where-it-lives)).
- Pydantic request/response models with camelCase aliases (matching the UI's JSON).
- `try/except` → `HTTPException`; validation failures → `422`.

There is a precedent for the whole control shape already in the codebase: the
`reset-skeleton-fitter` endpoint **arms a pipeline via a pub/sub message and a companion GET polls
its state**. Streaming's start/status pair is structurally the same.

## Endpoints

```
GET    /streaming/protocols          list transports/adapters: name, config schema,
                                     what each emits + requires
POST   /streaming/start              {protocol, config} -> {stream_id}
GET    /streaming/streams            active streams + state + stats
GET    /streaming/streams/{id}       one stream's detail (incl. stored error if FAILED)
DELETE /streaming/streams/{id}       stop it
```

- `GET /streaming/protocols` drives the UI: it returns each output's per-adapter config schema
  ([Config validation](#config-validation)) and a **positive** description of what it emits +
  requires ([03](03-emitters.md#the-adapter-contract)) — never a "what it discards" list.
- `POST /streaming/start` returns a `stream_id`. **`stream_id` is first-class** — everything after
  start is keyed by it, never by protocol name.

## Multiple concurrent streams

Assumed **yes** from day one:

- **Different protocols at once** — e.g. LSL → LabRecorder *and* VMC → VSeeFace simultaneously.
  The normal case, not an edge case.
- **Multiple instances of the same protocol** — two VMC streams on different ports targeting two
  machines is legitimate, and it is the **only** way to drive two avatars over VMC (one avatar per
  `IP:port` — see [03](03-emitters.md#the-vmc-adapter)). Keyed by `stream_id`, not by protocol name.

Multi-subject maps onto this: one subject per VMC stream (see
[01 — multi-subject](01-canonical-data-model.md#multi-subject-from-day-one)).

## Failure model

Scoped fail-loud — the codebase's "fail loudly, no fallbacks" rule, scoped so a stream failure
never kills the capture session:

- **Setup errors fail immediately and loudly, synchronously in the `POST` response.** Port in use,
  unknown/invalid config field, unresolvable host. This catches the large majority of real failures
  at the moment the user asks, with a `422`/`500` and a specific message.
- **Runtime errors transition that stream to `FAILED`**, stop its thread, and store the exception.
  It is retrievable from `GET /streaming/streams/{id}` and surfaced in the UI. **Other streams and
  the capture session continue.**
- **Never silently retry, never silently degrade.** A `FAILED` stream stays failed until explicitly
  restarted.

This is still failing loudly — it just scopes the blast radius to the thing that failed, because a
user who started a stream via the API expects to stop it via the API, not to have their capture
session die under them.

## Config validation

Each adapter publishes a **Pydantic config schema** (surfaced via `GET /streaming/protocols`) so the
UI can render a form and `POST /streaming/start` can `422` precisely. `required_fields` /
`required_views` ([03](03-emitters.md#the-adapter-contract)) are validated here too: asking for data
the frame can't supply fails at start, not mid-stream.

## Resolved behaviors

- **Start with no active capture → start idle.** `POST /streaming/start` succeeds and the stream
  sits idle; the [latest-frame slot](02-streaming-hub.md#the-handoff--a-single-slot-mailbox-not-a-queue)
  naturally yields nothing until frames arrive, then the stream begins emitting. No special-casing.
- **Persistence → ephemeral on the server.** Stream configs do **not** survive a server restart;
  the control plane holds them in memory only. Any "remember my streams" persistence is a **UI**
  concern, added later — the server stays stateless across restarts here.
