# freemocap-pipeline

The core real-time pipeline engine. A DAG of threads that processes multi-camera frames through detection, triangulation, and filtering.

## Topology

```
Distributor (1 thread)
  │
  │ BreakableBarrier (N_cameras + 1)
  │
  ├── CameraNode[0] (1 thread per camera)
  ├── CameraNode[1]
  └── CameraNode[2]
        │
        │ mpsc channels
        ▼
Aggregator (1 thread)
        │
        ▼
output_slot: Arc<Mutex<Option<AggregatorOutput>>>
```

Data flows strictly one direction. The barrier ensures all camera nodes receive the same frame number — desynchronization is impossible by construction.

## Key Design Decisions

### BreakableBarrier fan-out (inverted from skellycam)

skellycam uses `BreakableBarrier` for fan-in (N cameras → 1 gatherer). freemocap uses it for fan-out (1 distributor → N camera nodes). Same primitive, inverted direction.

### FrameSlots — direct Rust-to-Rust access

The distributor holds `FrameSlots` — clones of the same `Arc<Mutex<Option<T>>>` that the skellycam dispatcher writes to. Zero copies, zero Python. The distributor polls these slots each cycle and writes the `DistributorSlot` for camera nodes to read.

### Timestamp chain

Every stage stamps `performance_counter_nanoseconds()` (ns since T=0, skellycam's clock anchor):
- **Distributor:** slot_write_ns, barrier_release_ns
- **Camera node:** dequeue_ns, post_jpeg_decode_ns, post_detection_ns, pre_send_ns
- **Aggregator:** collection_start_ns, all_received_ns, post_triangulation_ns, post_filter_ns, output_published_ns

Plus skellycam's 5 timestamps carried through from `RawFrame`.

## Types

| Type | Role |
|------|------|
| `DistributorSlot` | Written by distributor, read by all camera nodes (under `RwLock` + barrier) |
| `PerCameraFrameData` | One camera's JPEG + skellycam timestamps |
| `CameraNodeOutput` | Detection result + camera-stage timestamps |
| `AggregatorOutput` | Final output: keypoints, frontend payload, full timestamp chain |
| `PipelineConfig` | Serde-deserializable config from Python JSON |
| `PipelineCommand` | UpdateConfig / Shutdown enum (sent to all nodes) |

## Config Hot-Reload

Config updates flow via `mpsc::Sender<PipelineCommand>` to each node. Nodes call `try_recv()` at loop top — zero latency. Charuco detector is recreated when board params change; filter params update in-place.

## Dependencies

- `skellycam` — `BreakableBarrier`, `FrameSlots`, `FrameLifecycleTimestamps`, performance clock
- `skellytracker` — `CharucoTracker`, `CharucoObservation`
- `opencv` — JPEG decode (`imgcodecs::imdecode`)
