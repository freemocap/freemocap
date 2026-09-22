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
reconnection behavior was not exercised in the application.

## Agreed scope

One user, one desktop server, one client doing scientific work. Server and client
have independent lifetimes: either can refresh, restart, disconnect, or crash.
Their relationship is the HTTP and WebSocket protocol, not shared lifecycle state.
Multi-client coordination is outside the current design scope.

The server owns long-lived camera groups, realtime pipelines, posthoc workers,
and their resources. It does not rely on a connected viewer to own those objects.
The client owns its presentation and request construction.

## Ownership vocabulary

| Layer | Responsibility | Implementation anchors |
| --- | --- | --- |
| Presentation | Render observations and collect input; own view choices | React components, canvases, viewport workers |
| Client application | Form requests, interpret messages, reconcile disposable views/caches | TransportService, ServerContextProvider, Redux |
| Server boundary and application | Own long-lived objects and execution; accept commands and publish observations | FreemocapApplication, CameraGroupManager, RealtimePipelineManager, PosthocPipelineManager, FastAPI |
| Processing and domain | Compute results and enforce scientific invariants | FreeMoCap tasks and Skelly package capabilities |
| Devices and files | Supply observations and persisted artifacts | Cameras and recording output |

This vocabulary does not require directory renaming. Detailed Skelly ownership
still needs a source-level audit.

## Agreement versus implementation

| Principle | Observed implementation | Follow-up |
| --- | --- | --- |
| Server owns long-lived objects independently of the client | FreemocapApplication holds camera-group, realtime, and posthoc managers; lifespan collects progress | Trace their creation, replacement, and disposal independently of viewer lifetime |
| Messages are fully self-describing | Frames carry definitions; task snapshots carry recording, status, progress, and membership | Check that each message can be interpreted alone for its declared scope |
| Client may discard its presentation state | Server retains up to 100 completed tasks; client persists dismissal IDs | Remove historical replay/dismissal bookkeeping; allow fresh messages to recreate views |
| Fresh server observations replace cached observations | Task snapshots replace the collection; same-instance stale revisions are ignored | Check that a restarted server's current messages are accepted without prior-client knowledge |
| Client may retain its last display while disconnected | Provider currently clears frame/model presentation data on disconnect | Reconcile this behavior with the intended disconnected display policy |
| Processing follows explicit overwrite/append intent | Normal mocap publication uses run-0 overwrite defaults; planner supports separate runs | Expose the intended policy through the command path; see the [follow-up audit](processing-ownership-audit.md) |

The ownership finding comes from `freemocap/app/freemocap_application.py`:
its manager fields, `create`, and `create_or_update_realtime_pipeline`.
Other findings are grounded in the companion reference's source map.

## Agreed behavior

### 1. Fully self-describing messages

Use **fully self-describing** to mean: a message contains the data and context
needed to interpret and represent its declared scope without earlier messages or
knowledge of the initiating HTTP request. The client still implements the protocol;
messages do not need to contain rendering code or the entire application state.

An existing view updates from the message. A missing view can be created from it.
A matching view can remain unchanged. The client need not predict what arrives.
This is the target contract, not a claim that every current message already satisfies it.

### 2. Define completed-task lifetime

Dismissal can be entirely local: remove the displayed item and forget it. If the
server subsequently describes that item, the client may recreate it. That is correct
for a current observation, including a still-running task. No persistent dismissal
IDs, server acknowledgment of dismissal, or multi-window coordination are required.

The server should not repeatedly replay completed-task history. Local dismissal
cannot prevent resurrection while that history is still broadcast. Remove that
history-producing behavior, rather than adding a remembered client suppression list.
Active worker/resource ownership is separate and remains server responsibility.

Completion delivery while disconnected is not guaranteed. There is no requirement
to preserve or replay a missed progress notification after restart. Existing output
files remain available through ordinary recording access.

### 3. Processing commands and output policy

The agreed default is **overwrite**: processing replaces the selected output using
the supplied configuration. An explicit **append run** requests a separate result.
Repeating processing is permitted; strict idempotence or exactly-once execution is
not a universal requirement. Output selection and overwrite/append semantics matter
more here than proving that repeated requests execute only once.

We still need to trace the actual settings and publication code before asserting
that the current implementation implements these defaults end to end. That audit
should also check overlapping writes to the same output: permission to overwrite
does not by itself define safe concurrent writing.

For camera/config commands, the intended model remains declarative: describe the
wanted configuration and have the server apply it. Do not turn all HTTP operations
into a durable retry/deduplication protocol.

### 4. Independent lifetimes

The server offers no command recovery, notification replay, or client-state recovery
guarantee across restart. The client can retain its last display while disconnected,
identify that it is disconnected, and receive fresh observations when communication
resumes. Stale presentation is not a claim of a live connection.

Neither side needs the other's previous state to interpret current protocol traffic.
There is no requirement to reconstruct a vanished server process's in-memory objects.
Persisted scientific files are separate from that process lifetime.

## Proposed acceptance scenarios

- Refresh the client during processing: a fresh progress message can recreate the view.
- Dismiss a current item locally: discard it; a later current message may recreate it.
- Finish processing: completed history is not repeatedly broadcast to recreate old cards.
- Disconnect at completion: no replay or missed-notification recovery is required.
- Restart either side independently: compatible fresh messages can be interpreted alone.
- Reprocess with overwrite: replace the selected output using the requested config.
- Process with append: create a distinct run according to the explicit output policy.
- Disconnect the client: server-owned cameras and pipelines do not depend on its view lifetime.

These are future checks, not test results claimed by this audit.

## Intellectual landscape and historical context

This section situates the **proposed design**, rather than claiming the current
implementation conforms to every pattern below. The connections to FreeMoCap are
our architectural interpretation of the cited sources. This is a focused contextual
review, not an exhaustive survey or a claim of research novelty.

### A useful name for our approach

**A server-owned scientific application with separated presentation, declarative
configuration, and fully self-describing observations.**

That description is more accurate than assigning the whole application to a single
named architecture. Camera and pipeline objects live on the server; the client
forms commands and presents observations. We combine several established ideas
within the practical constraints of a single-user desktop instrument.

### The closest architectural relatives

| Idea and historical anchor | Connection to our design | Limit of the comparison |
| --- | --- | --- |
| **Information hiding and modular decomposition** — Parnas, 1972 | Boundaries should hide decisions that other modules should not depend on: device internals, transport encoding, rendering, scientific calculations | Splitting code into folders or sequential processing stages does not itself establish these boundaries. [Parnas](https://doi.org/10.1145/361598.361623) |
| **MVC and separated presentation** — Smalltalk GUI tradition; Fowler's historical synthesis | Scientific state and operations are separable from their visual representation. Our client application layer mediates between protocol data and widgets | The whole server is not literally an MVC controller. It contains domain models, application orchestration, and adapters. [GUI Architectures](https://martinfowler.com/eaaDev/uiArchs.html) |
| **Presentation Model and Passive View** | Stores and presentation logic can prepare data for rendering while components concentrate on interaction/display | Our client retains local drafts and presentation behavior, so “passive” is a direction of responsibility, not a claim that React components contain no logic. [Presentation Model](https://martinfowler.com/eaaDev/PresentationModel.html), [Passive View](https://martinfowler.com/eaaDev/PassiveScreen.html) |
| **Ports and adapters / hexagonal architecture** — Cockburn, 2005 | Processing should be callable through application boundaries without depending on a particular UI or HTTP transport. This gives a useful direction for SDK and headless execution | We have not audited all dependencies or established that the repository already implements hexagonal architecture. [Original article](https://alistair.cockburn.us/hexagonal-architecture) |
| **Declarative configuration and reconciliation** | “Make the camera configuration look like this” separates requested state from observed state. A controller can compare them and apply necessary changes | Kubernetes illustrates this pattern; its cluster, persistence, and recovery machinery are not requirements for FreeMoCap. A processing command may deliberately rerun work. [Controllers](https://kubernetes.io/docs/concepts/architecture/controller/) |
| **Self-descriptive protocol interactions** — Fielding, 2000 | Messages expose their meaning through a defined protocol rather than requiring a hidden conversational history | REST includes other constraints. HTTP commands plus a WebSocket do not automatically make the whole system RESTful. Server-owned camera objects also do not make the server “stateless.” [REST dissertation](https://ics.uci.edu/~fielding/pubs/dissertation/rest_arch_style.htm) |

The historical progression is useful: modularity asks **what each part knows**;
presentation patterns ask **where UI behavior belongs**; ports and adapters ask
**how external mechanisms meet application logic**; protocol design asks **what
must cross the boundary**. These are complementary questions, not competing brands.

### Robotics and instrumentation: command/control versus telemetry

This is a particularly close practical relative. **Command/control versus telemetry**
is useful vocabulary for distinguishing requests to the instrument from observations
published by it. We can describe our HTTP interface as a control interface and our
WebSocket as an observation/telemetry interface. This is a functional distinction;
it does not require two physical networks or a distributed control system.

**Project history, confirmed by the project maintainer on 2026-09-10:** FreeMoCap's
internal PubSub message-delivery system was deliberately designed to mimic the
functionality of ROS topics. This is a direct design influence, not merely a
similarity inferred in this review. The influence is specific to topic-based
PubSub delivery; the project does not claim to share the rest of ROS's architecture.
The service/action comparisons below are explanatory analogies, not project lineage.

ROS offers a concrete comparison through its three interface categories:

| ROS concept | Purpose | FreeMoCap analogue |
| --- | --- | --- |
| Services | Short request/response operations | Read configuration or request a configuration change through HTTP |
| Topics | Continuous published data | Stream measurements, images, and current observations through WebSocket |
| Actions | Long-running operations with feedback and cancellation | Start processing through HTTP, receive progress through WebSocket, request cancellation through HTTP |

The mapping is conceptual, not a claim that FreeMoCap implements ROS action
semantics. ROS itself distinguishes these communication behaviors independently
of our HTTP/WebSocket choice.
[ROS: Topics vs Services vs Actions](https://docs.ros.org/en/lyrical/How-To-Guides/Topics-Services-Actions.html)

Browser-facing robotics tools provide a second connection. Robot Web Tools'
**rosbridge** exposes topic publication/subscription and service calls through a
protocol that supports WebSocket. This demonstrates why the semantic split should
not be confused with a mandatory transport split: commands can also travel over
WebSocket. [rosbridge project](https://github.com/robotwebtools/rosbridge_suite)

**Foxglove** is a nearby example of robotics visualization using a WebSocket protocol
for live data, including richer schema information. It provides useful comparative
material for our model-aware scientific viewer. Its protocol is not evidence that
every individual message meets FreeMoCap's proposed fully self-describing contract;
that requires examining metadata dependencies at the message level.
[Foxglove WebSocket protocol](https://foxglove.dev/blog/announcing-the-foxglove-websocket-protocol)

Our specialization is a desktop scientific instrument: the server owns acquisition
and computation, commands express user intent, and observations drive the display.
We can adopt this vocabulary without adopting ROS middleware, robot motion-control
requirements, or multi-client operation.

### Independence means less lifecycle coupling, not zero coupling

Our design reduces dependence on the other process's history and lifetime. A client
refresh should not erase server-owned camera objects; a server restart should not
require the client to remember the conversation that constructed a frame.

Both sides still agree on message schemas, units, identities, and command meanings.
That protocol coupling is deliberate. “Fully self-describing” means complete for a
declared scope **to a compatible consumer**, not interpretable without any shared
vocabulary. Fielding's self-descriptive interactions likewise use shared interface
semantics. [REST interface constraints](https://ics.uci.edu/~fielding/pubs/dissertation/rest_arch_style.htm)

For our architecture, distinguishing these forms of coupling is more useful than
calling either side entirely independent or stateless: their processes live
independently, while their communication contract is shared.

### Nearby patterns that should not silently become requirements

**CQRS:** separating commands from observations resembles part of Command Query
Responsibility Segregation. CQRS more specifically separates write and read models;
choosing HTTP for commands and WebSocket for observations is not sufficient to claim
it. We can use that distinction without introducing separate databases or a more
elaborate architecture. [Fowler on CQRS](https://martinfowler.com/bliki/CQRS.html)

**Event sourcing:** our current observations are not a durable event history from
which every state is reconstructed. Event sourcing explicitly records changes so
state can be rebuilt from events. We do not need that model for progress cards,
local dismissal, or server restarts. A fully self-describing observation describes
what it represents; it does not require preserving every observation ever emitted.
[Fowler on Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html)

**Idempotence:** this has a precise meaning: repeating an identical request has the
same intended server effect as making it once. That is useful for some desired-state
commands, but it is not synonymous with “safe to run processing again.” Our overwrite
and append policies should say exactly what gets replaced or created, without
claiming strict idempotence where it has not been established.
[HTTP Semantics, §9.2.2](https://www.rfc-editor.org/rfc/rfc9110.html#section-9.2.2)

These distinctions keep useful intellectual tools from expanding a desktop workflow
into an event-history, distributed-recovery, or multi-client coordination project.

### The scientific-computing lineage

**Self-description is already a scientific-data tradition.** NetCDF, for example,
explicitly includes information describing its contents, supports machine-independent
data access, and has published scientific-data work dating to 1990. That is a close
relative of our requirement to carry enough context to interpret measurements.
It is a precedent, not a proposal to replace Parquet with NetCDF.
[Unidata's netCDF description and publications](https://docs.unidata.ucar.edu/netcdf-c/current/faq.html)

For FreeMoCap, a proposed completeness checklist should include coordinate
conventions, units, timestamps, camera calibration, model definitions, and the
meaning of missing measurements wherever those are needed to interpret a scope.
A message that names its fields but omits the coordinate system can be syntactically
readable while remaining scientifically ambiguous. This checklist is our application
of the principle; each field still needs a concrete contract audit.

**Reproducibility and provenance concern the scientific artifact.** The FAIR
principles emphasize machine-actionable metadata and reusable scientific data,
including provenance. They provide useful vocabulary for deciding what configuration,
calibration, processing identity, and diagnostics belong with saved results.
A Parquet file or a self-describing message alone does not establish FAIR compliance.
[Wilkinson et al., 2016](https://www.nature.com/articles/sdata201618)

An ephemeral progress display and a durable scientific record have different jobs.
We can discard progress cards without discarding the metadata needed to interpret
published results. Likewise, overwrite is an explicit output policy: if a user needs
to preserve comparative runs, append is the relevant choice. This does not require
recovering in-memory operations after a server crash.

### The UX connection: visible state and user control

The visibility-of-system-status principle connects directly to our distinction
between a retained display and a live observation. A client may keep its last frame
when disconnected, while clearly indicating that the connection is absent. It should
not imply that the measurement is still arriving.
[Nielsen Norman Group: Visibility of System Status](https://www.nngroup.com/articles/visibility-system-status/)

Our application-specific consequence is to separate **presentation actions** from
**execution commands**: dismissing a card changes the view; stopping a pipeline
requests a server action. Showing progress from server observations lets the user
see what is actually happening without making the UI the owner of the operation.
These are related concerns, but they should not share an ambiguous close/stop control.

### What is established, distinctive, and still unproven?

- **Established:** separated presentation, server-owned resources, declarative
  configuration, self-descriptive data, and explicit protocol boundaries all have
  substantial precedents. We are applying existing engineering ideas.
- **Distinctive within this project:** making those ideas consistent across live
  acquisition, calibration, reconstruction, playback, diagnostics, and saved
  scientific results. The useful contribution is their concrete integration into
  this workflow, rather than a new general architecture pattern.
- **Potentially novel:** a particular schema, diagnostic method, or integration could
  be novel, but this review does not establish that. Such a claim would require
  comparison with relevant motion-capture and scientific-instrument systems.
- **Still to demonstrate:** that a fresh client can interpret each message correctly,
  that object lifetimes follow the ownership rules, and that UI-to-disk output
  policies preserve the intended scientific meaning.

This landscape gives us names for discussing the design and criteria for reviewing
it. It does not substitute for the source-level audit or the scientific validation.

## Next source-level pass

The [processing outputs and object ownership audit](processing-ownership-audit.md)
now traces the normal mocap publication path and the realtime apply path. It identifies
specific gaps between planner capability, exposed commands, and declarative configuration.

Trace processing mode/defaults and output ownership from UI to disk, then trace
camera-group and realtime-pipeline creation/disposal. Audit fully self-describing
message contents and client interpretation against those concrete workflows.

sBasically, we're just gonna check the current software architecture and see how well it actually aligns with these patterns and architectural principles and philosophies described and defined above. And then we're going to do an audit of the ways that we don't comply with that system, and then we're going to work on making ourselves comply with that system so we have a nice and coherent architecture throughout the FreemoCap software
