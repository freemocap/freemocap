# Streaming ecosystem: current status and next owner expansions

2026-11-02 update: the user reports that normalized VMC now receives/drives the
avatar. This establishes basic user-observed rendered motion, not full fidelity,
finger, placement or proportion acceptance. The user subsequently required fingers
on by default, no finger toggle, and separate VMC/LSL sections in the same Outputs
dropdown, each with its own settings and Start/Stop. Canonical integration owns
implementation/testing; the old finger-enabling flow and generic protocol-selector
instructions below are historical. Global4.3 stays open for full reference/live evidence.
See python-rust-sdk-first-phase.md for the ready-to-approve6.1–6.3 first phase
and subsequent Rust6.4–6.5 phase. Earlier implementation evidence below is retained.

Reconciled on 2026-11-01 against canonical Core at
`C:/Users/jonma/code-stuff/github/freemocap/project/repos/freemocap` and its
`packages/freemocap-client` SDK. This document is authored in the isolated W6
checkout for coordinator review. It describes canonical source, which is newer
than the isolated implementation. Do not copy isolated runtime files over it.

The approved nine global tasks and existing children remain frozen in
`streaming-output-dependencies.md`. The expansions below are proposals for the
next owners, not authorization to start every target tonight. Root serializes
the user's authorized commits/pushes. This documentation pass changes no Git
state, dependencies, running applications or hardware. No unattended monitoring
or indefinite background execution is promised.

## Implemented versus accepted

| Global | Implemented or verified | Still required |
| --- | --- | --- |
| 1: JS/TS | Canonical standalone SDK under Core's packages directory; 65 HTTP operations, self-describing WebSocket decoding, recording readers and app integration; lazy compressor loading avoids eager WASM startup | Coordinator's final publication/clean-checkout report; existing compatibility records retain their historical baselines |
| 2: shared outputs | Owned lifecycle, bounded independent consumers, discovery/start/status/stop, no-body VMC start; Outputs toolbar dropdown with advanced settings collapsed and no timer polling | Preserve this canonical implementation during publication; this global is locally complete |
| 3: LSL | Schema/clock/topology and missing/drop contracts, native outlets, independent reference-value tests; corrected camera timestamp identity verified on 40 live frames | Live numerical acceptance with two real observing cameras; supported-platform installation evidence |
| 4: VMC | OSC/UDP adapter, normalized VRM0 default plus original-reference option, partial ancestor-valid bones; independent CPU projection tests | Correct rendered motion, root placement and partial-body behavior on the actual receiver, then coordinated live acceptance |
| 5: native Skelly | Separate mesh owner owns implementation and evidence | Use that owner's current report; this reconciliation makes no completion claim |
| 6: Python/Rust | Contracts and JS reference implementation available; W6 has not delivered complete Python/Rust SDK packages | Standalone clients with full control, streaming and recording access |
| 7: hosts | Existing Blender recording/scene machinery; Unity editor and EVMC package provisioned by user; standalone VSeeFace used for VMC investigation | Blender live connection and controls; actual Unity/Unreal/Godot connectors and recorded/live demonstrations |
| 8: Skelly VRM | Optional asset decision remains separate | Evaluate with mesh owner; do not block ordinary streaming or native visualization |
| 9: compatibility | Existing reference corpus, SDK inventory and test evidence | Cross-target version matrix, clean installation and reproducible host demonstrations |

Source presence is not visual acceptance or publication. The canonical integration
owner reports 18 normalized-projector CPU tests and a quick-start HTTP test passed;
five real stream frames projected offline to finite 13-bone poses. Those are
numeric evidence, not a rendered receiver pass. See canonical
`vmc-receiver-profiles.md` and the integration owner's checkpoint for exact scope.

The W6 live03 LSL report covers 40 frames over 1.79 seconds: exact camera CSV
identity and source mean passed, mapped timestamp error was zero, and reported
gaps agreed. All 19,840 numeric values in that window were nonfinite. Recorded
camera 7599/index 2 showed an inactive Iriun placeholder while ef51 showed the
scene; this invalidated the two-view numerical acceptance setup. It does not
describe all later VMC frames or the user's subsequent standard-app selection.
Original live02/live03 evidence remains unchanged. Never relabel camera IDs or
relax clock tolerances to turn a failed acceptance check into a pass.

## Current user operation

In the standard app, open **Outputs → Start VMC**. In Swagger on the actual
backend origin, use **POST /freemocap/streaming/vmc/start → Try it out → Execute**;
no JSON is required. Default destination is localhost port 39539. The endpoint
starts or reuses a default output; it does not start cameras or inference.
An output may be idle until a source exists. Advanced configuration and the
generic output API remain available. Stop an output using its displayed control
or DELETE `/freemocap/streaming/outputs/{output_id}`.

Use the app's actual backend URL, not an assumed fixed port. Existing outputs
retain their profile; after the user loads updated backend code, a new output
uses the new default. VSeeFace is the standalone receiver route; Unity project
setup is reserved for later engine integration. Sending counters do not establish
receipt, valid pose or correct avatar rendering. Do not automatically recenter
measured coordinates to hide receiver camera or root-placement issues.

## Next two-level roadmap

Global numbers below refer to the approved plan. Existing 3.3 and 4.3 keep their
exact wording and remain open. New 6.x/7.x children are proposed expansions to
review when their owner starts; they do not replace or reorder the global plan.

### Global 3: finish LSL acceptance

- [ ] **3.3.** Validate reference replay and coordinated live capture with an independent LSL inlet or recorder, comparing values, timestamps, sample counts and cleanup.

Retain the completed reference replay evidence. Before a new scheduled live run,
verify actual camera content and calibration association, then compare finite
source values, declared missing data, channel identity/order, exact acquisition
provenance, mapped measurement time, frame gaps and cleanup. Test installation
through the standard Core dependency set on each claimed platform. The owner made
pylsl a normal dependency on2026-11-02; the coordinator verified its canonical
installation and native load. No hardware work is
authorized merely by this proposed next-step note.

### Global 4: finish VMC receiver acceptance

- [ ] **4.3.** Demonstrate reference replay and coordinated live motion on the selected receiver's existing avatar, and record numeric and visible acceptance evidence.

Use the canonical normalized binding and current partial-bone behavior. Check
asymmetric known poses, reference playback, measured root placement and missing
branches on the actual avatar; only then claim visible compatibility. Preserve
original-reference mode as a separate profile. Receiver-held old transforms and
position-application settings need observation, not invented source measurements.
User-directed viewing can supply visual evidence; UI automation remains prohibited.

### Global 6: deliver Python and Rust clients

- [ ] **6.1.** Reconcile the canonical operation ledger and recording/message contracts into a shared conformance corpus and agreed Python/Rust runtime support matrix.
- [ ] **6.2.** Implement the standalone Python client's complete controls, asset/task access, self-describing frame decoding and recording readers with public lifecycle and array contracts.
- [ ] **6.3.** Validate Python examples against both reference recordings, encoded live-form replay and server failures, including the intended Blender Python runtime.
- [ ] **6.4.** Implement the standalone Rust client's equivalent public controls, streaming and recording interfaces with explicit ownership, cancellation and errors.
- [ ] **6.5.** Validate Rust against the same independent corpus and runnable examples, recording supported versions and installation evidence.

Start from the current 65-operation ledger, not historical counts. Preserve exact
timestamps, dense numeric types, model/channel identity, self-description, metadata
reuse and buffer ownership. A client must decode a frame without prior metadata.
Do not require Core imports or a rendering engine. Python compatibility must fit
Blender's actual embedded runtime without importing the inference environment.
Reuse independent expected values; testing a decoder only against its encoder is
insufficient. Fresh hardware acceptance is separately scheduled after CPU checks.

### Global 7: deliver host connectors

- [ ] **7.1.** Extend Blender through the agreed Python client with selected server controls, live scene updates and remote recording playback using its existing scene/import machinery.
- [ ] **7.2.** Deliver a Unity sample connector with selected controls, live channels and recorded playback, selecting bindings through an actual packaging prototype.
- [ ] **7.3.** Deliver an Unreal sample connector with the same user workflows and verified host-owned scene updates and cleanup.
- [ ] **7.4.** Deliver a Godot sample connector with the same user workflows and verified host-owned scene updates and cleanup.
- [ ] **7.5.** Verify installation, reconnect, playback scrubbing and clean unload in each claimed host and record versioned demonstrations.

For each host, keep networking/decoding separate from scene-thread mutation and
reuse the same live/recorded presentation boundary. Minimal points and segments
establish a full-data connector before optional avatar work. Existing VMC receivers
can cover an avatar demonstration but do not supply all controls, numerical
channels or recorded-data access. Do not impose Rust as an engine dependency until
packaging evidence supports it. Native mesh geometry and reusable reconstruction
remain with their current owners; a connector is not a new scientific skeleton.

## Documentation gaps and review handoff

The earlier `streaming-ecosystem-next-phase.md` proposal is historical; the approved
ordering is `streaming-output-dependencies.md`. The contract delta now distinguishes
historical 64-operation evidence from canonical 65-operation behavior. Keep old
compatibility evidence rather than silently rewriting its tested baseline.

Before marking global 9 complete, add client/host installation and compatibility
tables, receiver profile/version evidence, LSL platform results and exact
live/reference acceptance links. The package remains private until publication
explicitly changes that status; a Git push is not a registry release. Root owns
the current commit/push outcome and other agents' status.

Canonical recovery sources: `shared/server-contract/README.md`,
`freemocap/api/http/streaming/streaming_router.py`,
`freemocap/core/streaming/outputs/vmc.py`,
`freemocap-ui/src/components/control-panels/streaming-outputs/`,
`packages/freemocap-client/src/recording/playback-parquet.ts`, and
`current-work-plans/03-transport/vmc-receiver-profiles.md`.
W6 evidence and the stop/ownership boundary are indexed in
`.test-artifacts/continuity/w6-streaming.md` in the isolated checkout.
