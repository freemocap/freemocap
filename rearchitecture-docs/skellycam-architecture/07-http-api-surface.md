# HTTP API Surface

> Worked example of Step 2 (Extract Invariants) — the API surface is the most critical set of invariants. See the [re-architecture playbook](../rearchitecture-playbook/).

## The Problem

Provide an HTTP API that the Electron/React frontend depends on. All endpoint paths, HTTP methods, request/response JSON shapes, and error formats must be preserved.

### Invariants

- Endpoint paths match exactly (frontend hardcodes URLs)
- Request/response JSON shapes match exactly
- Error format: `{"detail": "<message>"}` with status 500
- CORS permissive (all origins, methods, headers)
- Server on port 53117
- Swagger/OpenAPI docs available

## Python's API Surface

### Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness check |
| `GET` | `/shutdown` | Graceful shutdown |
| `POST` | `/skellycam/camera/detect` | Enumerate cameras |
| `GET` | `/skellycam/camera/microphone/detect` | Enumerate microphones |
| `POST` | `/skellycam/camera/group/apply` | Create/update camera group |
| `DELETE` | `/skellycam/camera/group/close/all` | Close all groups |
| `GET` | `/skellycam/camera/group/all/pause_unpause` | Toggle pause |
| `POST` | `/skellycam/camera/group/all/record/start` | Start recording |
| `GET` | `/skellycam/camera/group/all/record/stop` | Stop recording, return stats |
| `WS` | `/skellycam/websocket/connect` | WebSocket upgrade |
| `GET` | `/skellycam/playback/*` | Playback (5 endpoints) |

### Camera Config (20+ fields in Python)

```json
{
  "camera_id": "...", "camera_index": 0, "backend": 0,
  "resolution": {"width": 1280, "height": 720}, "framerate": 30.0,
  "exposure": -7, "brightness": 128, "contrast": 128,
  "saturation": 128, "hue": 0, "gamma": 100, "gain": 0,
  "white_balance_temperature": 4000, "sharpness": 128,
  "backlight_compensation": 0, "focus": 0, "zoom": 0,
  "pan": 0, "tilt": 0, "iris": 0, "rotation": -1,
  "video_file_extension": "mp4", "writer_fourcc": "XVID"
}
```

## Rust's Implementation

### Route Registration

```rust
Router::new()
    .merge(camera_routes())      // /skellycam/camera/...
    .merge(websocket_route())    // /skellycam/websocket/connect
    .route("/api-docs/openapi.json", get(openapi_json))
    .route("/docs", get(swagger_ui))
    .route("/test", get(serve_test_page))
    .layer(log_request_middleware)
    .layer(CorsLayer::permissive())
    .with_state(state)
```

### Endpoints Implemented

| Method | Path | Status |
|--------|------|--------|
| `GET` | `/health` | Returns `"OK"` |
| `GET` | `/shutdown` | Sets `shutdown_flag` |
| `POST` | `/skellycam/camera/detect` | Enumerates via `openpnp-capture` |
| `POST` | `/skellycam/camera/group/apply` | `create_or_update_group()` |
| `DELETE` | `/skellycam/camera/group/close/all` | `close_all_groups()` |
| `GET` | `/skellycam/camera/group/all/pause_unpause` | Toggle pause |
| `POST` | `/skellycam/camera/group/all/record/start` | `start_recording()` |
| `GET` | `/skellycam/camera/group/all/record/stop` | `stop_recording()` |
| `WS` | `/skellycam/websocket/connect` | Binary frames + framerate JSON + log relay |

### Endpoints Not Implemented

| Path | Reason |
|------|--------|
| `GET /skellycam/camera/microphone/detect` | Audio recording deferred |
| `GET /skellycam/playback/*` | Playback endpoints deferred |
| `GET /favicon.ico` | Not needed |

### Camera Config (8 fields in Rust)

```rust
pub struct CameraConfig {
    pub camera_id: String,
    pub camera_index: u32,
    pub width: u32,
    pub height: u32,
    pub exposure: i32,
    pub exposure_mode: String,  // "MANUAL", "AUTO", "RECOMMEND"
    pub framerate: f64,
    pub rotation: i32,
}
```

Only 8 fields vs Python's 20+. `openpnp-capture` exposes DirectShow properties generically — only exposure is directly managed. Other UVC properties (brightness, contrast, etc.) would need custom property ID mapping through the DirectShow IAMCameraControl/IAMVideoProcAmp interfaces.

### Error Handling

```rust
enum AppError {
    Internal(anyhow::Error),
}

impl IntoResponse for AppError {
    fn into_response(self) -> Response {
        (StatusCode::INTERNAL_SERVER_ERROR,
         Json(json!({"detail": self.0.to_string()})))
            .into_response()
    }
}
```

Matches Python's `HTTPException(status_code=500, detail=str(e))` pattern.

### OpenAPI

Uses `utoipa` for schema generation. Custom Swagger UI HTML page at `/docs`. Endpoint handlers and request/response types annotated with `#[derive(OpenApi)]`.

## Key Differences

| Concern | Python | Rust |
|---------|--------|------|
| Framework | FastAPI | Axum |
| OpenAPI | Auto-generated from Pydantic models + route decorators | `utoipa` derive macros on structs + handler paths |
| Camera config size | 20+ fields (all UVC controls) | 8 fields (exposure + format only) |
| Playback | 5 endpoints serving static files | Not implemented (deferred) |
| Mic detection | `GET /skellycam/camera/microphone/detect` | Not implemented (deferred) |
| API prefix | `/skellycam` | `/skellycam` (preserved) |
| CORS | `CORSMiddleware` with `allow_origins=["*"]` | `CorsLayer::permissive()` |
| Error format | `{"detail": "<message>"}`, 500 | Identical |
