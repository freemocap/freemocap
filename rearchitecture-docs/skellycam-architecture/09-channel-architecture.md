# Channel Architecture

> Worked example of Step 3 (Separate Python Concerns) + Step 4 (Design Rust) — where the entire Python PubSub infrastructure was replaced with typed channels. See the [re-architecture playbook](../rearchitecture-playbook/).

## The Problem

Camera threads, the gatherer thread, the dispatcher thread, and the WebSocket server must communicate. Commands must reach running cameras. Frame data must flow from cameras to consumers. Recording state must be coordinated.

### Invariants

- Camera settings updates propagate to running cameras
- Startup: cameras must report when ready
- Recording: all cameras must start/stop together
- Framerate stats must flow to WebSocket
- Log records must flow to WebSocket
- Clean shutdown: closing a communication channel must not leave receivers hanging

## Python's Solution: PubSub

A cross-process event bus built on `multiprocessing.Queue`:

```
CameraGroupIPC (one per camera group)
  └── PubSubTopicManager
        └── topics: dict[TopicTypes, PubSubTopicABC]
              ├── UPDATE_CAMERA_SETTINGS
              ├── EXTRACTED_CONFIG
              ├── SHM_UPDATES
              ├── RECORDING_INFO
              ├── RECORDING_FINISHED
              ├── FRAMERATE
              └── LOGS
```

Each topic holds `list[multiprocessing.Queue]` — one per subscriber. `publish(message)` iterates all queues and puts the message. Subscriptions must be created in the main process (Windows `spawn` limitation).

### Python-Specific Decisions

| Mechanism | Why Python Needs It |
|-----------|-------------------|
| `multiprocessing.Queue` for every topic | Cross-process communication requires serialization |
| `PubSubTopicABC` base class + 7 topic classes | Queues are untyped — `isinstance()` checks enforce type safety |
| "Main process creates subscriptions" rule | Windows `spawn` can't create queues in children |
| Polling subscriptions in hot loop | `multiprocessing.Queue.get()` is blocking; need non-blocking check |
| `overwrite=True` drain loop | No `send_replace()` equivalent for queues |
| Pickle serialization of all messages | `multiprocessing.Queue` requires pickling |
| `TopicTypes` enum + `TopicMessageABC` | Runtime type discrimination for untyped queues |

## Rust's Solution: Typed Channels

All of the above collapses into typed `std::sync::mpsc` channels (OS threads, not tokio):

### Channel Catalog

| Connection | Channel | Purpose |
|-----------|---------|---------|
| CameraGroup → Camera | `mpsc::Sender<CameraCommand>` | Shutdown, Configure |
| Camera → CameraGroup | `mpsc::Sender<CameraEvent>` | Ready, Error |
| Camera → Gatherer | `sync_channel<FramePacket>(1)` | Frame delivery with backpressure |
| Gatherer → Dispatcher | `mpsc::channel<MultiFramePayload>()` (unbounded) | Frame fan-out source |
| CameraGroup → Gatherer | `mpsc::Sender<GathererUpdate>` | AddCamera, RemoveCamera |
| CameraGroup → Dispatcher | `mpsc::Sender<DispatcherCommand>` | StartRecording, StopRecording, UpdateConfigs, Shutdown |
| Dispatcher → Recording thread | `mpsc::channel<RecordingFrameData>()` (unbounded) | Per-frame JPEGs + timestamps |
| Recording thread → Caller | `oneshot::Sender<RecordingSummary>` | Stop recording response |
| tracing → WebSocket | `broadcast::channel<LogRecord>` → `mpsc` bridge | Log relay |

### Why `std::sync::mpsc`, Not `tokio::sync::mpsc`

The camera pipeline runs on OS threads (`std::thread::spawn`), not tokio tasks. `std::sync::mpsc` is zero async overhead. The tokio runtime is only used for the HTTP/WebSocket layer.

### Sync Primitive: BreakableBarrier

Not present in the Python architecture because Python has no equivalent. Replaces `should_grab_by_id()` polling:

```rust
pub struct BreakableBarrier { ... }
impl BreakableBarrier {
    pub fn new(total: usize) -> Self;
    pub fn wait(&self) -> bool;         // true = normal, false = broken
    pub fn break_barrier(&self);        // release all
    pub fn set_total(&self, n: usize);  // dynamic participant count
}
```

## What Was Eliminated

| Python Artifact | Why Eliminated |
|----------------|----------------|
| `PubSubTopicABC` base class | Channels are the abstraction |
| `PubSubTopicManager` singleton | Channels are fields on CameraGroup |
| 7 topic classes + `TopicTypes` enum | Channel type parameters distinguish message types |
| 6 message wrapper classes | Rust enum variants carry data |
| `multiprocessing.Queue` for every subscription | Rust channels are the primitive |
| `isinstance()` type checks | Compile-time generics |
| `parent_process() is not None` guard | Threads share creation context |
| `overwrite=True` drain loop | `watch::send_replace()` would be O(1) — not needed here |
| Pickle serialization | `Arc` ref bump, not serialization |
| Polling subscription queues | `recv()` blocks; `try_recv()` for non-blocking |

## Key Differences

| Concern | Python | Rust |
|---------|--------|------|
| Communication primitive | `multiprocessing.Queue` | `std::sync::mpsc` channels |
| Type safety | Runtime `isinstance()` checks | Compile-time generics |
| Message routing | Topic-based PubSub with string keys | Direct typed channel per message type |
| Cross-process | Yes (pickle serialization) | No (threads share heap) |
| Sync mechanism | `should_grab_by_id()` polling | `BreakableBarrier` rendezvous |
| Channel creation | Must happen in main process (Windows) | Any thread can create channels |
| Shutdown | PubSub `close()` + queue drain | Channel drop unblocks all receivers |
