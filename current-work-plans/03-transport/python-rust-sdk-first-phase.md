# Python and Rust SDKs: first phase proposed for approval

2026-11-02. This expands global6 of streaming-output-dependencies.md. The user
wants both clients planned and implemented. The first bounded implementation
phase delivers a complete Python client and a language-neutral corpus that Rust
will also use; the next phase delivers Rust against the same contract. Neither
client requires a renderer. This is a ready-to-approve proposal, not a claim that
implementation has started or that a new checklist was already approved.

Preserve the existing proposed child wording from streaming-ecosystem-status-roadmap.md.
Approve and execute6.1–6.3 first, then6.4–6.5; no package publication or environment
changes are implicit in this proposal. Root coordinates owners and Git operations.

## First phase: full Python SDK and shared contract

- [ ] **6.1.** Reconcile the canonical operation ledger and recording/message contracts into a shared conformance corpus and agreed Python/Rust runtime support matrix.
- [ ] **6.2.** Implement the standalone Python client's complete controls, asset/task access, self-describing frame decoding and recording readers with public lifecycle and array contracts.
- [ ] **6.3.** Validate Python examples against both reference recordings, encoded live-form replay and server failures, including the intended Blender Python runtime.

6.1 produces a reviewed capability matrix against the current canonical operation
ledger (65 at this inspection), the source OpenAPI fingerprint, message/recording
contracts, supported runtime/package decisions and independent fixtures. Inventory
existing packages before choosing a new location. Keep the client independently
installable without importing Core, Tracker, Cam or Forge. Inspect Blender's actual
embedded Python before fixing the supported Python range; specify Rust MSRV and
async/runtime assumptions before Rust implementation. Do not use the old59-operation
compatibility record as the current inventory or redesign self-describing transport.

6.2 covers every supported HTTP operation, including outputs and no-body VMC start,
raw assets/ranges, long-running task state and explicit cancellation, plus WebSocket
connect/reconnect/close and all supported message kinds. Expose typed metadata,
dense numerical arrays, exact source timestamps and stable retained data ownership.
Specify request cancellation separately from server-task cancellation. Recording
access must preserve recording/run/revision identity and resolve HTTP resources
without assuming server filesystem paths are local. Rendering is out of scope.

6.3 proves the full operation inventory and examples with independent expected
data from both reference recordings and production-encoded live-form replay.
Cover fresh-decoder late join, changing metadata, multiple models, invalid/missing
values, dtype/byte order, retained buffers, reconnect, errors, task cancellation,
slow consumers and clean shutdown. Verify Python packaging/import in a compatible
Blender runtime without loading the inference environment; scene integration is
global7.1. Fresh camera inference remains a separately scheduled acceptance check,
not something to start while the user owns the application.

Completion artifact: installable local Python package, runnable control/stream/
recording examples, operation coverage ledger and versioned conformance evidence,
with actual skipped/unsupported cases stated. A thin REST wrapper alone is not a
complete client. No arbitrary subset of control operations substitutes for coverage.

## Next phase: equivalent Rust client

- [ ] **6.4.** Implement the standalone Rust client's equivalent public controls, streaming and recording interfaces with explicit ownership, cancellation and errors.
- [ ] **6.5.** Validate Rust against the same independent corpus and runnable examples, recording supported versions and installation evidence.

Rust has the same supported control/resource/message/recording scope. Its public
buffer and async lifecycle must be idiomatic and explicit rather than copying
Python's object model. Reuse corpus expectations, not Python implementation code.
Do not make Rust a dependency of Unity/Unreal/Godot until a host packaging prototype
supports that choice. Host adapters, native Skelly rendering, Skelly VRM and protocol
receiver acceptance remain separate deliverables.

## Review boundary

All work remains under established ownership, editable dependency and generated
artifact rules. Package location, dependency additions and runtime choices are
concrete outputs of6.1, to be reviewed before setup changes. No new worktrees,
installs, server launches, capture or Git mutations occurred during this planning
pass. The coordinator should present the first-phase checklist for approval and
then assign its implementation owner; no additional product interview is needed.
