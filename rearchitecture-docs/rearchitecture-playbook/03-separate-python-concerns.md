# Step 3: Separate Python-Specific from Universal

After analyzing the Python implementation and extracting the invariants, the next step is to identify which parts of the Python architecture exist ONLY because of Python's constraints — and which parts are inherent to the problem.

This prevents accidentally carrying Python baggage into the Rust design. If you treat the Python architecture as a template, you'll end up building Python-shaped Rust code that fights the language.

## The Tagging Process

Go through every architectural decision in your Python analysis and tag it:

### Python-Specific

These exist because of Python's particular constraints and do NOT apply to Rust:

| Python Pattern | Why It Exists in Python | Does It Apply in Rust? |
|---------------|------------------------|------------------------|
| `multiprocessing.Process` | CPython threads serialize on the GIL for CPU-bound work | **No** — `std::thread::spawn` runs truly in parallel |
| `multiprocessing.Value("b")` for shared flags | Processes have separate address spaces — can't share heap objects | **No** — `Arc<AtomicBool>` shares memory across threads |
| `multiprocessing.Queue` for cross-process messages | Processes must serialize everything through pipes | **No** — typed channels (`mpsc`, `broadcast`, `watch`) pass owned data on the heap |
| Pickle serialization of all messages | `multiprocessing.Queue` requires pickling | **No** — channels pass typed data, no serialization |
| Shared memory ring buffers for frames | Frames are multi-MB — can't copy through pipes between processes | **No** — `Arc<Vec<u8>>` shares ownership across threads, or just send through channels |
| DTO/recreate pattern for SHM | Each process must independently map shared memory by name | **No** — threads share address space; no "recreating" needed |
| PubSub for cross-process events | Processes can't call methods on each other | **No** — direct channel send to typed receiver |
| Polling PubSub subscriptions in hot loop | No blocking receive across processes with timeout | **No** — `recv()` blocks until data arrives |
| `freeze_support()` + `if __name__ == "__main__"` guard | Windows `spawn` re-imports the module tree | **No** — Rust threads don't re-import |
| Staggered process spawn (250ms delays) | Prevents file-locking races during Windows `spawn` | **No** — no module re-import |
| Heartbeat thread + child monitor | Processes are independent; parent death doesn't kill children | **No** — threads share the process fate |
| `atexit` safety nets | Python process exit is cooperative; cleanup may not run | **No** — `Drop` impls are compiler-guaranteed |
| 3-phase escalating shutdown | Processes may hang on exit (blocking I/O, deadlocks) | **No** — channel drop unblocks receivers; `JoinHandle::join()` waits for thread exit |
| `beartype` runtime type checking | Python type hints are not enforced at runtime | **No** — Rust's type system checks at compile time |
| `ensure_bytecode_compiled()` in lifespan | Windows `spawn` causes concurrent .pyc compilation races | **No** — Rust is AOT compiled |
| `asyncio.Lock` for WebSocket writes | `websockets` library doesn't support concurrent writes | **No** — Axum's `split()` gives independent send/receive halves |
| `numpy` recarrays for structured data | Python's only performant multi-dimensional array option | **No** — Rust structs with `#[repr(C)]` give type-safe, zero-cost structured data |
| `cv2.VideoCapture` with grab/retrieve | OpenCV provides camera access with BGR decode | May or may not apply — depends on whether you use OpenCV or a native API |

### Universal

These are inherent to the problem domain and apply regardless of language:

- Multi-camera frame synchronization (all cameras at the same frame number)
- Per-frame capture timestamps for performance analysis
- Recording video frames to files with consistent naming
- WebSocket streaming of frames to a frontend
- Config changes propagating to running cameras
- Graceful shutdown releasing hardware resources
- Camera detection and capability enumeration
- Pause/resume without dropping device connections

## The Key Insight

Most of the Python architecture's complexity comes from one root cause: **processes have separate address spaces.** Everything — shared memory, PubSub, pickle serialization, DTOs, staggered spawn, heartbeat monitoring — traces back to the fact that Python must use `multiprocessing.Process` to achieve parallelism.

In Rust, threads share the heap. This single difference eliminates roughly 60-70% of the Python architecture's complexity. The remaining 30-40% is the actual problem: camera capture, frame synchronization, recording, and streaming.

## The Danger of Direct Porting

If you port the Python architecture directly to Rust, you will:

- Build shared memory abstractions that threads don't need
- Implement PubSub systems that typed channels replace
- Create DTO/recreate patterns that `Arc` makes unnecessary
- Write polling loops that blocking `recv()` eliminates
- Build shutdown escalation that `Drop` handles automatically

The result: more code, more bugs, and performance that's constrained by a Python-shaped design.

Instead: **understand the invariants, discard the Python-specific mechanisms, and design fresh.**
