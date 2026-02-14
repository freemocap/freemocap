# Testing

## Quick Start

```bash
# Run EVERYTHING (backend + frontend) — works on Windows, macOS, Linux:
uv run poe test-all
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

Every command below works identically on Windows, macOS, and Linux.

### All tests

```bash
uv run poe test-all        # Backend (pytest) + frontend (vitest)
```

### Backend only

```bash
uv run poe test            # All backend tests
```

### Frontend only

```bash
uv run poe test-ui         # All frontend tests (vitest)
```

### Targeted backend runs

```bash
uv run poe test-schema     # Schema contract tests (field names, defaults)
uv run poe test-settings   # SettingsManager unit tests (merge, patch, version)
uv run poe test-http       # HTTP endpoint integration tests
uv run poe test-ws         # WebSocket protocol tests
uv run poe test-sync       # All 4 sync test files together
```

### Watch mode (frontend)

```bash
cd freemocap-ui
npx vitest
```

### Nox (CI / multi-Python)

```bash
nox -s test          # Backend on Python 3.11 + 3.12
nox -s test_sync     # Just sync tests on 3.12
nox -s test_ui       # Frontend vitest
nox -s test_all      # Backend + frontend on 3.12
nox -s coverage      # Backend with coverage report
```

## Available poe tasks

Run `uv run poe --help` for the full list. Testing tasks:

| Task | What runs |
|---|---|
| `test` | All backend tests (`pytest freemocap/tests/`) |
| `test-all` | Backend + frontend |
| `test-ui` | Frontend vitest suite |
| `test-schema` | Schema contract: Pydantic ↔ TypeScript field names & defaults |
| `test-settings` | SettingsManager: merge, patch, version, async notify |
| `test-http` | HTTP endpoints: payload validation, settings sync |
| `test-ws` | WebSocket protocol: patch routing, relay push |
| `test-sync` | All 4 sync test files combined |

## What Each Test Layer Catches

| Layer | File | What breaks if this fails |
|---|---|---|
| **Schema contract** | `test_schema_contract.py` | Backend renamed a field but frontend still sends the old name. A default value changed on one side but not the other. |
| **SettingsManager** | `test_settings_manager.py` | `apply_patch` clobbers sibling config fields. Version doesn't bump so WebSocket never pushes. `_deep_merge` mutates its inputs. |
| **HTTP endpoints** | `test_http_config_endpoints.py` | Frontend thunk payload gets 422 (camelCase vs snake_case mismatch). Config update doesn't reach SettingsManager or pipelines. |
| **WebSocket protocol** | `test_websocket_settings_protocol.py` | `settings/patch` accepted but never synced to running pipelines. `settings/request` doesn't trigger a state push. Bad message type silently ignored. |
| **Settings slice** | `settings-slice.test.ts` | Stale WebSocket version overwrites newer data. Disconnect doesn't reset state. |
| **Calibration slice** | `calibration-slice.test.ts` | Partial config update nukes sibling fields. Thunk reducers leave wrong loading/error state. |
| **Mocap slice** | `mocap-slice.test.ts` | Detector/filter config merge drops fields. Default constants drifted from backend. |
| **Message guards** | `message-type-guards.test.ts` | `isSettingsStateMessage` lets malformed data through. Valid messages rejected so settings never update. |

## When to Run What

| You changed... | Run... |
|---|---|
| A Pydantic model field name or default | `uv run poe test-schema` |
| `SettingsManager` or `_deep_merge` | `uv run poe test-settings` |
| An HTTP endpoint or request/response model | `uv run poe test-http` |
| WebSocket message handling | `uv run poe test-ws` |
| A Redux slice, thunk, or type guard | `uv run poe test-ui` |
| Anything in the settings sync path | `uv run poe test-sync` |
| About to push a commit | `uv run poe test-all` |
