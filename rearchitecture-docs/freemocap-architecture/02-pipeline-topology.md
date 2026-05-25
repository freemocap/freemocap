# Pipeline Topology

> Step 4 (Design Rust Architecture) — the overall DAG structure and data flow.

## The Problem

Orchestrate a real-time processing pipeline that takes multi-camera frames from skellycam, runs per-camera detection via skellytracker, triangulates charuco observations, applies filtering, and delivers synchronized (images + keypoints) frontend payloads.

### Invariants

- All camera nodes must process the same frame number — desynchronization by even one frame is a full failure
- Data flows strictly one direction (DAG, no round-trips)
- Pipeline runs at its own rate, independent of camera frame rate — drops frames when slower than cameras
- Frontend payload must pair the correct images with the correct processed data (same frame number)
- Real-time configurable without restart

## Python's Solution

```
CameraGroup (skellycam, separate processes)
    │  SharedMemory ring buffers (per camera)
    ▼
┌─────────────────────────────────────────────┐
│  RealtimePipeline (orchestrator, main proc)  │
│                                               │
│  CameraNode[0..N] (Process each):            │
│    - Reads frame from SHM ring buffer        │
│    - Charuco + skeleton detection            │
│    - Publishes CameraNodeOutput via PubSub    │
│                                               │
│  AggregatorNode (Process):                   │
│    - Subscribes to CameraNodeOutput topic     │
│    - Collects all cameras for frame N         │
│    - Triangulation + filtering               │
│    - Publishes AggregatorOutput via PubSub    │
│                                               │
│  Pipeline.get_latest_frontend_payload():     │
│    - Polls AggregatorOutput subscription      │
│    - Looks up frontend images by frame number │
│    - Returns combined packet                  │
└─────────────────────────────────────────────┘
```

### Python-Specific Mechanisms

| Mechanism | Why Python Needs It |
|-----------|-------------------|
| Shared memory ring buffers | Frames are multi-MB — can't copy through `multiprocessing.Queue` |
| PubSub for node communication | Processes can't call methods on each other |
| `result_ready_event` / `result_consumed_event` | Backpressure between processes — aggregator must signal consumer |
| `PipelineConfigUpdateMessage` via PubSub | Cross-process config propagation |
| Frame number lookup for frontend images | Image data and processed data are in separate SHM regions |

## Rust's Solution

```
SkellyCam (no changes)
  CameraGroup.latest_raw_frames: Arc<Mutex<Option<RawMultiFrame>>>
  CameraGroup.latest_frontend_payload: Arc<Mutex<Option<FrontendPayload>>>
        │
        │ poll both slots atomically
        ▼
┌──────────────────────────────────────────────────────┐
│  Pipeline (freemocap-rust)                            │
│                                                        │
│  Distributor (thread):                                 │
│    - Atomically snapshots both skellycam slots         │
│    - Guard: raw.frame_number == payload.frame_number   │
│    - Writes to shared slot + BreakableBarrier.wait()   │
│                      │                                 │
│        BreakableBarrier(N_cameras + 1)                 │
│                      │                                 │
│    ┌─────────────────┼─────────────────┐              │
│    ▼                 ▼                 ▼              │
│  CamNode[0]       CamNode[1]       CamNode[2]         │
│    │                 │                 │               │
│    │ JPEG decode     │                 │               │
│    │ charuco detect  │  (skellytracker CharucoTracker) │
│    │                 │                 │               │
│    └─────────────────┼─────────────────┘              │
│                      ▼                                 │
│  Aggregator (thread):                                  │
│    - Collects CameraNodeOutputs for frame N             │
│    - Verifies all same frame_number                     │
│    - Triangulation + velocity gate + one-euro filter    │
│    - Bundles frontend_payload + keypoints               │
│    - Writes AggregatorOutput to shared slot             │
│                      │                                 │
└──────────────────────┼─────────────────────────────────┘
                       ▼
  latest_output: Arc<Mutex<Option<AggregatorOutput>>>
  (Python WebSocket relay polls this)
```

Data flows strictly one direction: Distributor → CameraNodes → Aggregator → output slot.

### What Disappeared

| Python Artifact | Why Eliminated |
|----------------|----------------|
| Shared memory ring buffers for pipeline data | Threads share heap — channels + `Arc` slots |
| PubSub system (7+ topics, per-subscriber queues) | Direct typed channels between known threads |
| `result_ready_event` / `result_consumed_event` | `Arc<Mutex<Option<T>>>` — consumer polls, producer swaps |
| `PipelineConfigUpdateMessage` broadcast | Direct `mpsc::Sender<PipelineCommand>` to each node |
| Frame number lookup for frontend images | Distributor snapshots both slots atomically — images ride through pipeline |
| `ProcessFrameNumberMessage` request/response | Distributor pushes frames; barrier synchronizes consumption |

### What Stayed

- Multi-camera frame synchronization (all nodes process same frame_number)
- Strict one-way DAG topology
- Pipeline runs at its own rate, dropping intermediate frames
- Real-time config updates via channel commands
- `BreakableBarrier` — reused from skellycam, same primitive, inverted direction
