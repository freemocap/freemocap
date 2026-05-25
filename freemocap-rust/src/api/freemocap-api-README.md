# freemocap-api

Axum HTTP API for pipeline management. The binary server exposes these endpoints on port 53118.

## Routes

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/freemocap/pipeline/create` | Create a real-time pipeline attached to a camera group |
| `GET` | `/freemocap/pipeline/list` | List all real-time pipeline IDs |
| `DELETE` | `/freemocap/pipeline/{pipeline_id}` | Shut down and remove a pipeline |
| `POST` | `/freemocap/pipeline/{pipeline_id}/config` | Update pipeline configuration |
| `GET` | `/health` | Liveness check |

## Request/Response Shapes

### POST /freemocap/pipeline/create

Request:
```json
{
  "group_id": "abc123",
  "config_json": "{...}",
  "camera_ids": ["cam_1", "cam_2"]
}
```

Response (201):
```json
{
  "pipeline_id": "d4e5f6"
}
```

### GET /freemocap/pipeline/list

Response:
```json
{
  "pipeline_ids": ["d4e5f6", "a1b2c3"],
  "count": 2
}
```

### DELETE /freemocap/pipeline/{pipeline_id}

Response: 204 No Content, or 404 with `{"detail": "..."}`

### POST /freemocap/pipeline/{pipeline_id}/config

Request body: JSON object matching `PipelineConfig` schema.

Response: 200 OK, or 404 with `{"detail": "..."}`

## Error Format

All errors follow the Python FastAPI convention:
```json
{"detail": "<error message>"}
```

## AppState

```rust
pub struct AppState {
    pub camera_manager: Arc<tokio::sync::Mutex<CameraGroupManager>>,
    pub pipeline_manager: Arc<tokio::sync::Mutex<PipelineManager>>,
    pub shutdown_flag: Arc<AtomicBool>,
}
```

Both managers wrapped in `tokio::sync::Mutex` — locks are held briefly (never across I/O).

## Router Setup

```rust
let state = Arc::new(AppState::new());
let router = build_router(state);
// → CorsLayer::permissive()
// → All pipeline routes
// → /health endpoint
```

## Future Endpoints

- `WS /freemocap/pipeline/{id}/stream` — WebSocket for frontend payload delivery
- `GET /freemocap/pipeline/{id}/status` — pipeline health, frame rate, timing stats
- `POST /freemocap/recording/start` — recording orchestration across pipeline + camera group
