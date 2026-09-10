---
title: Architecture review — ownership and streaming
sidebar_position: 1.5
mdx:
  format: md
plan_status: ongoing
plan_generated: "2026-09-10"
plan_audited: "2026-09-10"
---

# Architecture review: ownership and streaming

## Ready for your review

This is the first substantive review packet. Read the
[implemented communication flow](../architecture/frontend-backend-communication.mdx)
first, then the comparison and decisions below. Allow roughly 15 minutes.

The audit date covers the named source paths and symbols in that reference page.
It does not certify every endpoint, message field, failure path, or application workflow.
No runtime behavior was changed for this review. Findings come from code inspection;
reconnection and multi-window behavior were not exercised in the application.

## Ownership vocabulary

| Layer | Responsibility | Concrete implementation anchors |
| --- | --- | --- |
| Presentation | Render observations and collect user input; own view choices | React components, canvases, viewport workers |
| Client application | Form requests, validate incoming messages, reconcile disposable caches | TransportService, ServerContextProvider, Redux reducers/thunks |
| Server boundary and application | Interpret requests, own operation lifetime, publish observations | FastAPI routers/lifespan, WebsocketServer, PosthocPipelineManager |
| Processing and domain | Compute results and enforce domain invariants | FreeMoCap pipeline/tasks and Skelly package capabilities |
| Devices and published files | Supply physical observations and persisted artifacts | Cameras and recording output |

This is a proposed vocabulary for documentation. It is not a requirement to rename
directories. The detailed division of domain work among Skelly packages needs its own audit.

## Agreement versus implementation

| Principle | Observed implementation | Required follow-up |
| --- | --- | --- |
| Server owns execution independently of viewers | Application lifespan collects posthoc progress; each connection reads snapshots | Verify lifecycle and failure isolation with multiple clients |
| Messages carry enough information to interpret their scope | Frames carry definitions; task snapshots include recording, camera progress, status, and membership | Define scope and completeness per message kind, including absence semantics |
| Completed-task dismissal removes the task | Server retains up to 100 completed tasks; client persists IDs used to hide them | Replace this retention/dismissal contract; do not promote it as intended architecture |
| New observations replace cached server state | Task snapshots replace the client task collection; same-instance stale revisions are ignored | Define session/revision ordering consistently across message kinds |
| Client needs no prior observation to understand a message | Snapshot rendering is reconstructible; playback refresh side effects also compare prior owners/task phases | Separate rendering completeness from artifact-refresh policy and test fresh-client behavior |
| Requests have defined retry semantics | A known terminal task can be stopped again successfully | Audit all mutating endpoints; this is not evidence that all requests are idempotent |
| Domain errors are visible and scoped | Transport logs subscriber exceptions and continues; unsupported messages are skipped | Decide which errors terminate a consumer, a connection, or the application |

## Decisions for this review

### 1. Approve the ownership vocabulary

Does the table capture the front/back distinction on each side of the API boundary?
The server is authoritative about execution and observations. A disconnected client
can still own unsent edits, navigation, and viewport choices.

### 2. Define completed-task lifetime

The agreed constraint is clear: dismissal must not require retaining historical
tasks or a client-side list of hidden IDs. Active worker management remains necessary.

We still need to decide whether a terminal result is a transient notification,
an explicitly dismissible current server item, or another narrowly defined lifecycle.
If it is a current server item, dismissal removes it from authoritative membership.
If it is a transient notification, missing it during disconnect cannot be repaired
by replaying an unlimited task history. Published output can be rediscovered from disk.

This choice needs to cover multiple windows and a client disconnecting just before
completion. There is no recommendation here to retain 100 completed tasks.

### 3. Define request identity before promising idempotence

Desired-state commands and deliberate new runs need different identity rules.
Specify how a retry identifies the same operation, how a new run differs, and what
the server promises after restart. Do not infer these guarantees from HTTP verbs.
The endpoint-by-endpoint evidence table is the next audit, not completed work.

### 4. Keep message completeness separate from delivery

A complete snapshot can describe itself without guaranteeing delivery during a
disconnect. Specify current membership and removal, ordering within a server session,
and recovery from published artifacts independently. Envelope fields alone do not
prove that consumers enforce those contracts.

## Proposed acceptance scenarios

- Refresh during an active task: the first task snapshot reconstructs its display.
- Dismiss a finished task: subsequent updates and reconnects do not resurrect it.
- Lose the connection at completion: recover published output using a defined policy.
- Stop an already stopped task: apply the agreed retry semantics without creating work.
- Open two windows, then close one: remaining delivery and processing continue.
- Receive stale observations: reject them within their declared session and scope.

These are future contract tests, not results claimed by this audit.

## What is ready and what is not

**Review now:** the ownership vocabulary, observed transport flow, identified gaps,
and the four decisions above. This is enough substance for architectural guidance.

**Review later:** the full SDK surface, a complete mutation/idempotence matrix,
device/config ownership, log fan-out, recording publication recovery, and detailed
Skelly package boundaries. Those still need source-level passes.

After this review, turn agreed decisions into an architecture decision document,
then audit each affected boundary against those decisions before changing runtime code.
