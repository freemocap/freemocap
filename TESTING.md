# Testing

## Pipeline E2E tests (posthoc + realtime mocap)

End-to-end tests for the `core/pipeline/{posthoc,realtime}` pipelines live in
`freemocap/tests/pipelines/`. They run the **real** pipelines against the shared
test recording (3 synchronized videos, 222 frames: a 7x5 charuco calibration
sequence followed by mocap movement) at `FREEMOCAP_TEST_DATA_PATH`
(`~/freemocap_data/recordings/freemocap_test_data`). If the data is absent the
tests skip.

```bash
uv run poe test-pipelines           # full suite (incl. slow full-skeleton realtime)
uv run poe test-pipelines-fast      # everything except the slow RTMPose case
```

There is also a longer realtime exercise against `freemocap_sample_data/` (the same
recording, not downsampled — ~1100 frames). It's capped by `--realtime-max-frames`
(default 250, `0` = the whole clip) so it terminates early by default:

```bash
# default 250-frame cap:
uv run pytest freemocap/tests/pipelines/test_realtime_pipeline.py -k sample_data
# run the entire clip:
uv run pytest freemocap/tests/pipelines/test_realtime_pipeline.py -k sample_data --realtime-max-frames=0
```

What they cover:
- **Posthoc calibration** — runs the calibration pipeline with the 7x5 board
  (`CharucoBoardDefinition.create_test_data_7x5()`) and verifies the written TOMLs
  and annotated videos. Produces the calibration that the other tests depend on.
- **Posthoc mocap** — runs the mocap pipeline (Blender export disabled) and checks
  `output_data/` has non-NaN 3D body data, for both `most_recent` and `specified`
  calibration sources.
- **Anthropometry / "human-shaped"** — measures limb-segment lengths (upper arm,
  forearm, thigh, shank) from the posthoc 3D output and asserts they are in
  anthropometric proportion (consistent implied standing height across segments),
  temporally rigid, and left/right symmetric. This is the real correctness bar —
  "not all NaN" is necessary but not sufficient.
- **Realtime** — a `MockCameraGroup` (subclass of skellycam's `CameraGroup`)
  creates the *real* shared memory and feeds it frames from the test videos; a
  single-threaded lockstep driver writes frame N, waits for the aggregator's
  output, and advances. Parametrized into a fast `charuco_only` case and a slow
  (`@pytest.mark.slow`) `full` RTMPose-skeleton case. The full case also asserts
  the raw realtime reconstruction is human-shaped **and** that its per-limb
  segment lengths match the trusted posthoc output (within ~25%). Camera capture
  is the only thing mocked — IPC, triangulation, filtering and fitting are real.

The "human-shaped" scoring lives in `freemocap/core/kinematics/segment_lengths.py`
(reusable as a runtime diagnostic): it divides each measured segment length by the
canonical `bone_length_ratios` to get a per-segment *implied height*; a genuinely
human skeleton implies one consistent height across all segments, so the spread
(CV) of implied heights is height-independent and is the core signal.

These tests run in-place in the recording folder (regenerating `output_data/`,
`annotated_videos/`, etc.), matching how the app runs.

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