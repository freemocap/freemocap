# Recording API organization and terminology cleanup

2026-10-31. Planning only; implementation has not started under this plan.

Organize recording resources, processing commands, exports, and task status around
one recording identity. Remove the meaningless `scientific` category from product
language and code while preserving functionality, output contents, and supported
saved inputs. Keep capability routers and clear Swagger headings.

The owner accepted the overall API direction and requested reviewable work chunks
before starting individual linear tasks. This document is the work breakdown,
not an instruction to execute every stage. Each stage below becomes its own
bounded linear checklist when selected for implementation.

## Agreed direction

- Address recordings through `/freemocap/recordings/{recording_id}`. The ID is the
  folder name, consistent with the [recording contract](../../RECORDING_CONTRACT.md).
  Preserve a capture UUID separately when present.
- Use optional `recording_parent_directory` consistently. Omission selects the
  established default; supplying it selects another parent. Resolve the location
  once when accepting work and retain that identity throughout the task.
- Use HTTP for resource reads, commands, and task snapshots. Use WebSocket for
  live frames, logs, state, and task updates. Saved video/file delivery stays HTTP.
- Keep implementation routers by capability. They may share the recording prefix
  without sharing a large router implementation.
- Playback and exports consume shared recording access. Playback does not own
  recording discovery, calibration access, saved results, or exported files.
- Preserve client-owned play/pause/seek. A server playback-session abstraction is
  unnecessary for the current functionality.
- Use `ExportOptions`, `ExportRequest`, `ExportResult`, `data_channels`, and
  `DataProvenance` where they describe the existing objects. Avoid replacing the
  unwanted adjective with another empty category or a standalone `data` endpoint.
- Keep task identity, retained run identity, and content revision distinct.
  Overwriting a run changes its contents; a run ID is not immutable content identity.

## Evidence and implementation entry points

The audit read the running `http://localhost:53117/openapi.json` and the local
handlers and callers on branch `sfn26`. Source inspection establishes the current
connections below; it does not establish runtime test success. Recheck live routes
and the working tree at the start of each stage.

Paths in this table are relative to the core repository unless stated otherwise.

| Concern | Current implementation | Callers and contracts to preserve |
| --- | --- | --- |
| Registration and Swagger | `freemocap/api/routers.py`; `freemocap/app/app.py` functions `_register_routes`, `_customize_openapi` | Core `/freemocap`, independent `/skellycam`, root app routes, `/websocket/connect`; custom OpenAPI generation |
| Recording resolution and reads | `freemocap/api/http/playback/playback_router.py`; `recording_access.py`; `resource_loading.py` in the same directory | `RecordingStructure`, `RecordingAccess`, default paths, partial resource failures, response-lifetime read leases |
| Playback projections | `freemocap/core/recording/playback_queries.py`; `freemocap/core/playback/` | Rendering definitions, independent timelines, source associations, revision-bound Parquet reads, video range/codec delivery |
| Export requests and publication | `freemocap/api/http/posthoc/exports_router.py`, `export_jobs.py`; `freemocap/core/recording/exports/` | Channel selection, run/revision binding, export manifest, hashes, keep/replace, cancellation, recoverable publication |
| Automatic exports | `freemocap/core/pipeline/dataflow/recording_pipeline.py`; `freemocap/core/pipeline/posthoc/export_completion.py`; `freemocap/core/tasks/mocap/mocap_task_config.py` | Produced run selection, operation IDs, saved configuration, completion and failure reporting |
| Processing, capture, import, synchronization | `freemocap/api/http/mocap/mocap_router.py`; `freemocap/api/http/calibration/calibration_router.py` | Application methods, saved stage validation, recording ownership, capture-stop processing behavior, sync-before-import workflow |
| Task state and cancellation | `freemocap/core/pipeline/posthoc/task_snapshot.py`; `freemocap/api/http/posthoc/tasks_router.py`; mocap/calibration cancellation routes | Retained terminal status, server identity, revision ordering, recording owners; standalone export and sync registries differ |
| Realtime and WebSocket | `freemocap/api/http/realtime/realtime_router.py`; `freemocap/api/websocket/` | Camera group attachment, pipeline IDs, refit command, frame delivery, per-client feedback and disconnect behavior |
| Blender | `freemocap/api/http/blender/blender_router.py`; `freemocap/core/blender/` | Executable/package preparation, run selection, export configuration, optional open-on-completion, opening existing files |
| Frontend URLs and recording state | `freemocap-ui/src/constants/server-urls.ts`; `src/store/slices/playback-data/`, `recording-status/`, `calibration/`, `mocap/`, `pipelines/` | Encoded paths, alternate parents, cache identity, saved UI settings, completion refreshes |
| Frontend direct requests | `freemocap-ui/src/components/mocap-setup/mocap-scientific-settings.tsx`, `mocap-csv-settings.tsx`; `src/components/viewport3d/RecordingPlaybackProvider.tsx`; `src/services/server/task-progress.ts` | Requests outside the central URL helper, polling, previews, workers, resource invalidation |
| NumPy provenance format | SkellyForge: `skellyforge/core/data_tensors/data_tensor.py`, `numpy_io.py`, `numpy_manifest.py`, `recording_dataset.py` | Exported `scientific_provenance` field, strict manifest validation, constructors and readers used by core |

Uncommitted server-stop, connection-ownership, and reconstruction changes were
present during planning. Preserve them. In particular, reconcile shutdown work
with [connection ownership](connection-ownership.md) before changing its method or
callers. Do not overwrite concurrent work to match this audit snapshot.

## Target routes and Swagger categories

The table specifies the target shape. Stage 1 reconciles each entry with actual
requests and responses before implementation. Paths are relative to `/freemocap`
unless explicitly marked. Existing functionality omitted from a short example
must remain in the complete migration inventory.

| Swagger category | Target routes | Existing source or required behavior |
| --- | --- | --- |
| Recordings | `GET /recordings`; `GET /recordings/{id}`; `GET /recordings/{id}/status` | Move discovery and general status out of playback; descriptor inventories independently available resources |
| Recording results | `GET /recordings/{id}/runs`; `GET /recordings/{id}/runs/{run_id}/channels`; `GET /recordings/{id}/runs/{run_id}/stages`; `GET /recordings/{id}/parquet` | Shared saved-run queries; preserve stages needed for restart and revision checks for file reads |
| Recording media | `GET /recordings/{id}/media`; `GET /recordings/{id}/videos`; `GET /recordings/{id}/videos/{video_id}` and `/browser` | Existing source selection, timestamps, annotated-media associations, range reads and browser conversion |
| Recording calibration | `GET /recordings/{id}/calibration` | Existing recording-specific calibration resolution |
| Playback | `GET /recordings/{id}/playback/manifest`; `GET /recordings/{id}/playback/bundle` | Retain specialized rendering projections and efficient bundled load; classify tracker schema during Stage 1 |
| Recording exports | `GET /recordings/{id}/export-options`; `GET /recordings/{id}/exports`; `POST /recordings/{id}/exports` | Separate available selections, existing artifacts, and creation; include tall CSV, wide CSV, NPY, NPZ, notebook, and Blender capabilities explicitly |
| Recording processing | `POST /recordings/{id}/processing` | Preserve mocap and calibration-specific configuration through typed request variants; do not discard either workflow |
| Tasks | `GET /tasks`; `GET /tasks/{task_id}`; `POST /tasks/{task_id}/cancel` | Common observable lifecycle across processing, standalone exports, and synchronization; retain specific result schemas |
| Capture | Explicit start/stop commands | Retain camera recording, calibration buffering, and stop-then-process behavior; settle exact URLs in Stage 6 |
| Recording import | Import and pre-import synchronization commands | These can operate before a recording exists and need not be forced under a recording ID |
| Realtime processing | Configuration, apply, cancel, and skeleton refit under `/realtime` | Move cancellation out of `/mocap/realtime`; preserve camera group and pipeline identities |
| Blender | Detect, inspect, install package, open existing output | Recording export creation joins Recording exports; executable/package operations remain Blender capabilities |
| App, Cameras, FFmpeg, Telemetry | Retain distinct capability headings | Root health/shutdown and mounted camera API retain explicit ownership; unrelated tools do not become recording resources |

Use the literal parameter name `recording_id` in implementation; `{id}` only
shortens this table. The optional parent query applies to recording-addressed
routes and all generated links to those resources. A task ID resolves its stored
recording location without requiring the client to supply the parent again.

`GET .../exports` describes durable published artifacts, including their source
run and revision. It must not depend on an in-memory export job still existing.
`POST .../exports` starts work and returns a typed task reference with status and
result links. Existing exporter differences must be represented honestly: tall
CSV has a different selection contract, notebooks have selection restrictions,
and Blender requires executable/package settings. Choose typed variants in Stage
5 rather than pretending all outputs accept one identical options object.

Swagger tags are part of acceptance. Define ordered tag descriptions in the
OpenAPI setup, verify the custom `get_openapi` call includes them, and give routes
intentional summaries, stable unique operation IDs, typed success responses, and
documented failure responses. Keep hidden compatibility routes out of the primary
catalog. Document WebSocket messages separately; Swagger HTTP operations are not
a complete WebSocket protocol specification.

## Terminology rules and compatibility

| Current name | Intended name or treatment |
| --- | --- |
| `ScientificExportOptions`, `ScientificExportRequest`, `ScientificExportResult` | `ExportOptions`, `ExportRequest`, `ExportResult` in the exports module |
| `SavedScientificRequest` | Remove redundant recording-path request wrapper when identity moves to the route; keep a compatibility adapter only if needed |
| `scientific_exports` / `scientificExports` | `export_options` / `exportOptions`; preserve supported saved settings through explicit input migration |
| `scientificExportFormats`, `scientificExportData`, related UI state | `exportFormats`, `exportChannels`, and corresponding specific settings; inspect persisted state before renaming |
| `scientific_channels` | `data_channels`; preserve its current selection and segment-pose pairing behavior, and document that scope |
| `export_scientific` | `export_recording`; retain separate format implementations behind the public operation |
| `ScientificProvenance` / `scientific_provenance` | `DataProvenance` / `data_provenance`, with an explicit NumPy format compatibility stage |
| `scientific_recording.py`, `CompletedScientificRecording` | Provisional `recording_results.py`, `CompletedRecordingResults`; check adjacent names and actual responsibilities before moving |
| “scientific completion”, “scientific inputs”, “scientific definitions” | Processing completion, saved inputs, or the concrete model/definition type; state exactly which outputs are required |

Preserve distinctions between observations, estimates, fitted results, generated
values, source provenance, execution settings, entry presence, and validity.
Generic data structures must still support synthetic/generated inputs and generic
skeletons. Renaming does not make every value an empirical measurement or add new
channels to existing exports.

Classify matches before changing them: active product text; internal symbols;
serialized settings; serialized datasets; historical notes; quotations or actual
discussion of research. Current API/UI/docs must stop presenting a “scientific”
category. Historical compatibility readers and fixtures can retain old spellings
with explicit explanations. Do not rewrite external quotations or historical
records just to make a text search empty.

Migration policy to finalize in Stage 1: canonical new routes and names, one
implementation, and a bounded set of legacy adapters where existing clients or
saved inputs require them. Record each adapter, its consumers, and its removal
condition. Avoid redirecting POST bodies. New writers emit canonical names;
readers accept supported historical inputs. Conflicting old/new settings must
produce a deterministic error rather than silently selecting one.

## Work breakdown

Execute one selected stage at a time. Each stage delivers its production changes,
caller updates, focused tests, documentation, and a concrete review handoff.
The sequence below is a planning order; checklists are written before each stage
so current code and concurrent changes determine the exact bounded tasks.

### 1. Freeze the behavior and migration inventory — core

Trace every registered HTTP route, hidden route, and WebSocket entry to its
handler, application operation, UI/Electron caller, response, and test. Start with
`api/route_inventory.py`, the live schema, and the evidence table above. Include
directly constructed frontend URLs and standalone tools, not just `server-urls.ts`.

Resolve the remaining contract choices: export request variants, processing
variants, capture/import URLs, artifact retrieval links, tracker-schema placement,
task retention and result shape, and compatibility lifetimes. Record which old
routes map to each new route and which remain separate capabilities.

Deliver a reviewed route/consumer matrix, naming map, Swagger catalog, and focused
behavior tests for the contracts being moved. Useful existing anchors include
`test_hardware_server_harness.py`, `test_export_preview.py`, `test_playback_data.py`,
`test_recording_access.py`, and `http/test_mocap_router_import.py`.

Done when every existing capability has a destination and its caller migrations
and acceptance tests are identified. No production URL moves in this stage.

### 2. Establish shared recording identity and access — core

Extract resolution from playback into the recording module. Reuse
`RecordingStructure` and `RecordingAccess`; keep handlers as transport adapters.
Centralize path validation, default-parent behavior, and canonical identity.
Update frontend URL construction and cache keys to carry parent plus folder name.

Define the ownership policy for playback reads, export reads/publication,
processing, calibration updates, and Blender reads. Preserve response-lifetime
leases for streaming, cancellation cleanup, immutable source selection, and export
publication locks. Avoid deadlock when a processing task launches its own exports.

Done when alternate roots with identical folder names stay distinct, invalid IDs
are rejected consistently, busy recordings are reported consistently, and readers
release resources on completion/disconnect. Exercise existing recording-access
and browser-video tests plus focused tests for the newly unified access behavior.

### 3. Move recording resources and playback projections — core

Apply the resource routes and tags above. Build shared run/channel/stage queries
from saved recording metadata without requiring rendering model composition.
Keep the specialized playback manifest/bundle. Move the general resource models
out of playback only where they actually serve multiple consumers.

Migrate recording browser, status/calibration thunks, playback worker requests,
`RecordingPlaybackProvider`, returned video URLs, and resource cache invalidation
together. Preserve independent resource failures, raw-media-only recordings,
run selection, timestamp behavior, revision mismatch handling, and supported
recording layouts. Reading must not rename or regenerate user files.

Done when the existing playback workflows use the new routes with default and
custom parents. Validate `test_playback_data.py`, `test_playback_timelines.py`,
`test_browser_video_http.py`, and relevant `app-playback.spec.ts` /
`parquet-playback.spec.ts` scenarios. Inspect Swagger headings and response schemas.

### 4. Expose a common task lifecycle — core

Build on `TaskRegistrySnapshot` and retained posthoc snapshots. Adapt standalone
export and synchronization state to a common public task contract; preserve
their distinct executors and results. Provide typed start acknowledgments,
status/result links, terminal failure/cancellation, and consistent cancellation
requests. State retention and server restart behavior explicitly.

HTTP and WebSocket must describe the same task state. Include recording identity,
run/revision where known, task kind, progress, and errors. Handle pre-import tasks
that have no recording yet. Update frontend polling/progress, cancellation, and
recording refresh behavior. Closing a client does not cancel accepted work.

Done when processing, export, and synchronization can be observed and cancelled
through the common interface and reconnecting recovers terminal status. Test
`test_posthoc_terminal_progress.py`, `test_pipeline_cancellation.py`, export API
tests, and client task snapshot handling. Do not promise persistence across server
restart unless implemented; durable exported artifacts remain discoverable.

### 5. Unify recording exports and remove export terminology — core

Implement export-options, artifact inventory, and task-backed creation routes.
Reuse selection and publication code; keep format writers independently testable.
Include existing tall/wide CSV, NumPy, notebook, and Blender behavior through the
typed variants decided in Stage 1. Preserve Blender preparation and explicit
open-on-completion settings while returning promptly for long export work.

Rename export types/functions, UI components, configuration, logs, and operation
labels together. Migrate saved export settings. Keep automatic after-processing
exports bound to the produced run and separate their failure from result saving.
Coordinate their task reporting with Stage 4 without duplicating execution.

Done when old saved settings still load, new settings use the new names, exports
are discoverable after job eviction/restart, and new API/UI text has no invented
category. Test selection, stale revisions, exact arrays/tables, metadata, hashes,
keep/replace, partial failure, cancellation, notebooks, and Blender option
forwarding. Start with `test_scientific_export_api.py`, `test_numpy_dataset_export.py`,
`test_tall_csv_export.py`, `test_export_completion.py`, Blender API tests, and
`e2e/scientific-exports.spec.ts`; rename relevant tests with their implementation.

### 6. Align processing and remaining control routes — core

Migrate processing and saved-stage access to recording identity. Preserve
calibration and mocap configuration, selected source run/group, restart stage,
keep/overwrite, recording ownership, and capture-stop processing behavior.
Complete capture/import/synchronization routing from the approved Stage 1 map.
Place realtime creation/configuration/cancellation in the same capability family.

Correct typed responses and documented statuses, including the mocap stop handler
currently declaring Boolean dictionary values while returning string IDs/paths.
Change core shutdown to a mutation method with all UI/Electron callers updated,
after reconciling concurrent server-stop work. Inventory bulk cancellation
semantics explicitly; never accidentally broaden a single-task command.

Done when existing capture, stop/process, calibration, import/sync, saved-stage
restart, realtime apply/cancel/refit, and graceful shutdown behavior is preserved.
Use existing HTTP, lifecycle, cancellation, import, and server-stop tests; report
hardware-dependent checks separately from simulated route tests.

### 7. Isolate WebSocket client failures — core

Reconcile with the existing connection-ownership work. Classify malformed client
messages and disconnects separately from application failures. Validate feedback
messages and close the affected connection without setting the application kill
flag. Preserve bounded frame delivery, logs, state, and task updates.

Done when malformed input and one client's disconnect leave the backend and
another connected client functioning. Extend `test_websocket_disconnect.py` and
the relevant message/connection tests. Changing the number of WebSocket channels
is outside this stage unless a separate functional need is established.

### 8. Remove remaining active core terminology — core

Sweep pipeline/result symbols, errors, comments, generated guides/notebooks, UI
types, current domain docs, and tests using the naming rules above. Reconcile
`CONTEXT.md`, `RECORDING_CONTRACT.md`, and current plans with the owner’s vocabulary.
Keep algorithm values, units, reference frames, required-output checks, and
published schemas unchanged in this stage. Rename serialized operation IDs only
with their readers and retained historical status behavior accounted for.

Done when remaining active core uses are an explicit compatibility/dependency
list, not accidental terminology. Validate affected imports and meaningful
pipeline/export contracts. Preserve historical documents as history.

### 9. Rename provenance and migrate the NumPy contract — SkellyForge

Independent repository stage. Read its current instructions and compare its
branch with core's live declarations before editing. Rename `ScientificProvenance`
to `DataProvenance` and associated fields/helpers across the owning tensor module.
Inventory all consumers before selecting the compatibility implementation.

Version the serialized field change and preserve supported old dataset reads.
Document writer-version behavior and new-to-old reader compatibility limits.
Use intentional old-format fixtures, test old/new round trips, reject conflicting
fields, and compare tensor values, axes, timelines, companions, definitions, and
provenance. No regeneration or modification of user datasets as a migration step.

Done when Forge works independently and the old/new format behavior is explicit
and tested. Stop for the human to commit and push the named Forge branch. No core
consumer edits or dependency refresh before that handoff is confirmed.

### 10. Integrate the provenance contract — core

After the Forge handoff, verify the intended revision and consumed code under
the actual dependency arrangement. Core currently declares editable paths and
separate workspace source metadata; do not introduce or alter that arrangement
as part of this plan. Git/environment mutation remains human-owned or separately
authorized under workspace policy.

Update `numpy_dataset.py`, `saved_channel_arrays.py`, consumers, generated examples,
and tests to `DataProvenance`. Validate historical and new NumPy exports through
core and identify any Blender/additional consumer changes as separate repository
stages before declaring the format migration complete.

Done when core imports and export round trips pass against the reviewed Forge
revision and the compatibility inventory has no unexplained entries.

### 11. Correct camera HTTP mutations — SkellyCam, then core integration

Independent SkellyCam stage: replace GET stop-recording and pause/unpause mutation
routes with explicit mutation requests. Prefer an explicit desired pause state
over a retry-sensitive toggle. Inventory standalone SkellyCam UI consumers as
well as core consumers; preserve camera-group scope and recording behavior.

Validate standalone capture/control behavior, then stop for the human commit/push
handoff. Core caller migration follows as its own stage after confirmation. Choose
a documented compatibility window so the producer and consumer can be reviewed
independently; do not leave unsafe legacy GET behavior indefinitely.

### 12. Close the migration and verify the complete workflows — core

Reconcile the actual registered routes, OpenAPI catalog, client URL builders,
remaining inline URLs, examples, and compatibility inventory. Remove only adapters
whose documented retirement conditions have been met. Check Swagger grouping,
typed response/error schemas, operation IDs, and absence of unwanted canonical
terminology. Document any deliberately retained historical spellings.

Exercise existing recording discovery/playback, reprocessing, each export family,
import/synchronization, task reconnect/cancel/failure, and selected live capture
flows. Verify default and custom parents, same-name recordings, multiple runs,
stale revisions, partial recordings, old settings, and old datasets. Compare
numeric outputs and metadata against unchanged intentional fixtures, not filenames
alone. Record prerequisites/skips; do not infer hardware or Blender success from
mock-only tests. Update the maintained recording and transport contracts.

## Execution and review requirements

Every selected stage starts with current instructions, branch/status/diff, and
relevant dependency declarations. Preserve user work and keep all changes
unstaged and uncommitted. The human owns Git state and commit/push handoffs.
Never mutate multiple independent repositories in one implementation stage.

Before tests or diagnostics create files, identify output paths and verify the
owning repository ignores them with `git check-ignore`; use narrowly ignored
`.test-artifacts/` or external temporary storage. Intentional fixtures stay tracked.
Do not install dependencies or change environments merely to run a test.

For each handoff, report the concrete diff, affected callers, validation actually
run, unavailable prerequisites, and remaining compatibility entries. Check
untracked/generated files. A documented plan or an unchanged route response does
not by itself demonstrate preserved end-to-end functionality.
