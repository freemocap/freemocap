# Streaming ecosystem: proposed next phases

Status: planning proposal, awaiting approval of the displayed checklist. The
completed six-step W6 JS/TS checklist remains frozen in `server-sdk-handoff.md`.
It completed one foundation, not the streaming ecosystem. No new implementation,
camera session, Git mutation, or publication is implied by this proposal.

## What exists

| Target | Inspected state | User-visible outcome still needed |
| --- | --- | --- |
| JavaScript/TypeScript | Standalone private `@freemocap/client` source, 59 typed HTTP operations at the tested baseline, WebSocket decoding, recording readers, CLI examples, default-app integration | Review/integration/publication; track subsequent server contract changes |
| Python | Hardware-validation CBOR receiver and integration scripts, not a complete standalone SDK | Full server control, decoded live channels, recording access, runnable examples |
| Blender | Existing Parquet/native-segment and legacy animation import/export; no WebSocket/CBOR receiver found in add-on Python sources | Live reception, server controls, remote recording selection, shared scene presentation |
| Rust | No Rust server SDK delivered by W6 | Full server control, decoded channels, recording access, runnable examples |
| LSL / VMC | Neither output delivered by W6 | HTTP-managed outputs, independent receivers, explicit conversion contracts |
| Unity / Unreal / Godot | None of these connectors delivered by W6 | Installable connectors, controls, live scene updates and recorded playback |

Inventory is bounded to the W6 workspace and relevant canonical source, not a
claim that no prototype exists elsewhere. Before implementing each target, search
its intended repository and reconcile any existing prototype with these contracts.
The canonical Blender checkout is clean on `sfn26`, matching Core's declaration;
its package supports Python >=3.9. It is outside the isolated W6 worktree.

## Established contracts to preserve

- HTTP is the command/resource surface; WebSocket messages remain fully
  self-describing. Late join and reconnect must not require a prior metadata
  handshake. Reuse metadata identity/caching without making decoding stateful.
- Follow `message-protocol.md`, `connection-ownership.md`,
  `../01-data-model/ontology.md`, `../00-foundation/conventions.md`, and the
  recording contract. Trace the actual encoder, connection decoder caches,
  model subscriptions and worker buffer lifecycle before changing an interface.
- Preserve channel/model identities, source clocks, dense numeric arrays,
  missing/invalid values, dtype, buffer ownership and explicit coordinate frames.
  Test live and recorded paths against the same source observations without
  pretending that their storage representation or timing is identical.
- Language clients provide the complete supported control/resource surface plus
  decoding and recording access; they do not require a renderer or Core imports.
  Engine connectors provide useful selected controls and scene presentation;
  they need not expose every server operation as a button.
- A protocol adapter advertises its supported channels and information losses.
  It must reject unsupported mappings rather than fabricate poses or timestamps.
- Keep protocol conversion in an independent adapter package and scene behavior
  in its host connector. Core owns only integration/lifecycle coordination that
  actually spans components. Component detector/geometry algorithms stay owned.

## Proposed global checklist

- [ ] **1.** Establish the shared client/output contracts and a reusable live-and-recorded conformance corpus against the chosen integrated server baseline.
- [ ] **2.** Deliver a standalone Python SDK with complete HTTP control, WebSocket decoding, recording access, and verified runnable examples.
- [ ] **3.** Extend the Blender add-on with server controls, live scene updates, and recorded playback, and demonstrate the complete Python-to-Blender workflow.
- [ ] **4.** Deliver a standalone Rust SDK that passes the shared conformance suite and runs equivalent control, streaming, and recording examples.
- [ ] **5.** Deliver an HTTP-managed LSL output and verify its schema, timing, values, and lifecycle with an independent receiver.
- [ ] **6.** Deliver an HTTP-managed VMC output and verify its supported pose mappings, coordinate conversion, and lifecycle with an independent receiver.
- [ ] **7.** Deliver a Unity connector with server controls, live scene updates, and recorded playback verified in a minimal sample scene.
- [ ] **8.** Deliver an Unreal connector with server controls, live scene updates, and recorded playback verified in a minimal sample scene.
- [ ] **9.** Deliver a Godot connector with server controls, live scene updates, and recorded playback verified in a minimal sample scene.
- [ ] **10.** Verify the integrated compatibility matrix and complete installable packages, walkthroughs, and per-target acceptance evidence.

Expand each global task into its bounded owner checklist when reached. Approval
freezes wording and order; completion requires evidence, not just code presence.
Marking a child checklist complete never marks the entire ecosystem complete.
Publication remains a separately authorized Git/release operation.

### First expansion: global task 1

- [ ] **1.** Reconcile the integrated server inventory and existing client/Blender interfaces into a versioned capability and ownership matrix.
- [ ] **2.** Specify control, message, recording, clock, coordinate, lifecycle, and failure contracts with explicit acceptance cases for every target.
- [ ] **3.** Build the reusable conformance corpus from reference recordings and live-form messages, verify it with independent source values, and record the next Python/Blender implementation checklist.

The accepted JS contract is the starting point. Reconcile newer server work;
do not silently pin new clients to the old 59-operation count or rewrite an
established transport decision. Register official protocol/engine sources and
citation checks when external specifications are researched in the owning repo.

## Bounded owner outcomes and dependency gates

These are expansion boundaries, not additional approved execution checklists.
Each owner follows contract/example, implementation, independent validation,
and user-run handoff in that order.

| Owner target | Contract/implementation boundary | Completion demonstration |
| --- | --- | --- |
| Python | Agree supported Python versions and dependency packaging with Blender first; provide typed operations, cancellation/errors/tasks/assets, independent message decoding and recording readers | CLI inspects server, issues a selected control operation, receives live/replayed frames, reads reference recording; values and clocks match independent evidence |
| Blender | Reuse existing importers/scene builders; separate network work from host scene mutation; avoid bringing the Core inference environment into Blender | Panel connects to explicit server, shows status, controls pipeline/capture, displays live landmarks/segments, lists and loads a processed recording, scrubs, disconnects cleanly |
| Rust | Stable public ownership/array/error API, complete control/resource bindings, asynchronous lifecycle and recording access | Equivalent language examples plus shared corpus, reconnect, cancellation and retained-buffer checks |
| LSL | Specify stream identity, numerical schema, clock mapping, sampling/missing data and lifecycle; isolate protocol library/dependencies | Start/status/stop through HTTP; independent receiver verifies reference values and timing; repeated start/stop and failures leave no output running |
| VMC | Specify supported skeleton/pose mapping, source and target frames, rest-pose requirements, timing and intentional losses; avoid claiming arbitrary landmark data is a valid avatar pose | Start/status/stop through HTTP; independent receiver checks synthetic known poses and reference motion; unsupported model receives a clear failure |
| Unity | Choose native bindings versus a shared library using a packaging prototype; implement minimal points/segments before optional avatar retargeting | Install sample, connect/control, see live data, load/scrub recording, reconnect and unload without lingering work |
| Unreal | Make the same binding decision for its host/toolchain; isolate network and scene ownership | Same observable scene/control/playback lifecycle with host-native packaging |
| Godot | Make the same binding decision for its host/toolchain; isolate network and scene ownership | Same observable scene/control/playback lifecycle with host-native packaging |

First visible milestone: **Python plus Blender**. A user can control an actual
server from Blender, see motion in the scene, then load and scrub reference
motion through the existing animation machinery. This uses existing Blender work
instead of replacing it. Basic points/segments are the acceptance target;
arbitrary avatar retargeting is a separately bounded feature.

After task 1, Rust, protocol outputs and engine packaging investigations have
independent seams. The coordinator may propose separate owner checklists and
revised sequencing for these lanes; this does not silently parallelize the
approved global order or create new chats. Blender depends on Python's agreed
runtime and public interfaces. Unity/Unreal/Godot are not automatically dependent
on Rust; choose that dependency only after testing host packaging. Output control
routes must be reconciled with the server owner and added to client coverage.

## Evidence required throughout

Use both reference recordings in their posthoc forms and production-encoded
live-message replay. Compare independent expected numbers and source timestamps;
do not test a decoder only against its own encoder. Include multiple models,
late join, changing metadata, missing/invalid channels, reconnect, server failure,
slow consumers, bounded queues and clean stop. Measure latency and dropped frames
without replacing source time with display arrival time.

Replay proves transport and playback behavior; it is not fresh camera inference.
Reserve a coordinated exclusive camera/GPU slot for actual live acceptance after
headless tests pass. Each host also needs a real runtime check: headless conformance
alone does not prove Blender/Unity/Unreal/Godot scene behavior. Preserve source
datasets; generated outputs and logs go into verified ignored artifacts.

Keep the existing JS app passing as new targets arrive. Report tested server,
SDK, protocol and host versions, source hashes and exact launch steps. Distinguish
local tested source from installed artifacts, published packages and untested hosts.

## Current workspace and review

The isolated workspace is already
`C:/Users/jonma/.codex/worktrees/w6-server-sdk/project`; do not create a redundant
outer worktree. It contains isolated Core, SDK source and public documentation.
Future Blender edits require an isolated add-on checkout before implementation;
canonical editable dependencies remain shared and are not isolated by this root.
No new worktree or Git mutation was performed during this planning pass.

See `server-sdk-local-demo.md` for the current user's local review recipe.
