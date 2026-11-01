# API cleanup validation

> Follow-up: all 24 baseline failures reported below have been resolved. The [remaining test failure fixes report](remaining-test-failure-fixes.md) records the final passing suites, physical-camera checks, and the one remaining model-prerequisite skip. Earlier results below are historical.

> The final full-validation section supersedes earlier partial results and missing-prerequisite notes. It includes physical cameras, both reference datasets, Blender, the complete browser suite, and the complete Python suites.

Worktree: `cleanup-api-terminology`, based on `64a068ff`. Changes remain
unstaged and uncommitted. The approved checklist controls execution order.

## Recording identity and resources (items 2–3)

- Shared identity/access tests: 17 passed.
- Resource/playback/timeline/video backend group: 33 passed; follow-up resource,
  schema and video-range checks: 12 passed.
- Frontend location/URL tests: 3 passed. TypeScript: passed.
- Parquet browser tests in installed Edge: 9 passed, 1 optional real-recording
  case skipped because its input was not configured.
- Electron video playback: 2 passed (native and conversion fallback), including
  seeking, source switching, reload and remount. The test launcher now handles
  Playwright's inspector arguments instead of assuming a fixed URL position.

## Common tasks (item 4)

- Existing processing/export/WebSocket regressions: 24 passed.
- Common-task and real-video synchronization/import group: 20 passed.
- Final common-task/operation-progress group: 11 passed.
- Frontend progress tests: 7 passed; TypeScript: passed.

HTTP and WebSocket use the same snapshot composer. Synchronization progress is
collected without a connected client. Export and synchronization observations
retain bounded terminal history. A cancellation request is distinct from a
completed cancellation. Source run/revision accompanies accepted exports.

## Recording exports (item 5)

- Export API, legacy adapters, automatic completion and Blender API group:
  42 passed, 2 failed before their intended assertions (environment limitation
  below), plus 2 passing subtests.
- Value preservation, tall/wide CSV, NumPy, generated notebook and Blender option
  checks: 66 passed, 2 environment-dependent cases deselected. One guide-fixture
  test initially double-converted CRLF to CRCRLF; after normalizing its input,
  the targeted test passed. The production guide preservation logic is unchanged.
- Export UI browser test: passed (empty result, unavailable selection, failure,
  retry, preferences and cancellation). Frontend export helper tests: 2 passed.
  TypeScript and focused lint checks: passed.

Canonical export options, inventory and creation share recording identity.
External jobs hold cancellable read leases; automatic exports remain within the
processing owner's operation. Inventory survives task eviction, reports source
revision, and distinguishes unverified, verified, changed and missing artifacts.
Blender/older outputs without manifests do not receive invented provenance.

## Export naming and settings (item 6)

Export types, functions, components and configuration now use the approved names.
Backend aliases load supported old snake/camel spellings and reject conflicts.
Browser migration preserves settings, writes canonical names and retains the
original saved object on conflicts until the user explicitly resets exports.

- Backend migration, export and completion group: 33 passed.
- Browser-settings migration unit tests: 2 passed.
- Export browser workflow: 3 passed (new, historical and conflicting settings).
- TypeScript, focused lint and source-reference scan: passed.

`test_scientific_export_api.py` is now `test_recording_export_jobs.py`; the export
browser test and component/type/style files were renamed with their callers.

### Remaining validation prerequisites

The reused Python environment has an incomplete installed
`freemocap_blender_addon` source directory. In `test_blender_export.py`,
`test_process_failure_cannot_pass_with_old_output` and
`test_process_isolation_and_missing_result` fail in `expected_build()` before
their mocked process assertions. No Python dependencies were installed or changed.
Real Blender execution/FBX/BVH output is not established by the passing API option
forwarding tests. Final validation must report or resolve this prerequisite.

Frontend locked dependencies were installed only after explicit owner approval,
inside this worktree. Package manifests and lockfile did not change. npm blocked
several install scripts; those were not enabled. Tests used installed Edge and
the source checkout's existing Electron executable. Test artifacts and caches
are ignored. A process check found no remaining video-test processes.

## Item 7 — command boundaries

Recording processing now accepts a discriminated mocap/calibration configuration at the recording URL. Capture start/stop, import/sync, and realtime stop have capability routes; hidden legacy handlers retain behavior. Capture stop reports typed recording/task references. Saved-stage preflight takes a short recording lease, released before processing reservation. Stage discovery provides an aggregate chooser and an individual run resource. Shutdown requires POST; panel and hardware-validation callers migrated.

Validation: 40 backend contract/capture/import/synchronization tests passed (both legacy and canonical real-video import paths); existing graceful-shutdown test passed. TypeScript and focused Ruff passed. Fifteen browser checks passed across calibration selection/processing, saved-stage selection, and shutdown controls (14 in initial run, fixed fixture's old URL and then its remaining test passed). Hardware capture and a full reconstruction run were not performed; manager dispatch/configuration and calibration buffering were exercised.

## Item 8 — WebSocket connection isolation

Connection exceptions no longer mutate the application fatal error or shutdown flag. Invalid acknowledgment JSON/shapes/non-finite dimensions close that connection with code 1008. Transport cleanup tolerates an already-closed socket and joins connection tasks. Application startup/resource failures and the shared log-relay health supervisor retain their fatal behavior.

Validation: 40 tests passed across concurrent clients (five malformed inputs, healthy task delivery, disconnect and reconnect), installed transport/backpressure handling, frame/log relays, common tasks, and genuine server failures.

## Item 9 — terminology and core handoff

Renamed the dataflow implementation to `recording_processing.py`, its completed result to `CompletedRecording`, and its processing entry points to `process_recording` / `process_resolved_recording`. Export operation IDs use `channel_exports`; progress labels, UI settings, benchmark/report names, active architecture documents, and generated export guides use recording/output terminology. Historical generated guides are recognized by their exact LF/CRLF hashes; three intentional fixtures verify refresh and preservation of user edits.

Remaining occurrences are deliberate: hidden legacy HTTP adapters and their tests; historical settings readers and migration tests; SkellyForge's `ScientificProvenance` / `scientific_provenance` contract pending items 10–11; historical fixtures and dated audit records; the mathematical term scientific notation and research/citation policy language. The approved checklist and migration history retain their original wording.

Validation: all 44 affected test modules were run. Final result: **353 passed, 15 skipped, 3 deselected, 42 subtests passed**. Skips require prepared reference recordings or real Blender prerequisites. The three explicit exclusions are the two previously recorded incomplete installed Blender add-on checks and `DatasetExecutionTests.test_graph_restart_is_rejected_before_reading_saved_files`. That unchanged assertion predates support for saved-stage graph processing: its mocked ready marker now reaches an attempted Parquet read. Only its module docstring changed here; the workflow implementation is unchanged. An initial capitalization regression in a renamed error was corrected and the complete affected suite rerun.

TypeScript passes. Three export/settings browser cases, three stacked-progress browser cases, and seven operation-state tests pass. The first progress launch lacked a bundled Chromium; rerunning against installed Edge passed, with existing CSS syntax/icon-case warnings. All 123 changed Python files parse. Ruff's only three findings also reproduce on HEAD: two runtime type imports in `test_reconstruction_state.py`, and one in `tools/hardware_validation/server_session.py`. No automatic unsafe import moves were applied. The current OpenAPI has 47 visible core/app paths, no scientific export paths, and no scientific export schema names. Item 14 remains the final integration/category reconciliation after producer migrations.

### Required repository boundary

Core changes remain unstaged and uncommitted in branch `cleanup-api-terminology`, worktree `repos/cleanup-api-terminology`. No dependency declarations or lockfiles were changed. The owner must review, commit, and push this core stage before implementation moves to SkellyForge. Workspace policy requires one repository at a time and an explicit human commit/push handoff. Items 10–14 remain incomplete. SkellyForge's workspace branch declaration is `sfn26`; inspect its checkout and instructions again after this handoff. Do not replace the current installed dependency or edit the original checkout to bypass the boundary.

## Local continuation authorized

The owner explicitly waived commit/push handoffs for this task on 2026-10-31. Continue items 10–14 through isolated local editable worktrees; leave all changes uncommitted. This supersedes the earlier required-boundary note above.

Item 10: SkellyForge worktree `repos/cleanup-provenance`, based on declared `sfn26` (1a58b8e). DataProvenance/data_provenance replace runtime names. NumPy writers emit v2; strict readers support v1 old fields and v2 new fields. A 4 KB original-writer v1 archive is an intentional regression fixture. 103 tests and 12 subtests passed, including NPY/NPZ migration, conflicting version fields, tensor ownership and standalone package independence. Original checkout untouched.

Item 11: core tensor/provenance consumers now use DataProvenance/data_provenance. Its own historical-v1 fixture loads and resaves as v2; outer export metadata retains the writer-reported format version. 41 integration tests passed, 1 prepared-data test skipped, 31 subtests passed. The isolated core `.venv` reuses unchanged installed third-party files and baseline editable mappings, with normal editable installs for core and cleanup-provenance. The original environment is untouched. Launch with `.venv/Scripts/python.exe -m freemocap` or `uv run --no-sync`; ordinary `uv sync` would restore baseline source declarations.

Item 12: standalone SkellyCam in `repos/cleanup-camera-api`, based on sfn26 (54921711), now uses POST recording-stop and PUT `/camera/group/all/pause` with strict boolean `paused`. Python and Rust managers set desired state instead of toggling. Standalone UI sends the explicit state and assigns the returned value, avoiding a second toggle after a WebSocket update. Thirty HTTP/backend/recording-finalization tests passed; TypeScript passed. Corrected numeric test fixtures to real NumPy records and updated an obsolete shutdown-test patch from os.kill to the existing signal.raise_signal implementation. No production shutdown implementation changed.

## Item 13 — core camera integration

Installed the camera cleanup worktree editable into the isolated core environment; verified import location. Core recording-stop callers now POST, including hardware campaign cleanup. Pause callers PUT explicit desired state; Redux uses the acknowledged state. The browser-store request test covers pause/resume with a WebSocket update arriving before each HTTP acknowledgment and recording stop. TypeScript passed; 10 capture/calibration control tests passed against the migrated camera package. Hardware campaign pause and resume explicitly request true and false. No physical-camera run was performed.


## Item 14 - final integration and review

The initial item-14 review below was incomplete and was reopened for the full validation recorded at the end of this document. The owner's local-integration authorization supersedes historical commit/push gates; no changes are staged or committed. Dependency declarations and lockfiles are unchanged.

The assembled public API has 54 paths, with one declared capability heading per operation, unique operation IDs, no scientific export URLs or schema names, POST shutdown/recording-stop, and PUT explicit camera pause state. Historical export/settings adapters remain deliberately hidden or migration-only. FFmpeg uses its declared heading. Router registration logs router prefixes rather than assuming nested FastAPI router entries have endpoint attributes; the real backend now starts successfully with the complete router tree.

Calibration updates and Blender discovery/launch now participate in recording access coordination. Busy recordings return 409. An admitted calibration write finishes its file-locked revision-checked update before queued processing begins. Blender's lease protects discovery and process launch; an external interactive Blender session is not held under a server lease for its entire lifetime.

Final validation:

- 47 affected Python modules: 376 passed, 19 skipped, 3 explicitly deselected, 55 subtests passed. Skips require prepared reference recordings or real Blender executable/add-on prerequisites. The three exclusions remain the previously documented two incomplete installed-add-on checks and the obsolete saved-graph restart assertion; this is not a claim that the entire repository suite passes.
- SkellyForge: 103 tests and 12 subtests passed, including historical v1 NPY/NPZ reads and v2 round trips. SkellyCam: 30 backend/control/finalization tests and 5 standalone shutdown tests passed.
- Core and camera TypeScript checks passed. Core request/reducer checks verify explicit pause/resume, POST stop, and pushed-state/HTTP acknowledgment ordering.
- Twelve selected browser workflows passed: exports/settings migration, concurrent progress, shared processing-stage selection, calibration save, CSV task completion/errors, and native/converted app playback. The CSV test fixture was updated from the obsolete route and separate run picker to the actual shared source run and task result API. Eleven cases passed in the initial batch; the corrected CSV case passed separately.
- Real backend smoke: isolated free port and data/log directories, successful startup, live OpenAPI and Swagger, route inventory generation, POST shutdown, exit code zero. The original server was not stopped.
- All worktree diffs pass git diff --check. No staged changes or tracked generated artifacts were introduced. Four documentation files had non-UTF-8 punctuation repaired. Ruff reports only the three previously verified baseline type-import findings. Existing CSS media-query and icon-case browser build warnings remain.

At that initial review, physical cameras and real Blender exports had not been tested. This limitation is superseded by the full validation below. Test reports and logs are ignored under .test-artifacts/api-cleanup/.

To run this integrated version, use the cleanup-api-terminology worktree's .venv/Scripts/python.exe -m freemocap --port <available-port>. Its core, SkellyForge, and SkellyCam editable imports point to cleanup-api-terminology, cleanup-provenance, and cleanup-camera-api respectively. Other dependencies retain their original installed versions and editable mappings. Use uv run --no-sync if launching through uv; ordinary uv sync would restore the unchanged baseline source declarations. The original checkout and environment remain available.


## Item 14 — full validation after reopening

Completed on 2026-10-31 in the same three cleanup worktrees. No commits, pushes,
lockfile changes, or original-checkout source edits were made. Existing concurrent
work in the original core checkout, including its bibliography, was preserved.

### Actual workflow coverage

| Workflow | Result |
| --- | --- |
| Extended physical-camera campaign | 45 scenarios on Python and 45 on Rust, using all four cameras and every nonempty subset. Initial result: 86 passes and four failures (duplicate start and idle stop on each backend). Both defects were fixed. Ten affected recording scenarios then passed: four-camera recording, close during recording, repeated start, idle stop, and pause during recording on each backend. |
| Calibrated realtime tracking and recording | Passed on Python and Rust. Recorded videos were decoded and checked against timestamps. |
| Production UI with real cameras and tracking | Passed on Python and Rust using the existing Electron binary. |
| Raw/tracked/raw camera transitions | Passed on both backends; camera identity and orientation comparisons passed. |
| Native camera lifecycle polling | The normally opt-in physical-camera test passed with an explicitly selected available camera. |
| Fresh reference datasets | Both `freemocap_test_data` (222 frames) and `freemocap_sample_data` (1108 frames) passed the standard acceptance workflow: fresh calibration, RTMPose, reconstruction, exports, Blender, and saved-scene motion validation. Source recordings were preserved. |
| Processing-stage matrix | All 15 contiguous start/finish combinations passed, including numerical comparisons against the full run. |
| Uncached producer regression | Passed separately in a fresh output tree. This test intentionally replaces prepared outputs, so it ran separately from consumers that require those outputs to remain immutable. |
| Live canonical HTTP/WebSocket API | Passed real recording-scoped reconstruction and channel, tall CSV, and Blender export tasks. HTTP and WebSocket agreed on all four completed tasks. Verified inventory contained 36 artifacts across wide CSV, NPY, NPZ, notebook, tall/static CSV, and Blender. |
| Browser suite | All 87 tests passed, including real sample-recording Parquet playback, exports, calibration, production UI startup/shutdown, Electron streaming, and camera controls. |
| Blender integration | Both datasets passed both segment and constraint routes, automatic managed-profile installation, explicit installation, scene reopening, and FBX output checks. Installed-package fingerprint enforcement passed. The real PyInstaller frozen-backend test passed, including relocation and exports of both datasets. |
| TypeScript and source checks | Both UI type checks passed. Critical Ruff checks passed across all 142 changed core Python files. All three worktree diffs pass `git diff --check`. |

The native tests and benchmark harnesses own their server processes and isolated
application folders. Every completed server cleanup report records exit code 0
and no errors. No test-owned backend, camera, browser, or Blender process remains.
Timing measurements were collected during concurrent validation and are not an
isolated performance benchmark.

### Fixes discovered by full validation

- Editable Blender distributions store metadata separately from their source.
  Resolve editable source through its installed module specification, without
  importing the add-on's Blender-only code. Normal wheels and frozen bundles
  retain their existing resolution paths. This also resolves the two previously
  excluded Blender process tests.
- Reserve recording state before awaiting worker startup. Repeated starts can no
  longer overwrite an active recording, and idle stops return HTTP 409. Stop and
  close release the reservation. Camera and core capture routes expose these
  conflicts consistently. Physical reruns verified saved video/timestamp counts.
- Update hardware harness URLs to the canonical realtime routes and allow the
  production UI observer to use the existing Electron executable.
- Repair stale browser fixtures for the actual alignment selector, canonical
  configuration/task contracts, Redux dispatch promises, and export responses.
  Replace the obsolete Vite demo test with the production server/UI observer.
- Repair stale Python fixtures: use `CaptureGroup` for realtime replay, resolve
  artifact paths relative to their manifest, inspect FBX under `exports/3d_models`,
  select the explicit run in Blender profile/fingerprint fixtures, and explicitly
  select the legacy coordinator in tests that mock that coordinator. Its tiny
  synthetic single-camera fixtures disable automatic Blender export; full real
  datasets and separate Blender integration tests validate that export workflow.
  The obsolete graph-restart rejection test now checks the required prepared
  recording instead of rejecting a supported operation.

### Complete suite results and remaining baseline failures

The complete core suite ran with all available recording, Blender, and frozen-build
prerequisites enabled: **1224 passed, 17 failed, 117 subtests passed, no skips**.
The separate fresh producer test passed. Sixteen failing checks were corrected
and passed on focused reruns: calibration replay (1), tall CSV acceptance (2),
Blender artifact locations (4), Blender profile/fingerprint checks (2), and
legacy-coordinator/metadata fixtures (7). Four new capture-conflict cases also
passed. This is a full run plus verified corrections, not a claim that the initial
full run was green.

The one remaining core failure is
`test_model_scale_in_the_loop.py::test_a_subject_at_a_desk_still_gets_correctly_sized_feet`.
The seated fit is 1584.2657417553319 mm versus 1684.1504338313796 mm standing,
outside the existing 5% tolerance. The identical test and values fail in the
untouched original core/Forge environment, with import locations verified.
No numerical algorithm or tolerance was changed to hide this existing issue.

The complete SkellyCam suite produced **342 passed, 23 failed, 1 skipped**.
The skipped physical native-polling test subsequently passed with camera access.
All 23 failures reproduce in the clean original SkellyCam checkout at the same
revision (`549217112fd68f367da9acc83681caf53d8d9a43`), using the same dependencies.
They concern numeric/type fixtures, filename expectations, uninitialized test log
queues, timebase conversion, standalone WebSocket logger initialization, and
obsolete worker-monitor patches. Their exact test IDs and diagnostics are retained
in the baseline comparison. They remain outside this API/terminology cleanup.

The complete SkellyForge suite produced **903 passed, 1 skipped**. Its skip reports
that the shipped model has no adjacent rigid-fit pairs for the requested
root-placement angle check; it is not a missing camera or dataset prerequisite.

Thus the repository-wide suites still contain **24 reproduced baseline failures**
(one core, 23 camera). The cleanup's real workflows and corrected regression checks
pass. The final checklist acknowledges these explicit remaining limitations.

### Reproduction and local evidence

The ignored manifest `.test-artifacts/api-cleanup/full-validation/paths.json`
records Blender, add-on wheel/archive/profile, and the temporary output roots.
Current roots are `C:/Users/jonma/AppData/Local/Temp/fmc-api-gsr9_xoo` (logs and
JUnit) and `C:/tmp/fmc-4lokv7vn` (prepared recordings and short-path test outputs).
Short output paths avoid Windows path-length failures in Blender dependencies and
long sample video filenames. Failed initial attempts are retained as diagnostics.

The standard dataset workflow used `python -B -m freemocap.tools.datasets process-all`
with the original recordings root, a separate prepared root, explicit Blender,
`--output-profile standard`, and a 1800-second timeout. Stage coverage used
`python -B -m freemocap.tools.datasets.stage_matrix` with the fresh calibration.
The hardware runs use `python -B -m freemocap.tools.hardware_validation` with
`camera-suite --backend both --suite extended`, `pipeline-benchmark --backend both`
(with and without `--with-ui`), and the `camera_transition` module for each backend.

Key evidence:

- Worktree `.test-artifacts/api-cleanup/full-validation/`: `cameras-01`,
  `cameras-fixed`, `tracked-capture`, `tracked-ui`, `transition-python`,
  `transition-rust`, and the reproducible `real_api.py` diagnostic.
- Log root: `full-core.xml/log`, `full-camera.xml/log`, `full-forge.xml/log`,
  `baseline-camera.xml/log`, `baseline-scale.xml/log`, `browser-final.log`,
  `fresh-producer.xml/log`, `blender-fixed.xml/log`, `final-fixtures.xml/log`,
  `csv-control-fixed.log`, `cache-rerun.log`, and `native-polling.log`.
- Short output root: `p/*/ready.json`, `matrix/matrix.json`, `matrix/report.txt`,
  and `api-2/report.json`. The API report records matching HTTP/WebSocket statuses.

All generated outputs are ignored or outside source checkouts. No generated
artifacts became tracked. The integrated launch command remains the isolated core
worktree's `.venv/Scripts/python.exe -m freemocap --port <available-port>`.
