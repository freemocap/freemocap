# freemocap-pipeline-manager

Manages the lifecycle of real-time and posthoc pipelines. Mirrors `skellycam::CameraGroupManager` in structure and CRUD semantics.

## Ontology

```
PipelineManager
  realtime: HashMap<PipelineID, RealtimePipeline>
  posthoc:  HashMap<PipelineID, PosthocPipeline>   ← deferred

  PipelineID = 6-char UUID prefix (same strategy as CameraGroup ID)
```

- **CameraGroup** exists independently
- **RealtimePipeline** optionally attaches to a CameraGroup via `FrameSlots`
- A CameraGroup can have zero, one, or (future) multiple pipelines attached

## CRUD Operations

| Operation | Method | Returns |
|-----------|--------|---------|
| Create | `create_realtime_pipeline(frame_slots, config, camera_ids)` | `PipelineID` |
| Read | `get_realtime_pipeline(id)` | `Option<&RealtimePipeline>` |
| Update config | `update_realtime_pipeline_config(id, config)` | `Option<()>` |
| Delete | `remove_realtime_pipeline(id)` | `bool` |
| List | `list_realtime_pipelines()` | `Vec<PipelineID>` |
| Count | `realtime_pipeline_count()` | `usize` |
| Shutdown | `shutdown_all()` | drains both maps |

## Posthoc Pipeline

`PosthocPipeline` is a placeholder type. The `posthoc` map exists with zero entries. `create_posthoc_pipeline()` is `unimplemented!()`. This is future-proofing — the manager is designed to hold both types from day one.

## Drop Behavior

`PipelineManager::drop()` calls `shutdown_all()`, which:
1. Sets `shutdown_flag` on each pipeline
2. Joins all thread handles
3. Clears both maps

Same pattern as `CameraGroupManager::drop()` → `close_all_groups()`.

## Thread Safety

- Binary path: wrapped in `Arc<tokio::sync::Mutex<PipelineManager>>` in `AppState`
- PyO3 path: `PyPipeline` manages threads directly (uses `FrameSlots`, `BreakableBarrier`, channels, and `Aggregator`) without going through `RealtimePipeline` or `PipelineManager`
- `RealtimePipeline` is `Send + Sync` (all fields are `Arc`, `Mutex`, `AtomicBool`, or owned channels)
