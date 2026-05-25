# System Overview & Integration

> Step 1 (Understand) + Step 2 (Extract Invariants) applied to freemocap-rust's integration with skellycam-rust and skellytracker-rust.

## The Problem

FreeMoCap's real-time pipeline composes camera capture (skellycam) with tracking (skellytracker) into a processing DAG. The Rust re-architecture replaces Python `multiprocessing.Process` nodes with `std::thread` nodes, using typed channels instead of PubSub, and eliminating shared memory ring buffers for pipeline data.

### Invariants

- skellycam owns camera capture and frontend payload encoding
- skellytracker owns detection algorithms (charuco, skeleton)
- freemocap orchestrates: takes frames from skellycam, runs detection via skellytracker, triangulates, filters, publishes
- Same API endpoint paths and JSON shapes (frontend compatibility)
- Real-time configurable from UI (charuco params, filter settings, toggles)
- Works on Windows

## Crate Integration

Freemocap-rust depends on sibling crates via path dependencies:

```
code_repos/github/freemocap/
├── freemocap/
│   ├── freemocap-rust/           ← this crate
│   │   └── Cargo.toml            path = "../../skellycam/skellycam-rust"
│   └── freemocap/                ← Python package
├── skellycam/
│   └── skellycam-rust/           ← camera engine
└── skellytracker/
    └── skellytracker-rust/       ← detection algorithms
```

```toml
# freemocap-rust/Cargo.toml
[dependencies]
skellycam = { path = "../../skellycam/skellycam-rust" }
skellytracker = { path = "../../skellytracker/skellytracker-rust" }
```

## Process Model

Unlike skellycam (which supports both a standalone binary AND a PyO3 module), freemocap-rust is **PyO3-only**. No `main.rs`, no Axum server. Pipeline threads run inside the Python process:

```
Python Process
├── FastAPI server (main thread, tokio via uvicorn)
├── skellycam-rust threads (cameras, gatherer, dispatcher)
│   └── latest_raw_frames + latest_frontend_payload slots
├── freemocap-rust threads (distributor, camera nodes, aggregator)
│   └── latest_aggregator_output slot
└── WebSocket relay (Python async task, polls latest_aggregator_output)
```

The GIL is not a concern: Rust threads doing CPU work (JPEG decode, charuco detection, triangulation) release the GIL via PyO3's `allow_threads` or by never acquiring it in the first place (pure Rust code paths).

## What Python Does vs What Rust Does

| Layer | Python Responsibility | Rust Responsibility |
|-------|----------------------|---------------------|
| skellycam | thin wrapper imports `_skellycam_rust` | cameras, sync, frontend encoding, recording |
| skellytracker | thin wrapper imports `_skellytracker_rust` | charuco detection, skeleton detection, observations |
| freemocap | FastAPI routes, `RealtimePipelineManager`, adapter class | pipeline topology, triangulation, filtering, coordination |

## Logging

Uses the same `tracing` + `tracing-subscriber` setup as skellycam. The subscriber is process-global — skellycam's `init_logging()` initializes it once, and freemocap's logs flow through the same pipeline. Logs are prefixed by crate target (`freemocap::pipeline::aggregator`) so origin is always clear.

## Key Differences from Python Architecture

| Concern | Python | Rust |
|---------|--------|------|
| Node execution | `multiprocessing.Process` | `std::thread::spawn` |
| Communication | PubSub (7+ topics, pickle, per-subscriber queues) | Typed `mpsc` channels |
| Frame data flow | Shared memory ring buffers with DTO/recreate | Channels + `Arc` slots |
| Config propagation | PubSub broadcast + polling | Direct `mpsc::Sender<PipelineCommand>` |
| Shutdown | 3-phase escalating kill + heartbeat monitor | `Drop` impls + channel disconnect |
| Type checking | beartype at runtime | Compile-time type system |
