# TODO: Desired-state (PUT) endpoint refactor — freemocap write-side (Phase 2)

## Where this sits

The **read-side** of the server↔UI state overhaul is DONE in freemocap (committed work pending
runtime confirm): freemocap's websocket pushes an authoritative `APP_STATE` snapshot — a *superset*
of skellycam's camera-group state plus the realtime pipelines this app owns, plus `server_pid` —
and freemocap-ui consumes it (a `connection` Redux slice; websocket-only connectedness; PID display;
self-heal-on-disconnect; "Launch/Stop server" split away from the connection indicator).

This document tracks the **deferred write-side**: replacing the imperative command endpoints with
idempotent **desired-state** PUTs. It is the freemocap counterpart to
`skellycam/TODO-desired-state-refactor.md`. Read that one too — the division of labor matters (see
*Cross-repo ownership* below).

This doc is intentionally long. The first half is the **reasoning** (the theory and the jargon, with
definitions, plus the practical considerations). The second half is the **concrete change list**.

---

# Part 1 — Reasoning

## 1.1 The core problem: imperative commands couple the client to the server's state machine

The current endpoints are **imperative**: `POST /realtime/apply`, `DELETE /realtime/all/close`,
`POST …/record/start`, `GET …/record/stop`, `GET …/pause_unpause`. Each is a *verb* — an instruction
to perform an action *right now*. Crucially, each carries **implicit preconditions**: "stop" is only
meaningful while running; "apply pipeline" presumes cameras exist; "start recording" presumes not
already recording.

When the write API is a set of precondition-gated commands, the **client must model the server's
state machine** to know which commands are currently legal — i.e. to decide which buttons to enable.
That duplicated state machine is the source of the drift, the stale buttons, and the "broken after
restart" behavior. The fix is to change the *shape* of the write API so the client no longer needs
to mirror anything.

## 1.2 Declarative vs imperative

- **Imperative**: describe *how* — a sequence of commands to reach a goal (`start`, then `stop`,
  then `apply`…). The caller owns the procedure and must know the current state to choose the next
  legal command.
- **Declarative**: describe *what* — the desired end-state — and let the system work out how to get
  there (`recording should be: active`). The caller states intent; the system reconciles.

Desired-state PUT is declarative. The win is not aesthetic: **declaring a desired state is a valid
operation in *any* current state**, so the precondition gating disappears. "I want recording = idle"
is meaningful whether or not we're recording; "stop" is not.

## 1.3 HTTP method semantics (the contract behind the verb)

HTTP methods carry a *contract* (RFC 9110) that infrastructure and clients rely on:

- **Safe** (GET, HEAD, OPTIONS): no intended state change — read-only.
- **Idempotent** (GET, HEAD, OPTIONS, **PUT**, **DELETE**): the intended effect of *N* identical
  requests equals the effect of one.
- **POST**: neither safe nor idempotent in general; "process this representation per the resource's
  own semantics." Conventionally used to *create a subordinate resource* (server assigns the URI) or
  *trigger processing*.
- **PUT**: "create or replace the state of the target resource with the supplied representation."
  The client names the target URI; sending the same body twice lands the same state. Idempotent.
- **PATCH**: partial update; *not* necessarily idempotent.

Current smells this refactor removes:
- `GET …/record/stop` — a **GET with a large side effect** (stops recording, writes files). Violates
  *safe*. A prefetch, a link preview, or a double-render could stop a recording.
- `GET …/pause_unpause` — a **toggle**, the canonical *non-idempotent* operation: call it twice and
  you're back where you started. If a response is dropped, neither client nor server can be sure of
  the resulting state. (This one is skellycam's to fix; see its TODO.)

This also restores **Command–Query Separation** (Bertrand Meyer): a method should either *change
state and return nothing meaningful* (a command) or *return data with no side effects* (a query) —
never both. A side-effecting GET is a CQS violation.

## 1.4 Idempotency (formal)

An operation `f` is **idempotent** iff `f(f(x)) = f(x)` — applying it again from its own result is a
no-op. For HTTP this is about the **server's state**, not the response body (DELETE twice: maybe
`200` then `404`, but the state "resource is gone" is identical both times).

Why we want it: it makes the network **retry-safe**. Double-clicks, reconnect storms, "did that
request actually land?" retries — all become harmless. `PUT /realtime/pipeline {desired: "running"}`
ten times = pipeline running, same as once.

## 1.5 Level-triggered vs edge-triggered (this is the big one)

Terms from digital electronics / interrupt handling, adopted by distributed-systems design
(notably Kubernetes controllers):

- **Edge-triggered**: react to the *transition* — the discrete moment a value changes ("recording
  *started*!"). If you miss the edge (dropped event, client asleep during the change), you
  desynchronize permanently.
- **Level-triggered**: react to the *held state* — continuously observe the current level and act on
  it ("recording *is* on"). Missing or duplicating an event is self-correcting, because the next
  observation re-establishes truth.

The old design was **edge-triggered**: the UI set its state from command *responses* (the edge) and
never re-observed. A dropped websocket message or a server restart left it stranded. The read-side
we just shipped is **level-triggered**: the server re-pushes the *entire current state* on every
(re)connect and on every change, so the UI is **self-healing**. The write-side completes the picture
by making *writes* idempotent too, so a retried write can't corrupt the converged state.

## 1.6 CQRS — separate the write plane from the read plane

**Command Query Responsibility Segregation** (Greg Young, generalizing CQS): use *different paths*
for writes (commands that mutate) and reads (queries that report). In our system:

- **Write plane** = HTTP `PUT` (the client's *desired* state). Returns essentially "accepted."
- **Read plane** = the websocket `APP_STATE` snapshot (the server's *observed* state). Authoritative.

The rule that falls out: **the UI never treats a command's HTTP response as truth.** The result of a
PUT is observed when it shows up in the next snapshot. This is what guarantees a single source of
truth instead of two (the optimistic local write *and* the server reality) that can disagree.

## 1.7 spec/status split & reconciliation loops (the Kubernetes model / control theory)

The canonical realization of all the above is the **spec/status split**:

- **spec** = desired state. Written by the client. (Our PUT body.)
- **status** = observed state. Written by the system. (Our `APP_STATE` snapshot.)

The server runs a **reconciliation loop**: observe `status`, compare to `spec`, take actions to drive
`status → spec`, repeat. This is literally a **control loop** in the control-theory sense — a
controller minimizing the error between a *setpoint* (spec) and a *process variable* (status). Its
properties are exactly what we want: **declarative**, **convergent**, **eventually consistent**, and
**self-healing**.

"Eventually consistent" is the honest caveat: after a PUT, `status` converges toward `spec` over a
short interval, not instantaneously. Intermediate observed states are transient. The UI must be
designed to show that honestly (a "pending" affordance) rather than lying optimistically — see 1.9.

## 1.8 Single source of truth & unidirectional data flow (Flux/Redux lineage)

The React/Redux ecosystem's **single source of truth** (SSOT) + **unidirectional data flow** is the
front-end half: state lives in *one* authoritative place; the view is a *pure function* of that
state; data flows one way (action → store → view). The original "two notions of connected" bug
(Electron-process-running vs websocket-open) was a textbook SSOT violation. Post-refactor, the SSOT
for *observed* state is the reduced snapshot, and the UI renders from it.

## 1.9 Statecharts / FSM, and affordances

"Which controls are valid in which state" is, formally, a **finite state machine** (Harel
*statecharts* are the hierarchical generalization). The imperative design forced the *client* to
re-implement the server's FSM to gate its buttons — coupling + drift. Declarative desired-state
**dissolves the gate**: expressing a desire is valid in every state, so a control's
enabled/disabled rendering becomes **derived feedback**, not a **precondition** the client computes.

This does *not* mean "all buttons always enabled." Disabled state is a legitimate **affordance**
(Gibson/Norman — what an interface communicates as actionable): greying "Stop" when nothing runs is
good UX. The point is the affordance is *derived from observed status*, not *computed by mirroring*
the server. Correct by construction, not by manual synchronization.

## 1.10 Practical considerations & tradeoffs

- **Breaking change, landed atomically.** PUT-ifying renames/replaces endpoints. Per this repo's
  CLAUDE.md (zero backwards-compat, no shims), the old `POST/DELETE` routes are deleted outright;
  backend + frontend + tests must land in one pass. No dual-path compatibility layer.
- **Optimistic UI vs latency (the real tension).** Pure SSOT — no optimistic writes — means a button
  click waits for the next snapshot (~1 s cadence) before the UI reflects it, which feels laggy.
  Mitigation is the **desired/observed split on the *frontend* too**: store a local `desired` set
  immediately on PUT (snappy), render `desired !== observed → "pending"`, take `observed` from the
  snapshot as authoritative, and **reset `observed` on disconnect** so a stale `desired` can never
  render a false "connected." This is the same spec/status pattern, recursed into the client.
  - A seam for this already exists: the realtime reducer's `!isLoading` guard
    (`realtime-slice.ts`) lets the optimistic `applyRealtimePipeline.fulfilled` and the authoritative
    snapshot coexist without a mid-action flicker. B4 formalizes it and drops the optimistic write.
- **Snapshot cadence.** If "pending" lingers too long, lower the `_app_state_sender` interval or
  event-drive it (push immediately after a reconcile) rather than the 1 s diff-poll.
- **Fail loudly at the boundary (CLAUDE.md).** Validate desired-state payloads at the endpoint
  (reject unknown `desired` values). Internal reconcilers should raise on impossible states, not
  silently degrade. The only place to be lenient is untrusted input at the system boundary.
- **Idempotency in practice.** `create_or_update_realtime_pipeline` already returns the existing
  pipeline for a matching camera set (so re-PUT is an update, not a duplicate). Verify "stop when
  already stopped" and "run when already running" are genuine no-ops, not errors.

---

# Part 2 — Concrete changes

## 2.1 Cross-repo ownership (read this first)

freemocap **mounts skellycam's `camera_router`** (`freemocap/api/routers.py` → `SKELLYCAM_ROUTERS`)
and adds its **own** `realtime_router`. Therefore:

- The **camera / recording / streaming** desired-state PUTs are **skellycam's** to build
  (`skellycam/TODO-desired-state-refactor.md`). They appear in freemocap automatically once
  skellycam's A3 lands and is pulled in. freemocap-ui's *thunks* for those still need updating here,
  but only **after** skellycam ships them.
- The **realtime pipeline** endpoint is **freemocap-owned** and can be done independently, now.

So B3/B4 split into: **(a) realtime — do anytime** and **(b) camera/recording/pause thunks — gated
on skellycam**.

## 2.2 Backend (freemocap-owned)

### `api/http/realtime/realtime_router.py`
- `PUT /realtime/pipeline` — `{desired: "running" | "stopped", config?, cameraConfigs?, realtimeCameraIds?}`.
  Replaces `POST /realtime/apply` + `DELETE /realtime/all/close`.
- Reconciler wiring (reuse existing `FreemocapApplication` methods):
  - `desired == "running"` → `create_or_update_realtime_pipeline(...)` (already idempotent — returns
    the existing pipeline for a matching camera set and updates its config).
  - `desired == "stopped"` → `close_pipelines()`.
- Validate `desired` at the boundary; raise `HTTPException` on unknown values.

### Stays POST (not stateful singletons — do NOT PUT-ify)
`POST /mocap/recording/process` (job creation; server-assigned id), `POST /shutdown`,
`POST /blender/...` actions, calibration/mocap recording-start flows. These are commands or
job submissions, not declarations of a single resource's desired state.

## 2.3 Frontend (freemocap-ui)

### Realtime (do with 2.2)
- `store/slices/realtime/realtime-thunks.ts` — `applyRealtimePipeline` + `closePipeline` →
  `PUT /realtime/pipeline`.
- `store/slices/realtime/realtime-slice.ts` — delete the optimistic `applyRealtimePipeline.fulfilled`
  / `closePipeline.fulfilled` writes that set `isConnected`. Observed state already arrives via the
  snapshot reconciler (added in B2). Introduce an explicit `desired` field + "pending" rendering
  (formalize the `!isLoading` seam).
- `constants/server-urls.ts` — repoint realtime endpoints to the PUT route.
- `store/slices/realtime/realtime-selectors.ts` — `selectCanConnectPipeline` currently cross-reads
  the cameras slice; re-express affordances against the unified observed projection from the
  `connection` slice so controls derive from one place.

### Camera / recording / pause (gated on skellycam A3/A4)
- `store/slices/cameras/cameras-thunks.ts` — `camerasConnectOrUpdate` + `closeCameras` → one
  `PUT /camera/group` (empty body = close); `pauseUnpauseCameras` → `PUT /camera/group/streaming`.
- Recording start/stop thunks → `PUT /camera/group/recording`.
- Delete the optimistic `.fulfilled` reducers in `cameras-slice.ts` (`connectionStatus='connected'`)
  — observed state comes only from the snapshot (the read-side reconcilers are already wired).
- `constants/server-urls.ts` — repoint these to the (pulled-in) skellycam PUT routes.

## 2.4 Verification
- `curl -X PUT …/realtime/pipeline` twice with the same body → identical final state (idempotent);
  `{desired:"stopped"}` when already stopped → no-op, not an error.
- Run freemocap server from source + freemocap-ui dev: connect/close the pipeline via the new PUT;
  confirm the button reflects the snapshot (no optimistic-only state). Double-click and reconnect
  mid-action → no broken state.
- `tsc --noEmit` clean on freemocap-ui; backend tests for the realtime router updated to the new verb.

## 2.5 Why deferred
The read-side already fixed the daily pains (the connectedness contradiction, stale-state-after-
restart, PID display). This write-side adds **robustness and correctness**: idempotent retries,
elimination of the optimistic dual-source-of-truth, and the declarative "express a desire" model
from Part 1. It is a breaking API change spanning two repos, so it earns its own focused, atomic
pass rather than being rushed in alongside the read-side.
