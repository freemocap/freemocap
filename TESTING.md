# Testing

## Quick Start

```bash
# Backend (from repo root):
uv run poe test-all

# Frontend (from freemocap-ui/):
cd freemocap-ui
npm test
```

## Setup (one time)

```bash
# Backend (from repo root):
uv sync --group dev

# Frontend:
cd freemocap-ui
npm install
```

## Running Tests

### Backend (from repo root)

```bash
uv run poe test-all        # All backend tests
uv run poe test-schema     # Schema contract tests (field names, defaults)
uv run poe test-settings   # SettingsManager unit tests (merge, patch, version)
uv run poe test-http       # HTTP endpoint integration tests
uv run poe test-ws         # WebSocket protocol tests
uv run poe test-e2e        # End-to-end integration tests (HTTP + WebSocket round-trip)
uv run poe test-sync       # All sync test files together (unit + E2E)
```

### Frontend (from freemocap-ui/)

```bash
cd freemocap-ui
npm test                   # Run once
npm run test:watch         # Watch mode (re-runs on save)
```

### Nox (CI / multi-Python)

```bash
nox -s test          # Backend on Python 3.11 + 3.12
nox -s test_sync     # Just sync tests on 3.12
nox -s test_ui       # Frontend (requires npm on PATH)
nox -s test_all      # Backend + frontend on 3.12
nox -s coverage      # Backend with coverage report
```

## Available poe tasks

Run `uv run poe --help` for the full list. Testing tasks:

| Task | What runs |
|---|---|
| `test-all` | All backend tests |
| `test-schema` | Schema contract: Pydantic ↔ TypeScript field names & defaults |
| `test-settings` | SettingsManager: merge, patch, version, async notify |
| `test-http` | HTTP endpoints: payload validation, settings sync |
| `test-ws` | WebSocket protocol: patch routing, relay push |
| `test-e2e` | End-to-end: HTTP → SettingsManager → WebSocket push round-trip |
| `test-sync` | All sync test files combined (unit + E2E) |

## What Each Test Layer Catches

| Layer | File | What breaks if this fails |
|---|---|---|
| **Schema contract** | `test_schema_contract.py` | Backend renamed a field but frontend still sends the old name. A default value changed on one side but not the other. |
| **SettingsManager** | `test_settings_manager.py` | `apply_patch` clobbers sibling config fields. Version doesn't bump so WebSocket never pushes. `_deep_merge` mutates its inputs. |
| **HTTP endpoints** | `test_http_config_endpoints.py` | Frontend thunk payload gets 422 (camelCase vs snake_case mismatch). Config update doesn't reach SettingsManager or pipelines. |
| **WebSocket protocol** | `test_websocket_settings_protocol.py` | `settings/patch` accepted but never synced to running pipelines. `settings/request` doesn't trigger a state push. Bad message type silently ignored. |
| **E2E HTTP** | `test_e2e_http_settings_sync.py` | Route prefix mounting wrong (double prefix, missing prefix). Cross-router updates clobber each other through shared SettingsManager. Frontend URL paths don't resolve. |
| **E2E WebSocket** | `test_e2e_websocket_settings_sync.py` | HTTP POST doesn't trigger WebSocket state push. WebSocket patch round-trip loses data. Version not monotonic across mixed HTTP/WS updates. |
| **Settings slice** | `settings-slice.test.ts` | Stale WebSocket version overwrites newer data. Disconnect doesn't reset state. |
| **Calibration slice** | `calibration-slice.test.ts` | Partial config update nukes sibling fields. Thunk reducers leave wrong loading/error state. |
| **Mocap slice** | `mocap-slice.test.ts` | Detector/filter config merge drops fields. Default constants drifted from backend. |
| **Message guards** | `message-type-guards.test.ts` | `isSettingsStateMessage` lets malformed data through. Valid messages rejected so settings never update. |

## When to Run What

| You changed... | Run... |
|---|---|
| A Pydantic model field name or default | `uv run poe test-schema` |
| `SettingsManager` or `_deep_merge` | `uv run poe test-settings` |
| An HTTP endpoint or request/response model | `uv run poe test-http` then `uv run poe test-e2e` |
| WebSocket message handling | `uv run poe test-ws` then `uv run poe test-e2e` |
| Route mounting, prefixes, or middleware | `uv run poe test-e2e` |
| A Redux slice, thunk, or type guard | `cd freemocap-ui && npm test` |
| Anything in the settings sync path | `uv run poe test-sync` |
| About to push a commit | `uv run poe test-all` then `cd freemocap-ui && npm test` |