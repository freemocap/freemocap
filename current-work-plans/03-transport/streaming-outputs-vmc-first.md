# Streaming outputs and clients: VMC-first proposal

2026-11-01. Supersedes the order and standalone-output-package recommendation in
`streaming-ecosystem-next-phase.md`. The completed JS/TS checklist and its evidence
remain unchanged. This is a two-level planning proposal, not implementation approval.

## Recovered intent and architecture

VMC and LSL are outputs running inside the FreeMoCap server's lifecycle. The user
configures and starts them from the UI through HTTP, and the server transmits motion
to external consumers. Client SDKs instead run in the consuming application: they
also execute at runtime, but do not need to be hosted inside the FreeMoCap server.
Package location and runtime location are separate decisions. We do not need new
top-level output repositories to implement the requested server feature.

The existing maintained `hub-and-adapters.md` and `http-control-plane.md` already
describe these server outputs and mark them unimplemented. The archived strategy
adds app-owned lifecycle, stream IDs, multiple destinations, idle startup, ephemeral
configuration and scoped errors. Reuse that intent. Do not revive its outdated
LSL-first order, schema-once transport, old pub/sub tap or automatic assumptions
about humanoid rest frames. VMC now comes first by explicit user instruction.

The actual source path is:

1. `FreemocapApplication.wait_for_realtime_result()` and
   `get_latest_aggregator_outputs()` expose the live pipeline results.
2. `core/streaming/message_composer.py` and its producers compose self-describing
   numeric channels and model metadata; the WebSocket relay currently consumes them.
3. Add server output consumers at that boundary, independently of browser sessions.
   Reuse composition/metadata caches and owned numeric data; do not make a loopback
   WebSocket connection or repeat CBOR encoding/decoding merely to send VMC.
4. The application owns output startup, status and teardown; each protocol emitter
   consumes supplied data and owns its outgoing transport, not the capture pipeline.

Outputs must work with no WebSocket client connected. Inspect shared result events
and per-pipeline cursors before adding another consumer: a connection-owned frame
cursor or destructive event read must not become shared output state. Bound each
output's buffering and keep slow receivers from blocking capture or the UI stream.

## Proposed source placement

Paths below are relative to their owning checkout and proposed, not created.

| Behavior | Placement | Ownership reason |
| --- | --- | --- |
| App-managed output instances, status and teardown | Core `freemocap/core/streaming/outputs/manager.py`, integrated through `freemocap/app/freemocap_application.py` | Coordinates pipeline results, application lifetime, API and status |
| FreeMoCap channel/model projection into VMC or LSL and transport emission | Core `freemocap/core/streaming/outputs/vmc.py` and later `lsl.py` | Adapts Core's composed stream and source identity to external protocols; receives data, never drives detector/geometry internals |
| Reusable coordinate, parent/local pose and rest-frame mathematics | Existing Forge `skellyforge/core/math/geometry/coordinate_systems/`, `core/math/kinematics/coordinate_frame_ops.py`, and public skeleton pose interfaces | Standalone geometry responsibility; no Core-dependent algorithms or duplicate math in protocol modules |
| Output configuration, discovery, start/status/stop | Core `freemocap/api/http/streaming/`, normal router registration | Application command/resource surface |
| Output form, observed status and stop controls | Core UI `src/components/control-panels/streaming-outputs/`, using the JS SDK | UI presentation and server control |
| New HTTP operation bindings and operation coverage | Existing JS SDK source/generation and fixtures | Keep UI serialization in the reusable SDK |

Core's protocol modules are application adapters, not a general-purpose geometry
library. If a conversion can operate solely on a Forge pose and is independently
useful, put that conversion in Forge and call it. Prefer an existing codec/library
or recover the old prototype before writing generic OSC infrastructure. The archive
mentions a `freemocap_vmc/` prototype; it was not found in the inspected workspace
locations, so its existence is not evidence of working current code. No package
move, new repository, dependency installation or generic plug-in registry is required
by this proposal. Registry abstraction can follow evidence from actual outputs.

The endpoint behaviors are already part of the intended design. Their final names
and payloads still need reconciliation with the current API conventions: protocol
capabilities/configuration; create output; list/get output by ID; stop output by ID.
The archive's `/streaming/start` spelling is not an existing accepted route. Update
the route inventory, SDK and app-state schema only for this new surface.

## Level 1: proposed global milestones

- [ ] **1.** Complete canonical integration and validation of the existing JavaScript/TypeScript SDK and default-app changes.
- [ ] **2.** Deliver server-managed VMC streaming with HTTP and UI controls and a verified receiving-avatar demonstration.
- [ ] **3.** Deliver server-managed LSL streaming through the same output lifecycle and verify reference values and clock mapping with an independent receiver.
- [ ] **4.** Deliver a standalone Python SDK covering server controls, live decoding and recording access with runnable conformance-tested examples.
- [ ] **5.** Deliver a standalone Rust SDK covering server controls, live decoding and recording access with runnable conformance-tested examples.
- [ ] **6.** Extend the Blender integration with server controls, live motion and recorded playback while retaining its existing import and animation behavior.
- [ ] **7.** Deliver verified Unity, Unreal and Godot integration examples using VMC where suitable and direct clients for remaining control, data and playback requirements.
- [ ] **8.** Verify the cross-target compatibility matrix and deliver versioned installation instructions, packages and acceptance evidence.

Global 1 is coordinator-owned integration of completed work, not a request to repeat
SDK development. Root reports landing status; this note does not guess it. VMC is
the first new output milestone. These numbers identify portfolio milestones rather
than imposing one serial owner over the ecosystem. The coordinator can assign
Python/Rust and host work in parallel after interfaces are stable; each active owner
executes its approved child list linearly. LSL reuses the VMC milestone's lifecycle.
Unity/Unreal/Godot can start receiver validation as VMC becomes available; they need
not wait for Python, Rust or Blender. Expand other milestones when they become active.

## Level 2: proposed current VMC checklist (global 2)

- [ ] **2.1.** Reconcile the existing VMC strategy and current pose interfaces into an executable mapping and output-control contract with known-pose acceptance fixtures.
- [ ] **2.2.** Implement the server-owned output lifecycle and independent frame consumer with bounded buffering, idle startup, status and clean shutdown tests.
- [ ] **2.3.** Implement VMC pose projection and OSC/UDP emission using existing geometry interfaces and verify packet values, rest frames and coordinate conversions independently.
- [ ] **2.4.** Add output discovery, start, status and stop endpoints with SDK bindings and integration tests for concurrent outputs and scoped failures.
- [ ] **2.5.** Add the UI streaming-output controls and verify that displayed state follows the server through start, stop, failure and reconnect.
- [ ] **2.6.** Demonstrate VMC with reference replay and coordinated live capture in an independent avatar receiver, then record measured results and exact reproduction steps.

Task 1 is a bounded contract delta, not another broad discovery/documentation phase.
Reuse the accepted 59-operation baseline, channel contracts, golden fixtures and
reference recordings, reconciling only changed integrated APIs and VMC additions.
Select the initial receiver/version and supported humanoid profile there. Verify
which measured channels can supply body, fingers and expressions; describe emitted
capabilities positively and fail clearly when requested data cannot be supplied.

Acceptance details for the child list:

- Verify root placement, unit conversion, quaternion component order, handedness,
  parent-relative rotations and receiver rest-pose interpretation using independent
  known transforms. Our existing wxyz local rotations are not by themselves proof
  of VMC avatar compatibility. Reuse Forge's animation-math/coordinate tests.
- Support multiple output IDs/destinations; report setup errors immediately and
  isolate runtime errors to the affected output. Idle means waiting for source
  data; server restart does not silently restart old outputs. Test capture restart,
  model/source changes, stale data and disposal of every owned socket/task.
- Verify datagram sizing and packetization, including a non-loopback receiver;
  UDP transmission success is not proof that an avatar received or rendered it.
  Treat absent receivers honestly rather than claiming a connected handshake.
- Keep normal self-describing WebSocket output and recorded-data readers passing;
  no metadata delta protocol, silent pose substitution or per-point frame-path
  dictionaries. Do not add image encoding work just for a numerical output.
- Replay and stored-data comparisons use the existing reference corpus. Replay
  tests emission but not fresh inference; actual camera/GPU acceptance gets a
  coordinated slot. Observe the receiving avatar and compare numeric evidence,
  rather than accepting either appearance or a packet round trip alone.

## Engine compatibility: verified claim and remaining work

The official VMC specification lists EVMC4U for Unity, VMC4UE/VRM4U for Unreal,
and Godot XR VMC Tracker for Godot. This supports prioritizing one VMC sender
as a route into these environments [@vmcProtocolSpecification]. It is not evidence
that our current segment frames already drive all three correctly. Receiver,
engine, avatar/VRM and plug-in versions must be selected and exercised; none were
launched during this planning pass. Official source:
<https://protocol.vmc.info/english>.

VMC supplies a motion compatibility route. It does not implement FreeMoCap's full
HTTP controls, arbitrary scientific channels, recording discovery, seeking or
loading a processed recording into a host timeline. Retain those requirements in
SDK/host milestones. Existing receiver examples may substantially reduce host work;
do not promise a complete native integration merely from successful VMC motion.

## Decisions and next action

No unresolved product question blocks this proposal: VMC first, server-managed,
UI-triggered, with the full SDK/recording roadmap retained. Exact target bone/rest
mapping, endpoint spelling, supported receiver versions and LSL clock mapping are
bounded engineering checks, not reasons to restart requirements discovery. The
source placement above is a recommendation pending packet alignment, not a file move.

Review the global milestones and current VMC child list together. Freeze approved
wording and update the active child list after each completed task; complete its
parent only after all child acceptance evidence exists. Changes to milestone scope
or dependencies must be explicit. The coordinator owns integration/Git sequencing
and the shared skill's two-level workflow update; no parallel Git operation here.
