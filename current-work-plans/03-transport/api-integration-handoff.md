# Integrated API handoff

Status: accepted runtime/API baseline, published to the canonical `sfn26` branches.
This report supplements the [route migration inventory](api-route-migration.md)
and [recording contract](../../RECORDING_CONTRACT.md). W6 and other consumers can
target the accepted revisions below. Worktree archival is separate housekeeping.

## Revisions and ownership

Canonical checkouts are `repos/freemocap`, `repos/skellycam`, and
`repos/skellyforge` under the workspace. Core uses their normal editable imports.
The starting revisions were Core `72235c4d`, Cam `1df7fcb0`, Forge `73b1ac7`,
and Tracker `713a175`. Cleanup sources were Core `d613f549`, Cam `f1aefa95`,
and Forge `20cd7a6f`.

- Core runtime integration: `90cd474e94eb320be22cadd2b65472108725dd54`, published.
- Cam integration: `e9f70c200810d7aa68b24f7e71ad2294cf87ce93`, published.
- Forge integration: `a7648e115f9a83ee80056137a438f72cadc579fe`, published.

These checkouts were clean at runtime publication. Subsequent handoff-only commits
may advance Core HEAD without changing the tested runtime baseline.

Graph-only posthoc processing remains canonical. Export settings migration does
not restore the retired runner. Tracker still owns detector presets, hand crops,
keypoint assembly and mappings; Core retains hybrid and TensorRT settings through
those interfaces. Forge topology and the shared live/playback rendering path are
preserved. No prerequisite metadata handshake or state-dependent decoding is added.

## Authoritative contracts

Paths below are relative to the owning repository.

| Contract | Source |
| --- | --- |
| Registered capability routers | Core `freemocap/api/routers.py` and `freemocap/app/app.py` |
| Ordered HTTP categories | Core `freemocap/api/openapi_tags.py` |
| Recording identity and resources | Core `freemocap/api/http/recordings/` and `freemocap/core/recording/recording_location.py` |
| Export request variants and results | Core `freemocap/core/recording/exports/recording_export_request.py`, `requests.py`, `catalog.py` |
| Task observation and cancellation | Core `freemocap/api/http/posthoc/tasks_router.py`, `freemocap/api/task_interface.py`, `freemocap/core/pipeline/posthoc/task_snapshot.py` |
| Provider availability and loaded sessions | Core `freemocap/api/http/onnx/onnx_router.py` |
| WebSocket connection and inbound validation | Core `freemocap/api/websocket/websocket_connect.py`, `websocket_server.py`, `client_messages.py` |
| Frontend decoding and reconciliation | Core `freemocap-ui/src/services/server/transport/` |
| NumPy format and provenance migration | Forge `skellyforge/core/data_tensors/NUMPY_FORMAT.md`, `numpy_manifest.py`, `numpy_io.py` |
| Standalone camera controls | Cam `skellycam/api/http/cameras/camera_router.py` |

`GET /openapi.json` describes the running server's public HTTP surface. The
integration's generated `openapi.json` and `registered-routes.json` are retained
in Core `.test-artifacts/w3-integration/`; the latter includes hidden compatibility
routes and the WebSocket route. OpenAPI alone does not specify bidirectional WS.
At this checkpoint there are 59 public HTTP operations and 105 registered routes.
The inventory handles the installed FastAPI's effective included-router contexts,
including its separate Starlette WebSocket route representation.

## Client semantics and migration

- Recording identity is the folder name in `/freemocap/recordings/{recording_id}`.
  Optional `recording_parent_directory` selects another parent; omission uses the
  established default. Preserve it in resource URLs and cache identity. Capture
  UUID, task ID, retained run ID and content revision remain distinct.
- `GET .../export-options` describes available selections; `GET .../exports`
  inventories persisted artifacts; `POST .../exports` accepts typed `channels`,
  `tall_csv`, or `blender` work and returns a task reference with HTTP 202.
  Published artifact discovery is independent of retained in-memory task state.
- Read task state with `GET /freemocap/tasks` or `GET /freemocap/tasks/{task_id}`;
  cancel with `POST /freemocap/tasks/{task_id}/cancel`. Retained HTTP snapshots
  and WebSocket task updates share the registry, including server identity and
  revision ordering. A task's stored recording identity governs subsequent work.
- Playback remains HTTP-based with client-owned play/pause/seek, video range
  delivery and revision-bound recording reads. Shared read leases and recording
  ownership conflicts remain enforced; clients must handle busy/stale responses.
- Canonical command migrations include `POST /shutdown`, camera recording stop
  via POST, and camera pause via PUT with explicit `{paused: boolean}`. See the
  route inventory for capture, import, synchronization and realtime mappings.
- Preserve both `GET /freemocap/onnx/execution_providers` and
  `GET /freemocap/onnx/session_providers`; their advertised-vs-loaded meanings differ.
- `/websocket/connect` retains self-describing outgoing messages and validated
  inbound acknowledgments/display sizes and ping handling. Preserve connection
  isolation, content reconciliation, decoder caches and worker-buffer ownership.
  Clients must support the full HTTP control surface as well as WS interactions.
- `ScientificExportOptions/Request/Result` become `ExportOptions/Request/Result`;
  channels use `data_channels`; provenance uses `DataProvenance` and
  `data_provenance`. Historical settings are accepted through explicit migration.
  NumPy writers emit format v2; readers retain strict v1 compatibility. Historical
  spellings remain only where needed for compatibility and provenance/history.
- Hidden legacy export routes still exist for compatibility; clients should use
  the canonical recording endpoints, not discover a new scientific category.

## Validation and readiness

| Validation | Result |
| --- | --- |
| Standalone Cam | 378 passed; physical opt-in subsequently exercised separately: 1 passed |
| Standalone Forge | 918 passed; 1 structural skip: no adjacent rigid-fit pairs in the shipped model |
| Full Core/reference/Blender baseline | 1395 passed, 15 failed, 115 subtests passed; original report retained |
| Focused closure of all 15 failures | Passing timing checks (6), CPU fixture/oracle checks (24 plus 2 subtests), model/reference/trajectory checks (9), provider-switch/replay checks (5) |
| Fresh calibration and posthoc producer | 1 passed against private output, including numerical and annotated-video checks |
| Fresh Blender consumers | Both segment and constraint exports passed, with generated scenes reopened and checked |
| Browser suite | 92 passed |
| TypeScript | 75 checks across 23 bundles passed, including the 222-frame recording; compilation passed |
| Four physical cameras, Python and Rust | Both capture baselines passed at approximately 30 FPS without missing or duplicate captured frames |
| Physical tracking and recording, both backends | Raw recording audits passed; 21 finite human channel blocks per backend |
| Production UI, both physical backends | Camera configuration, decoding, overlays and 3D rendering exercised; no JavaScript errors |
| Final checks | Critical Python lint and diff checks passed; eight test-server cleanup reports have exit 0 and no errors |

The full suite was not rerun after its 15 failures were resolved. The coordinator
requested focused closure, fresh producer/Blender checks and physical/UI acceptance
instead. Do not describe this as a new all-green full-suite run. The original
`w3-core-full.xml` and `.log` are preserved in
`.test-artifacts/w3-integration/reports/`, alongside the focused reports.
Core `.test-artifacts/w3-integration/full-core-failures.json` records each original
failure, diagnosis, resolution and focused passing evidence.

Three failures exposed a recording-model compatibility defect: loading an old
model added absent `presentation: null`, changing its strict fit fingerprint.
Serialization now omits absent presentation while retaining declared definitions;
regression tests cover both. Original prepared recordings were not regenerated,
and fit validation was not weakened. Three timing fixtures lacked capture metadata;
seven reconstruction/batch/trajectory assertions were stale against current
independent-component reconstruction and complete tensor products. Two GPU cases
had stale assumptions about bounded tracking fallback and cold startup duration.
No geometry algorithm changed to satisfy those tests.

The hardware harness also constructed a default board recipe before replacing its
board with a calibration's different size. It now constructs the configuration
once from that board, preserving Tracker ownership and the API's consistency check.
The first rejected harness runs and their successful cleanup reports are retained.

Limitations and deferred performance work:

- Cold TensorRT compilation exceeded the old 120-second test startup allowance.
  The harness now distinguishes a bounded 600-second first-frame allowance from
  unchanged 120-second frame waits. The focused rerun used populated native caches;
  this does not fix or establish absence of live compilation pauses.
- Provider changes may intentionally emit capture frames without tracking after
  the existing 2-second aggregation wait. Tests require explicit timeout evidence,
  no fabricated observations, and resumed tracking on the selected provider.
- The CUDA physical benchmark measured 19.12 processed FPS on Python and 15.21 on
  Rust against approximately 30 FPS capture. Raw recordings passed their audits;
  this is not a claim of full-rate tracking or a TensorRT throughput benchmark.
- Forge's one skip is structural, not an unavailable recording. Its exact test is
  `test_chain_closure::test_root_placement_does_not_leak_into_relative_angles`.
- The session-provider diagnostic response retains its existing `list[dict]`
  schema; SDK consumers must not infer narrower guarantees from one response.

GPU/camera ownership was explicitly released at 16:53 ET on 2026-11-01. No matching
test-owned processes remained; user applications were not stopped. Cleanup evidence
is in `final-resource-cleanup.json` beside the failure ledger and hardware reports.

## Worktree preservation

The three cleanup worktrees were retired with ordinary non-force Git removal after
clean-status, merged-ancestry and process checks. Their branches and history remain.
All 72 ignored entries (87,601 filesystem objects), including environments and test
evidence, were preserved under canonical Core `.test-artifacts/retired-worktrees/`.
Before/after file identities, sizes, modification times and report/source hashes
matched. Nested reparse points were not traversed. Archived environments are for
restoration at their original paths, not claimed runnable at the archive location.

Provenance and verification: `.test-artifacts/w3-integration/retirement-manifest.json`.
Restoration instructions: `.test-artifacts/retired-worktrees/README.md`.
The archive is local and ignored, not a remote backup. Canonical normal imports were
verified again after retirement; other worktrees were left untouched.
