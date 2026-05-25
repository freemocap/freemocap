# System Startup and Process Model

> Worked example of Step 1 (Understand) + Step 2 (Extract Invariants) + Step 4 (Design Rust) from the [re-architecture playbook](../rearchitecture-playbook/).

## The Problem

Boot a multi-camera capture server, manage the lifecycle of camera workers, and ensure clean shutdown. The server must respond to HTTP requests, stream frames via WebSocket, and release all hardware resources on exit.

### Invariants

- Single global kill switch must cause all cameras to stop
- Clean exit — all camera handles and subprocesses released
- Works on Windows (no `fork()`, no Unix signals for threads)
- Ctrl+C triggers clean shutdown
- Graceful shutdown via HTTP endpoint

## Python's Solution

### Architecture

```
entry_point() → multiprocessing.freeze_support() → asyncio.run(main())
  main():
    - Create global_kill_flag = multiprocessing.Value("b", False)
    - Create WorkerRegistry(global_kill_flag, WorkerMode.PROCESS)
    - Start heartbeat thread (perf_counter every 1s to shared Value("d"))
    - Start child monitor thread (polls workers, triggers shutdown if any die)
    - Install SIGTERM/SIGINT handlers
    - Build FastAPI app via create_fastapi_app(kill_flag, worker_registry)
    - Start uvicorn server
    - On shutdown: set kill flag → worker_registry.shutdown_all()
```

`WorkerRegistry.shutdown_all()` — 3-phase escalating shutdown:
1. Set kill flag, wait 3s
2. `terminate()` stragglers, wait 3s
3. `kill()` remaining, wait 2s
4. Raise if zombies remain

### Why This Architecture

Every element exists because Python uses `multiprocessing.Process`:

| Mechanism | Why Python Needs It |
|-----------|-------------------|
| `multiprocessing.Value("b")` for kill flag | Processes have separate address spaces |
| Heartbeat thread + shared `Value("d")` | Children must detect parent death (OS processes are independent) |
| Child monitor thread | Parent must explicitly poll children — process death is silent |
| 3-phase escalating shutdown | Processes may hang on exit (blocking I/O, deadlocks) |
| `atexit` safety net | Python process exit is cooperative — cleanup may not run |
| `freeze_support()` + staggered spawn | Windows `spawn` re-imports the module tree |
| `ensure_bytecode_compiled()` | Concurrent .pyc compilation races on Windows |

## Rust's Solution

### Architecture

```rust
run_server() in main.rs:
  1. Create Arc<AppState> with:
     - camera_manager: Mutex<CameraGroupManager>
     - shutdown_flag: Arc<AtomicBool>
     - active_group_id: Mutex<Option<String>>
  2. Build Axum Router via build_router(state)
  3. Bind TCP listener on 0.0.0.0:53117
  4. axum::serve with graceful_shutdown:
     - Waits for Ctrl+C OR shutdown_flag == true
  5. On exit: camera_manager.blocking_lock().close_all_groups()
```

### What Disappeared

Everything that existed to work around `multiprocessing.Process`:

- **No heartbeat thread** — threads share the process fate; no orphan detection needed
- **No child monitor** — `JoinHandle` collected in `CameraGroup`; panics caught at `join()`
- **No 3-phase escalation** — `Camera::shutdown()` sends command, joins thread
- **No `atexit` safety nets** — `Drop` impl on `CameraGroupManager` calls `close_all_groups()`
- **No `freeze_support()` or bytecode compilation** — Rust is AOT compiled
- **No staggered spawn** — `thread::spawn` just runs the closure

### What Stayed

- `shutdown_flag: Arc<AtomicBool>` — same semantics as Python's kill flag, but no `multiprocessing` import
- `GET /shutdown` endpoint sets the flag
- `tokio::signal::ctrl_c()` replaces SIGINT handler
- `with_graceful_shutdown()` replaces the `finally` block

## Key Differences

| Concern | Python | Rust |
|---------|--------|------|
| Concurrency | `multiprocessing.Process` | `std::thread::spawn` + `tokio` |
| Kill flag | `multiprocessing.Value("b")` | `Arc<AtomicBool>` |
| Worker tracking | `WorkerRegistry` with 3-phase escalation | `Vec<JoinHandle>` + `Drop` |
| Orphan detection | Heartbeat + child monitor threads | Not needed — threads share fate |
| Cleanup guarantee | `atexit` + `finally` | `Drop` impls (compiler-guaranteed) |
| Signal handling | `SIGTERM`/`SIGINT` handlers in parent | `tokio::signal::ctrl_c()` |
| Process model | Separate processes, separate address spaces | One process, shared address space |
