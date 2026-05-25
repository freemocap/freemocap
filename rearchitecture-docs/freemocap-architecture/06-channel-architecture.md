# Channel Architecture

> Step 3 (Separate Python Concerns) + Step 4 (Design Rust) — where Python's PubSub infrastructure is replaced with typed channels.

## The Problem

Pipeline threads (distributor, camera nodes, aggregator) must communicate. Commands must reach running nodes. Frame data must flow from distributor to cameras to aggregator. Config changes must propagate instantly.

### Invariants

- Config updates propagate to running nodes without polling PubSub
- Clean shutdown: closing a channel must not leave receivers hanging
- Camera nodes send outputs to exactly one aggregator
- Distributor fans out to exactly N camera nodes
- All channels are typed at compile time — no `isinstance()` checks

## Python's Solution: PubSub

The Python pipeline uses `PubSubTopicManager` with 7+ topics:

| Topic | Publisher | Subscribers |
|-------|-----------|-------------|
| `ProcessFrameNumberTopic` | Aggregator | All CameraNodes |
| `PipelineConfigUpdateTopic` | Pipeline (via manager) | All CameraNodes, Aggregator |
| `CameraNodeOutputTopic` | CameraNodes | Aggregator |
| `SkeletonInferenceResultTopic` | SkeletonInferenceNode | Aggregator |
| `AggregationNodeOutputTopic` | Aggregator | Pipeline (websocket relay) |
| `PipelineTimingTopic` | All nodes | TimingReporter |
| `VideoNodeOutputTopic` | VideoNodes | PosthocAggregator |

Each topic holds `list[multiprocessing.Queue]` — one per subscriber. Messages are pickled. Subscriptions must be created in the main process (Windows `spawn` limitation).

## Rust's Solution: Typed Channels

All PubSub collapses into typed `std::sync::mpsc` channels. No pickle, no `isinstance()`, no topic registry.

### Channel Catalog

```
┌──────────────────┬──────────────────────────┬──────────────────────────────┐
│ Connection       │ Channel Type             │ Purpose                      │
├──────────────────┼──────────────────────────┼──────────────────────────────┤
│ PipelineMgr →    │ mpsc::Sender<            │ Config updates, shutdown     │
│   Distributor    │   PipelineCommand>       │                              │
├──────────────────┼──────────────────────────┼──────────────────────────────┤
│ Distributor →    │ One shared              │ Frame fan-out (all cameras    │
│   CameraNodes    │   Arc<RwLock<Slot>>      │ read same slot under barrier) │
│                  │   + BreakableBarrier     │                              │
├──────────────────┼──────────────────────────┼──────────────────────────────┤
│ PipelineMgr →    │ mpsc::Sender<            │ Config updates, shutdown     │
│   CameraNodes    │   PipelineCommand>       │                              │
│   (one per node) │                          │                              │
├──────────────────┼──────────────────────────┼──────────────────────────────┤
│ CameraNodes →    │ mpsc::Sender<            │ Per-frame detection output   │
│   Aggregator     │   CameraNodeOutput>      │                              │
│   (one per node) │                          │                              │
├──────────────────┼──────────────────────────┼──────────────────────────────┤
│ PipelineMgr →    │ mpsc::Sender<            │ Config updates, shutdown     │
│   Aggregator     │   PipelineCommand>       │                              │
├──────────────────┼──────────────────────────┼──────────────────────────────┤
│ Aggregator →     │ Arc<Mutex<               │ Latest processed output      │
│   Python relay   │   Option<AggregatorOutput│ (Python polls this slot)     │
│                  │ >>                       │                              │
└──────────────────┴──────────────────────────┴──────────────────────────────┘
```

### Why `mpsc` and Not `broadcast` or `watch`

- **Distributor → CameraNodes**: `Arc<RwLock<Slot>>` + `BreakableBarrier` instead of channels. All cameras read from the same memory under a shared lock. No data copying, no per-camera channels. The barrier ensures they all read the same version.
- **CameraNodes → Aggregator**: Per-camera `mpsc` channels. The aggregator blocks on `recv()` for each camera — zero CPU when waiting.
- **Command channels**: Per-node `mpsc` channels. `try_recv()` at loop top gives zero-latency command processing.
- **Aggregator → Python**: `Arc<Mutex<Option<AggregatorOutput>>>`. Same polling pattern as skellycam's `latest_frontend_payload`.

### Why `std::sync::mpsc`, Not `tokio::sync::mpsc`

The pipeline runs on `std::thread::spawn` — OS threads, not tokio tasks. `std::sync::mpsc` has zero async overhead. Only the WebSocket relay (Python `asyncio`) involves async code.

### Command Enum

```rust
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PipelineConfig {
    pub charuco_config: CharucoDetectorConfig,
    pub triangulation_enabled: bool,
    pub filter_config: FilterConfig,
    pub skeleton_enabled: bool,
}

pub enum PipelineCommand {
    UpdateConfig(PipelineConfig),
    Shutdown,
}
```

Each node receives a clone of the config. Nodes apply changes at the top of their next loop iteration.

### Shutdown Sequence

1. Python calls `pipeline.shutdown()` → PyO3 bridge sends `PipelineCommand::Shutdown` to all node command channels
2. Each node's `try_recv()` returns `Ok(Shutdown)` → breaks out of main loop
3. Distributor calls `barrier.break_barrier()` → releases all camera nodes from barrier with `false` return
4. All channel `Sender`s are dropped → receivers get `TryRecvError::Disconnected`
5. `JoinHandle::join()` called on all thread handles
6. `PyPipeline.drop()` ensures shutdown if Python forgets

## What Was Eliminated

| Python Artifact | Why Eliminated |
|----------------|----------------|
| `PubSubTopicManager` singleton | Channels are fields on `Pipeline` struct |
| 7+ topic classes + `TopicTypes` enum | Channel type parameters + `Arc` slots distinguish message types |
| `multiprocessing.Queue` per subscriber | Rust channels are the primitive — no per-subscriber queues |
| `TopicMessageABC` base class | Rust enum variants carry data |
| `create_topic()` factory | Channel creation is `mpsc::channel()` |
| `isinstance()` type checks in PubSub handlers | Compile-time generics |
| Pickle serialization of all messages | `Arc` ref bump or typed channel send |
| Polling subscription queues | `recv()` blocks; `try_recv()` for non-blocking |
| `overwrite=True` drain loop | `Arc<Mutex<Option<T>>>` swap is O(1) |
