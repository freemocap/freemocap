# Step 4: Design Rust Architecture from the Invariants

You have the invariants (Step 2) and you know which Python patterns are Python-specific (Step 3). Now design the Rust architecture.

**Start from the invariants, not from the Python code.** Ask "what Rust primitive achieves this invariant?" — not "what's the Rust equivalent of this Python class?"

## Principles

### 1. Threads share the heap — use it

Every Python pattern that exists to move data across process boundaries (shared memory, DTOs, pickle, PubSub) disappears. In Rust:

- An `Arc<T>` IS shared memory — no SHM setup, no DTOs, no recreate
- An `mpsc::channel()` IS cross-thread communication — no queues, no pickle
- A `Mutex<T>` IS shared mutable state — no `multiprocessing.Value`
- `thread::spawn()` gives true parallelism — no GIL workarounds

### 2. The type system works at compile time — use it

Every Python pattern that exists to enforce correctness at runtime (`isinstance()`, `beartype`, type checks in PubSub handlers) disappears. In Rust:

- Channel type parameters enforce message types at compile time
- `enum` variants carry data — no "message type" field + casting
- `#[derive(Serialize, Deserialize)]` guarantees correct JSON shapes
- `#[repr(C)]` guarantees binary layout without manual offset calculation

### 3. Drop is deterministic — use it

Every Python pattern that exists to ensure cleanup (`atexit`, try/finally, context managers, escalating shutdown) is handled by `Drop`. In Rust:

- `Drop` on a `VideoRecorder` kills ffmpeg — no zombie processes
- `Drop` on a `CameraGroupManager` shuts down all groups — no leaked cameras
- Dropping a channel `Sender` unblocks all `Receiver`s — no explicit "close" needed
- Panic unwinding runs `Drop` impls — cleanup still happens

### 4. Expect the architecture to look different

This is the hardest principle to internalize. If your Rust architecture looks like the Python architecture translated to Rust syntax, you've missed the point. The skellycam Rust implementation is demonstrably different from the Python one:

| Concern | Python Solution | Rust Solution |
|---------|----------------|---------------|
| Multi-camera sync | `should_grab_by_id()` polling with `deepcopy` of shared counters | `BreakableBarrier` — all threads rendezvous |
| Image pipeline | BGR decode → rotate → resize → JPEG re-encode | MJPEG passthrough — no decode |
| Process model | `multiprocessing.Process` + PubSub | `std::thread::spawn` + typed channels |
| Camera API | OpenCV `VideoCapture` with grab/retrieve | `openpnp-capture` FFI with raw MJPEG |
| State sharing | 11 `multiprocessing.Value` booleans per camera | 1 `Arc<AtomicBool>` for paused |
| Config updates | PubSub broadcast + polling | Direct `mpsc::Sender<CameraCommand::Configure>` |

None of these are 1:1 mappings. All of them achieve the same invariants.

## The Design Loop

For each component:

1. **State the invariant** — what must this component achieve? (from Step 2)
2. **List the Python-specific mechanisms** you're explicitly NOT carrying over (from Step 3)
3. **Identify the Rust primitives** that naturally solve this invariant
4. **Sketch the architecture** — threads, channels, shared state, data flow
5. **Validate against invariants** — does this design satisfy every item on the checklist?
6. **Check for Rust anti-patterns** — are you fighting the borrow checker? Are you using `unsafe` where safe code would work? Are you building abstractions Rust already provides?

## Common Python→Rust Concept Translations

When you DO need to translate a concept (because it's universal, not Python-specific):

| Universal Concept | Python Implementation | Rust Implementation |
|-------------------|----------------------|---------------------|
| Shared mutable flag | `multiprocessing.Value("b")` | `Arc<AtomicBool>` |
| Shared configuration | `multiprocessing.Value` per field | `Arc<Mutex<Config>>` |
| Command dispatch | PubSub topic + polling | `mpsc::Sender<CommandEnum>` |
| One-shot notification | PubSub topic (1 message) | `oneshot::channel()` |
| Latest-value state | PubSub with `overwrite=True` | `tokio::sync::watch` |
| Streaming data (every frame) | Shared memory ring buffer | `mpsc::channel()` (unbounded) or `sync_channel(n)` |
| Thread-safe lazy init | Module-level global + `get_or_create_*` | `OnceLock<T>` or `Arc<T>` in Axum State |
| Graceful shutdown signal | `multiprocessing.Value("b")` + atexit | `Arc<AtomicBool>` + Drop impls |
| Structured binary data | numpy recarray with dtype | `#[repr(C)]` struct + `bytemuck` |

## Reference

The [skellycam example](../skellycam/) shows this design process applied to 9 components. Each document demonstrates: invariant → Python solution (with rationale) → Rust solution (with rationale) → what changed.
