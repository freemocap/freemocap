# Multi-Socket WebSocket Refactor

## Overview

Splitting the single WebSocket connection into three specialized sockets for better separation of concerns, independent backpressure handling, and cleaner architecture.

---

## ✅ Completed

### Backend (`freemocap/api/websocket/`)

| File | Description | Status |
|------|-------------|--------|
| `message_types.py` | `StrEnum` for FrameMessageType, LogsMessageType, StateMessageType | ✅ Complete |
| `base_handler.py` | Pydantic `BaseModel` abstract class with connection lifecycle, message routing, heartbeat | ✅ Complete |
| `frame_handler.py` | Frame streaming with backpressure, overlay JSON, tracked points | ✅ Complete |
| `logs_handler.py` | Log record streaming from queue | ✅ Complete |
| `state_handler.py` | Settings sync, framerate updates, patch handling | ✅ Complete |
| `routes.py` | FastAPI router with `/ws/frame`, `/ws/logs`, `/ws/state` endpoints | ✅ Complete |
| `__init__.py` | Module exports | ✅ Complete |
| `app.py` | Router registration updated | ✅ Complete |

### Frontend (`freemocap-ui/src/services/server/`)

| File | Description | Status |
|------|-------------|--------|
| `message-types.ts` | TypeScript enums for message types, ConnectionStatus | ✅ Complete |
| `BaseWebSocketConnection.ts` | Reusable WebSocket class with reconnection, heartbeat, message routing | ✅ Complete |
| `ServerContextProvider.tsx` | Consolidated provider managing 3 sockets internally | ✅ Complete |
| `index.ts` | Module exports | ✅ Complete |

### Integration Updates

| File | Description | Status |
|------|-------------|--------|
| `freemocap-ui/src/hooks/server-urls.ts` | Added new WebSocket URL methods with backward compat | ✅ Complete |
| `freemococap/tests/conftest.py` | Updated test fixtures for `/ws/state` | ✅ Complete |
| `freemocap/tests/test_e2e_websocket_settings_sync.py` | Updated all E2E tests for `/ws/state` | ✅ Complete |
| `freemocap/api/http/app/debug.py` | Updated debug page to use `/ws/state` | ✅ Complete |

---

## 🔜 Remaining

### Backend

1. **Test the handlers** - Run pytest to verify the new handlers work correctly
   ```bash
   cd freemocap && pytest freemocap/tests/test_e2e_websocket_settings_sync.py -v
   ```

2. **Decision: Keep or deprecate old `websocket_server.py`**
   - OLD: `/websocket/connect` (single socket, 300+ lines)
   - NEW: `/ws/frame`, `/ws/logs`, `/ws/state` (3 sockets, ~100 lines each)
   - Recommendation: Keep old as fallback during transition, remove in future release

### Frontend

3. **Test the new UI components** - Verify ServerContextProvider works with real backend
4. **Run type checking** - `cd freemocap-ui && npm run typecheck`
5. **Test backpressure** - Verify frame acknowledgment under load

### Integration

6. **Full E2E smoke test** - Start server, connect UI, verify all 3 sockets
7. **Performance test** - High frame rate, many cameras, verify no blocking

---

## Architecture

```
Backend                          Frontend
┌─────────────────┐              ┌─────────────────┐
│ /ws/frame       │──────────────│ Frame Socket    │
│ - binary frames │              │ - CanvasManager │
│ - overlays      │              │ - OverlayMgr    │
│ - tracked pts   │              │ - Subscribers   │
└─────────────────┘              └─────────────────┘

┌─────────────────┐              ┌─────────────────┐
│ /ws/logs        │──────────────│ Logs Socket     │
│ - log records   │              │ - Redux dispatch│
└─────────────────┘              └─────────────────┘

┌─────────────────┐              ┌─────────────────┐
│ /ws/state       │──────────────│ State Socket    │
│ - settings      │              │ - Redux dispatch│
│ - framerate     │              │ - Patch sending │
└─────────────────┘              └─────────────────┘
                                 ┌─────────────────┐
                                 │ ServerContext   │
                                 │ - Unified API   │
                                 │ - Health status │
                                 └─────────────────┘
```

---

## Key Benefits

- **Independent backpressure** - Frame throttling doesn't block logs/state
- **Separate connection states** - Granular status display
- **Smaller modules** - ~100-200 lines each vs 361-line god object
- **Type-safe routing** - Enums prevent string typos
- **Easier testing** - Test each socket independently

---

## Migration Notes

### Endpoint Changes

| Old | New |
|-----|-----|
| `/websocket/connect` | `/ws/frame`, `/ws/logs`, `/ws/state` |

### Frontend URL Methods

| Old (deprecated) | New |
|------------------|-----|
| `getWebSocketUrl()` | `getFrameSocketUrl()` |
| | `getLogsSocketUrl()` |
| | `getStateSocketUrl()` |
| `endpoints.websocket` | `endpoints.websocketFrame` |
| | `endpoints.websocketLogs` |
| | `endpoints.websocketState` |

### Message Types (unchanged)

- `frameAcknowledgment` → Frame socket
- `charuco_overlay`, `mediapipe_overlay` → Frame socket
- `tracked_points3d`, `rigid_body_poses` → Frame socket
- `log_record` → Logs socket
- `settings/state`, `settings/patch`, `settings/request` → State socket
- `framerate_update` → State socket
