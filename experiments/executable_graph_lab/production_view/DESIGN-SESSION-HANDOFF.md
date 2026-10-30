# Design-session handoff: FreeMoCap post hoc pipeline graph view

Written 2026-10-30 from a code-reading session in the core checkout
`C:/Users/jonma/code-stuff/github/freemocap/project/repos/freemocap`, branch `sfn26`, HEAD `8a58f7ba`
("Document the production graph interface handoff"). Everything under "What exists" was read from the
files named; everything under "Design" is a proposal that the user has partly approved (see "Decisions").
Paths are relative to that checkout unless stated otherwise.

## 1. Purpose of the next session

Produce a Design artifact (mockups) for a second, graph-based view of the existing Mocap processing
modal: the real typed-data-flow pipeline drawn as typed nodes, configurable by clicking nodes, and
showing per-node progress once a run is launched. Build it with the FreeMoCap UI design system
(claude.ai Design System artifact "FreeMoCap UI", Skull theme) on top of the app's existing CSS
architecture. Do not touch the backend. Collect anything the frontend needs that the backend does not
provide as explicit asks for a separate "integration agent"; the user relays handoffs between agents.

Governing documents already in the repo, read these first:

- `experiments/executable_graph_lab/HANDOFF-UX-UI.md`: the UX/UI agent brief and non-negotiable
  lessons (stable geometry under zoom, no enlarged labels, inputs left or top and outputs right or
  bottom, no delivery jargon on edges, no fictional dependency edges, distinguish disk reads, disk
  writes and computation, counts with units, unknown progress is indeterminate, plain verb labels).
- `experiments/executable_graph_lab/APPLICATION-INTEGRATION-AUDIT.md`: architecture inventory,
  mismatches, proposed shared contract (processing draft, processing plan, run snapshot).
- `experiments/executable_graph_lab/README.md`: the accepted visual direction is the synthetic viewer
  `experiments/executable_graph_lab/synthetic/viewer.html`, served by
  `.venv/Scripts/python.exe -B experiments/executable_graph_lab/synthetic/server.py --port 8766`.
  Screenshots exist locally at `.test-artifacts/graph-lab-live/full-pipeline.png` and
  `fixed-zoom-styling.png`.
- Workspace rules in `../project/AGENTS.md`: never mutate Git state, leave edits unstaged, ignore
  generated artifacts before creating them, prefer `.test-artifacts/`.

## 2. Decisions the user made in this session

- Placement: option A, the graph is a second view inside the existing Mocap processing modal
  (List | Graph switch), not a new page and not only in the progress panel.
- Styling source of truth: the claude.ai "FreeMoCap UI" design system, Skull theme as default. Its
  files were downloaded to `freemocap-ui/design-system/` (README.md, audit.md, tokens.json,
  manifest.json; untracked). Values are reproduced in section 5 so nothing needs re-downloading.
- Sections 1 and 2 of the design (modal shell and lifecycle; graph content) were drafted and shown;
  the user has not yet confirmed them. Sections 3 to 5 (configure interaction, run view, visual
  language) and the backend-ask list are outlined but not yet presented.
- Scope for now: the post hoc mocap pipeline only. Broader application of the design system to the
  rest of the app is a later task.

## 3. What exists today (verified in code)

### 3.1 The configuration surface

- `freemocap-ui/src/components/mocap-setup/mocap-setup-modal.tsx`: a `role="dialog"` with
  `ModalWindowControls` (move, resize, maximize), a left nav of eight sections and a scrolling body:
  Recording directory, Processing stages, Detectors, Camera geometry, Triangulation, Post-processing,
  Exports, Blender. Each section is a `SettingsSection` with `SettingsSummaryChip` summaries. Footer:
  Cancel (`ButtonSm quaternary`) and "Process Mocap" (`ButtonSm primary accent` with
  `processmocap-icon`). Mode `playback` shows Stages and Process; mode `recording` hides Stages and
  shows Save.
- Modal-local React state, not Redux: `pipelineImplementation` ('typed_dataflow' default | 'current'
  legacy), `graphExecutionProvider` ('auto' | 'cpu' | 'cuda'), `sourceRunId`, `stageSelection`.
- `mocap-stage-selection.tsx`: fetches `GET /freemocap/mocap/recording/process/stages?recording_path=`
  for the saved-stage inventory (runs, sensor groups, which stages are saved). Controls: Starting data
  (run + sensor group), Save results ('overwrite' | 'new_run'), and a five-item checklist where
  checking a stage runs it and all later stages. Per-stage status words: Run, Rerun, Reuse saved,
  Saved, Not saved, Not requested, Removed after save, In original run only.
- The five stages, from `freemocap-ui/src/services/recording/posthoc-processing.ts`:
  `observations` "2D tracking (SkellyTracker)", `triangulation` "Triangulation (3D points)",
  `filtering` "Gap filling and filtering", `scale_fit` "Person scale fitting", `reconstruction`
  "Skeleton reconstruction and biomechanics".
- Settings rows reuse the settings-layout grammar (`components/common/settings-layout/`):
  `SettingsSection`, `SettingRow` (label | required info | control), `SettingSelectInput`,
  `SettingToggleSwitch`, `SettingsGroupHeading`, `DependentRowGroup`, `SettingsSummaryChip` with tones
  neutral, quiet, positive, path. Real rows: Detectors = Skeleton detector (RTMPose | MediaPipe
  Holistic), Model, Confidence threshold, MediaPipe confidences, Board group with "Detect and
  reconstruct Charuco board". Triangulation = camera matching rows, Use outlier rejection, Minimum
  cameras for triangulation, Maximum cameras to drop, Target reprojection error. Post-processing =
  skeleton anchor, Filter trajectories, Sampling rate (from timestamps), Cutoff (Hz), Order.

### 3.2 The request

- `buildPosthocConfig(state)` in `freemocap-ui/src/store/slices/mocap/mocap-thunks.ts` assembles the
  config from Redux (`state.mocap.config`, `state.blender`, `state.calibration`). `processMocapRecording`
  spreads the `StageSelection` over it and POSTs `{mocapRecordingDirectory, mocapTaskConfig}` to
  `POST /freemocap/mocap/recording/process` (`freemocap/api/http/mocap/mocap_router.py`).
- The backend validates it as `PosthocMocapPipelineConfig`
  (`freemocap/core/tasks/mocap/mocap_task_config.py`): aliases `pipelineImplementation`,
  `graphExecutionProvider`, `graphAnnotate` (default true), `startStage`, `stopStage`, `baseRunId`,
  `runSaveMode`, `sensorGroup`, `cameraMatching`, `bodyAlignment`, `filterConfig`,
  `charucoTrackingEnabled`, `boardMode`, `charucoBoard`, `detectorType`, `rtmPoseModelName`,
  `rtmPoseConfidenceThreshold`, `mediapipe*`, `calibrationTomlPath`, `triangulationConfig`,
  `exportTallCsv`, `scientificExports`, `blender*`, `exportToBlender`, `autoOpenBlendFile`.
  Validators: stop must not precede start; early stops and new runs require `typed_dataflow`.
- Response is a launch acknowledgement with `pipeline_id`; completion arrives through snapshots.
  Cancel: `DELETE /freemocap/mocap/posthoc/pipelines/{pipeline_id}`.

### 3.3 The progress feed

- The server sends a complete retained `TaskRegistrySnapshot` over the WebSocket as message kind
  `progress` every 0.5 s (`freemocap/api/websocket/websocket_server.py`). Contract on both sides:
  `freemocap/core/pipeline/posthoc/task_snapshot.py` and
  `freemocap-ui/src/services/server/transport/message-contract.ts` (Zod).
- Snapshot shape: `server_instance_id`, `revision`, `recording_owners[]`, `tasks[]`. Task:
  `task_id`, `revision`, `task_type` ('calibration' | 'mocap'), `recording {base_directory,
  recording_name, full_path}`, `status` ('running' | 'complete' | 'failed' | 'cancelled'),
  `progress {phase, progress_fraction | null, detail}`, `operations[]`, `timing | null`, `cameras[]`
  (legacy per-camera video nodes), `created_at`, `updated_at`.
- Operation (`OperationProgressSnapshot` / `TaskOperation`): `operation_id`, `label`, `status`
  ('waiting' | 'running' | 'complete' | 'failed' | 'cancelled'), `progress_fraction | null`,
  `detail`, `completed | null`, `total | null`, `unit | null`, `elapsed_seconds | null`,
  `seconds_per_motion_frame | null`.
- Timing (`RunTimingSnapshot`): `elapsed_seconds`, `motion_frame_count | null`,
  `seconds_per_motion_frame | null`.
- Task phases that reach the UI (`pipeline_phases.py`, mapped in `pipelines-slice.ts`
  `phaseForTask`): `queued`, `setting_up`, `processing_images`, `collecting_camera_output`,
  `building_recorders`, `triangulating`, `filtering`, `reconstructing`, `exporting_csv`,
  `exporting_blender`, `validating_observations`, `running_solver`, `saving_calibration`,
  `complete`, `failed`.
- Rendering today: `freemocap-ui/src/components/pipeline-progress/PipelineGroupCard.tsx` (recording
  name, type badge, timing, Open folder, Load in playback, Stop) and `OperationProgressBars.tsx` (one
  row per operation: label, elapsed, ms per mocap frame, state and percent, 4 px track
  `.sub-progress-track`, indeterminate animation, count with unit, collapsible detail). Shown in
  `PipelineProgressSnackbar.tsx`, a draggable, resizable bottom-right window mounted in
  `app/AppContent.tsx`. Status colours used: `--color-info` running, `--color-success` complete,
  `--color-error` failed (note: `--color-error` is undefined in color.css; falls back).
- The slice (`pipelines-slice.ts`) applies snapshots by revision, groups by `task_id`, keeps
  dismissals in localStorage.

### 3.4 The production graph (typed data flow V1)

Contracts: `freemocap/core/pipeline/dataflow/definition.py`. `GraphNode {id, operation,
execution_resource, inputs[], outputs[]}`, `GraphPort {name, contract {kind, data_granularity,
namespace, reference_frame, units}}`, `GraphConnection {source {node, port}, target {node, port},
binding}`, `GraphDefinition {nodes, edges}`, `CompiledGraph {definition, topological_order}`. The
recording executor accepts recording-level `same_key` bindings only.

Builder: `freemocap/core/pipeline/dataflow/recording_pipeline.py` `build_recording_pipeline`. Every
node has exactly one output port named `result`. Resources: `compute` (capacity 2), `recording_io`
(capacity 1), `annotation` (capacity 2), from `recording_executor.py`. Full run
(start `observations`, stop `reconstruction`), in build order:

| node id | resource | inputs (port: kind, from node) | output kind |
|---|---|---|---|
| `load_and_track` (or `load_saved_observations` when starting at triangulation) | compute | none | `camera_observations` |
| `match_and_triangulate` | compute | observations: camera_observations, from the observation node | `raw_recording_geometry` |
| `filter_trajectories` | compute | science: raw_recording_geometry, from match_and_triangulate | `filtered_trajectories` |
| `align_reference` | compute | science from match_and_triangulate; filtered from filter_trajectories | `aligned_recording` |
| `reconstruction_input` | compute | aligned from align_reference; filtered from filter_trajectories | `reconstruction_input` |
| `fit_model_dimensions` | compute | request from reconstruction_input | `recording_model_fits` |
| `reconstruct_skeletons` | compute | request from reconstruction_input; fits from fit_model_dimensions | `reconstructed_models` |
| `observation_request` | compute | observations from the observation node | `observation_recording_request` |
| `save_observations` | recording_io | request from observation_request | `saved_observations` |
| `spatial_request` | compute | request from observation_request; science from match_and_triangulate; filtered from filter_trajectories; aligned from align_reference | `spatial_recording_request` |
| `save_spatial` | recording_io | request from spatial_request; saved_observations from save_observations | `saved_spatial` |
| `save_recording` | recording_io | request from spatial_request; saved_spatial from save_spatial; aligned from align_reference; reconstructions from reconstruct_skeletons | `saved_recording` |
| `annotate_camera_{i}` (one per camera, only when annotate is on) | annotation | observations from the observation node | `annotated_video` |

Variants, all from the same builder:

- Stop at `observations`: terminal node `save_observations`; only its ancestors (plus annotation
  nodes) are compiled.
- Stop at `triangulation` or `filtering`: `stage_result_request` (request from spatial_request) and
  `save_stage_result` (request from stage_result_request; saved_observations from save_observations)
  replace `save_spatial` and `save_recording`. Filtering and alignment still run (the UI note says
  so too).
- Stop at `scale_fit`: `save_model_fits` (saved from save_spatial; fits from fit_model_dimensions)
  is the terminal node.
- Start at `filtering`, `scale_fit` or `reconstruction`: a different, smaller graph from
  `saved_spatial_pipeline.py`: `load_saved_spatial` (recording_io) → optional `filter_trajectories`
  (only when starting at filtering) → `reconstruction_input` → `fit_model_dimensions` or
  `load_saved_model_fits` (when starting at reconstruction) → optional `reconstruct_skeletons` (only
  when stopping at reconstruction) → `save_stage_result` (recording_io). Ports there are also
  recording-level, kinds `saved_spatial_inputs`, `filtered_trajectories`, `reconstruction_input`,
  `recording_model_fits`, `reconstructed_models`, `saved_recording`.
- Export nodes `export_scientific` and `export_tall_csv` exist in the builder but the application
  disables them inside the graph (`application_pipeline.py` overrides `export_to_blender`,
  `scientific_exports`, `export_tall_csv` to off) and runs exports afterwards (see 3.6).

Progress mapping: `application_pipeline.py` `progress(node, event, fraction)` reports each node as an
operation whose `operation_id` equals the node id, with `describe_active_operation(node)` as label.
Tracking additionally reports `completed`/`total` in unit `camera images` (frames × cameras) and a
label like "Detect poses and ChArUco board points in 3 videos (RTMPose, CUDA GPU)". Blocked nodes are
reported `failed` with detail "Cannot run because required work failed: ..." or `cancelled` with
"Stopped before starting". Per-node `elapsed_seconds` come from the executor
(`RecordingExecutionResult.elapsed_seconds`, `started_seconds`, `finished_seconds`, `failures`,
`failure_tracebacks`, `blocked`).

Backend labels (`NODE_LABELS` in `application_pipeline.py`), keep them in the inspector:
load_and_track "Reading videos and detecting poses and requested board points";
match_and_triangulate "Matching camera views and calculating 3D points"; filter_trajectories "Filling
gaps and smoothing 3D point movements"; align_reference "Orienting 3D motion in the recording
coordinate system"; reconstruction_input "Preparing 3D points for skeleton fitting";
fit_model_dimensions "Fitting skeleton body dimensions to this recording"; reconstruct_skeletons
"Calculating skeleton positions and joint rotations"; observation_request "Preparing detected image
points for saving"; save_observations "Saving detected image points to disk"; spatial_request
"Preparing reconstructed 3D points for saving"; save_spatial "Saving reconstructed 3D points to disk";
save_recording "Saving reconstructed motion to the recording Parquet file"; load_saved_observations
"Loading saved 2D tracking and recording timing"; load_saved_spatial "Loading saved 3D points and
their coordinate frame"; load_saved_model_fits "Loading saved skeleton body dimensions";
save_model_fits "Saving fitted skeleton body dimensions"; stage_result_request "Preparing completed
3D results in the requested coordinate frame"; save_stage_result "Saving the requested processing
stages"; annotate_camera_N "Drawing tracking overlays and saving annotated video N+1".

### 3.5 Setup before the graph

`_run_application_graph` reports phase `setting_up` with details such as "Checking the inputs
required for the selected processing stages" and board-selection progress, resolves the execution
provider ('auto' becomes cuda when onnxruntime has CUDA, cpu for MediaPipe), loads saved inputs, and
holds a per-recording file lock. These are task-level phase and detail, not operations.

### 3.6 Exports after the graph

`complete_mocap` → `export_completion.py` `complete_recording_exports`. They report as operations
through `report_export` with ids `scientific_files` ("Save WIDE CSV files" etc., with
`completed`/`total` in unit `channels`), `tall_csv` ("Save tall CSV files") and `blender` ("Create
Blender scene and animation exports"), phase `exporting_csv`. Scientific and tall CSV serialize; Blender
runs concurrently. Failures keep saved results and are reported per export.

### 3.7 Stage dependencies

`freemocap/core/pipeline/posthoc/stage_dependencies.py`: OBSERVATIONS ← TIMING; TRIANGULATION ←
OBSERVATIONS; FILTERING ← TRIANGULATION, TIMING; SCALE_FIT ← FILTERING; RECONSTRUCTION ← FILTERING,
SCALE_FIT; BIOMECHANICS ← RECONSTRUCTION, SCALE_FIT, TIMING; REPROJECTION ← RECONSTRUCTION.
`stage_execution_plan.py` computes execute/invalidate sets and the target run id (keep → max run + 1).

### 3.8 What the backend does not provide yet (source of the asks)

- No graph-preview or plan route; `build_recording_pipeline` also loads calibration and builds
  handlers, so it cannot be called on every settings edit.
- Snapshots carry operations but no topology, plan identity, node-to-stage membership, configuration
  bindings, artifact paths or dependency-wait reasons.
- Tracking reports one counter for all cameras; no per-camera lanes in V1 (the legacy pipeline's
  `cameras[]` snapshots are per camera, but that is the other implementation).
- Stage, run and execution choices are modal-local UI state.

## 4. The accepted Graph Lab reference (what to carry, what to drop)

From `synthetic/viewer.html` and `production_view/layout.js`:

- Carry: node card with title header, typed input slots on the left edge and output slots on the
  right edge (dot + name + type), a state icon per node (pending ring, running pulse, complete check,
  failed cross, blocked slash, cancelled dashed), a thin progress bar inside running nodes, curved
  edges between slot dots, left-to-right default with a top-down alternative, zoom that scales the
  view only (level-of-detail hides secondary text at distant zoom), focus mode that dims unrelated
  nodes, a legend, and a disk terminal drawn as a folder joined to the node by a rail with an arrow
  that says load or save, listing file names. Inspector: eyebrow, title, state pill, description,
  progress block (big count, bar, counts), slot rows with type, key-value facts, collapsible raw JSON.
- Drop: pause, resume, step, hold, injected failure, resource-slot meters, synthetic cost, "Expand
  cameras" unless the backend reports lanes, per-type palette of 14 hues (FreeMoCap reserves hue for
  status), IBM Plex fonts and the SkellySpeak token names (`--bg`, `--sheet`, `--ink`, `--accent`).

## 5. The design system (FreeMoCap UI, claude.ai artifact; copied values)

Architecture to keep (from its README): one ordered import chain `src/index.css → styles/App.css`
(`reset → font → icons → color → animation → feature sheets → toggle → button-sm →
pipelineProgress`), three colour layers in `color.css` (raw ramps, semantic aliases, domain aliases;
components use layers 2 and 3 only), utility classes as the API (`flex items-center gap-1 p-1 br-1
bg-dark text-white`; `p-1` = 4 px, `br-2` = 8 px), icons as CSS background masks
(`span.icon.<name>-icon.icon-size-20`, files in `src/assets/icons/`, 20 px viewBox), and the
settings-layout grammar.

Skull theme, layer 1 (only these change per tint; semantic names stay):

- gray-900 `#121c1c`, gray-800 `#242e2e`, gray-700 `#353f40`, gray-600 `#444f4f`, gray-500 `#737b7b`,
  gray-400 `#babfc0`, gray-300 `#c0c6c7`, gray-200 `#ced3d3`, gray-100 `#e1e5e5`
  (Classic on disk: `#141414 #212121 #2e2e2e #3a3a3a #606060 #aaaaaa #b4b4b4 #cdcdcd #e4e4e4`).
- blue (teal accent) 100 `#badadb`, 200 `#a2cfd1`, 300 `#86c2c5`, 400 `#68b7bb`, 500 `#4cafb4`,
  600 `#30a7ad`, 700 `#298387`, 800 `#26676a`, 900 `#184446` (Classic 500 `#2ba4ff`, 600 `#0898ff`).
- green 100 `#70d269`, 200 `#65bd5f`, 300 `#57a352`, 400 `#498944`, 500 `#3a7037`, 600 `#2e592b`,
  700 `#22431f`, 800 `#162f14`, 900 `#0f240d` (Classic 100 `#16dd12`).
- red (coral) 100 `#fde3e1`, 200 `#fbcbc8`, 300 `#f9a4a1`, 400 `#f56e6f`, 500 `#bf2a38`,
  600 `#982930`, 700 `#7f2127`, 800 `#6c1a1f`, 900 `#4b1014` (Classic 500 `#d7184b`).
- warning 100 `#fae9d4`, 200 `#f7dab7`, 300 `#f3c490`, 400 `#f0b071`, 500 `#d1603c`, 600 `#c65c3c`,
  700 `#ae5234`, 800 `#8b4129`, 900 `#5d2b1a` (Classic 500 `#e64900`).
- Surface ladder (settings surfaces): `color-surface-ground` `#0f1919`, `color-surface-raised`
  `#1a2424`, `color-surface-control` `#232d2e` (Classic `#111111 #191919 #202020`).
  `color-border-control` `#71797a`, `color-text-help` `#909596`, `color-text-inactive` `#909596`.
  `color-border-hairline` rgba(255,255,255,0.07), `color-border-hairline-strong` rgba(255,255,255,0.12).
- Semantic aliases (unchanged names): `color-bg-primary` gray-900, `color-bg-secondary` gray-800 (app
  ground), `color-bg-tertiary` gray-700, `color-bg-elevated` gray-600 (hover, "on" fills),
  `color-bg-idle` gray-500, `color-surface-hover` gray-700, `color-surface-active` gray-600,
  `color-surface-overlay` rgba(6,6,6,0.75), `color-text-primary` gray-100, `color-text-secondary`
  gray-200, `color-text-muted` gray-400 (body default), `color-text-disabled` gray-500 (disabled
  only), `color-border-primary` gray-500, `color-border-secondary` gray-600, `color-border-muted`
  gray-100 at 10%, `color-info` blue-500, `color-info-strong` blue-600, `color-info-medium` blue-700,
  `color-info-muted` blue-800, `color-info-idle` blue-900, `color-info-surface` blue-500 at 10%,
  `color-success` green-100, `color-success-strong` green-200, `color-success-muted` green-500,
  `color-success-surface` green-100 at 20%, `color-warning` warning-500, `color-warning-strong`
  warning-600, `color-warning-surface` warning-500 at 20%, `color-danger` red-500,
  `color-danger-strong` red-700, `color-danger-surface` red-500 at 20%. Proposed and in tokens.json
  but not in code: `color-danger-text` red-300 and `color-warning-text` warning-300 for words in a
  status colour.
- Hue means status: teal = brand, selected, info, focus; green = live, OK; orange = caution; coral =
  error, destructive, record. Pair every colour with a word or icon.
- Type: Inter only (Google Fonts, opsz 14 to 32). Scale: `title` 13 px / 14 line / 600; `text.bg`
  12 / 17 / 600 with −0.43 px tracking; `text.md` 12 / 14 / 500; `text.sm` 11 / 14 / 500. Markup pairs
  a size class with `.text` (`p.text.md`). Hierarchy by weight and colour, not size. Uppercase with
  0.09 em tracking only for `settings-group-heading`. Monospace (`ui-monospace, Menlo, Consolas`) for
  paths, versions, logs, metrics and identifiers; `font-variant-numeric: tabular-nums` for numbers that
  update.
- Spacing 4 px step via utilities (`space-1` 4, `space-2` 8, `space-3` 12, `space-4` 16, `space-8` 32).
  Settings layout: row min height 30 px, inline padding 14 px, control column 224 px, dependent indent
  18 px, section header 36 px. Controls 25 px tall (`h-25`, `icon-size-25`).
- Radius `br-1` 4 px (buttons, inputs), `br-1-1` 6 px (tracks, selects, toasts), `br-2` 8 px (cards),
  `br-3` 12, `br-pill`. Border width `border-1` is 1.5 px; settings-layout uses 1 px hairlines.
- Shadows only: `shadow-raised-lip` inset 0 1px 0 rgba(255,255,255,0.055), `shadow-raised-low`
  0 1px 2px rgba(0,0,0,0.55), `shadow-raised-high` 0 2px 4px rgba(0,0,0,0.5), 0 14px 32px −18px
  rgba(0,0,0,0.95), `shadow-elevated-sharp` 0 7px 15px rgba(0,0,0,0.5) (tooltips), `shadow-lg`
  0 4px 20px rgba(0,0,0,0.4) (flyouts). Flat otherwise; no gradients.
- Motion: `--speed-0` 50 ms press, `--speed-1` 120 ms hover colour, `--speed-2` 220 ms reveals;
  keyframes `fmcPulse` (live dot), `indeterminateProgress`, `fadeIn`, `slide-up`; reduced motion
  respected.
- States: hover = background to `color-bg-elevated`, text muted → primary; selected = darker
  (`color-bg-primary`) with primary text; on = `color-info-strong` toggle track; disabled = opacity
  0.5 to 0.6; focus = 2 px `color-info-strong` outline.
- Copy: plain, technical, second person; Title Case for section and panel titles, sentence case for
  actions; ellipsis for in-progress; no emoji; strings go through i18n locales.
- Audit findings that bear on this work: the progress toast has a debug magenta border
  (`#FF00FF` in `pipelineProgress.css`); `color-error` is undefined; status greens are fully saturated
  in Classic; surfaces collapse into one plane in Classic; icons bake Classic inks (`#9b9b9b` idle,
  `#0898ff` active) so under Skull they need `currentColor` masks.
- Design-system component cards exist for ButtonCard, ButtonSm, Checkbox, IconButton,
  SegmentedControl, SettingsSection, SidebarNav, ToastNotification, ToggleComponent, Tooltip,
  UpdateBanner (not downloaded; the real components in `freemocap-ui/src/components/ui-components/`
  are the source of truth: `ButtonSm.tsx`, `SegmentedControl.tsx`, `TabbedContent.tsx`,
  `IconButton.tsx`, `ModalWindowControls.tsx`, `ValueSelector.tsx`, `ToggleComponent.tsx`).

## 6. The design (drafted; sections 1 and 2 shown to the user, not yet confirmed)

### 6.1 Modal shell and lifecycle

- A List | Graph segmented control (existing `SegmentedControl`) in the modal's title row; the choice
  is remembered. List view is unchanged.
- A run-wide chip bar above the graph: Recording, Starting data (run + sensor group), Save results,
  Stage range, Pipeline implementation, Tracking device, as `SettingsSummaryChip`s. Clicking a chip
  opens that section in the inspector. These are never nodes.
- Graph view opens the modal at a larger default size and fits the whole graph on first open; the
  existing window controls still move, resize and maximize.
- Three body states: Draft (nodes and chips editable), Launched (immutable copy of the plan that was
  sent, nodes show progress), Finished (same graph as inspection surface for timings, outputs,
  failures; "New draft" returns to editing prefilled from the last draft).
- Process keeps the modal open and flips it to Launched. Closing the modal never affects processing.
  The snackbar remains the compact summary; its run card gains "Show graph", which reopens the modal
  on that run.
- Frontend-only prerequisite: stage range, source run, save mode, pipeline implementation and device
  move from modal-local state into the shared mocap draft so both views build byte-identical requests.

### 6.2 Graph content

- Nodes are the real operations (section 3.4), one per operation id, titled with short plain verbs
  (proposed: Detect poses; Calculate 3D points; Fill gaps and smooth; Orient to reference; Prepare for
  fitting; Fit body dimensions; Reconstruct skeletons; Prepare 2D for saving; Save 2D tracking; Prepare
  3D for saving; Save 3D points; Save recording; Annotate camera N; Load saved 2D tracking; Load saved
  3D points; Load saved body dimensions; Save fitted dimensions; Save requested stages). The backend
  label and the id stay visible in the inspector.
- Five stage bands with the list's names and status vocabulary (Run, Rerun, Reuse saved, Not
  requested). Bands inside the requested range are live; outside they dim, never disappear. Proposed
  membership (backend should own it): band 1 = observation node, observation_request,
  save_observations, annotation branch; band 2 = match_and_triangulate; band 3 = filter_trajectories,
  align_reference, spatial_request, save_spatial; band 4 = reconstruction_input, fit_model_dimensions
  (+ save_model_fits); band 5 = reconstruct_skeletons, save_recording (or stage_result_request +
  save_stage_result for early stops).
- The graph changes with the request exactly as the builders do (variants in 3.4).
- Typed slots: inputs on the left edge, outputs on the right, each labelled with its contract kind
  (monospace identifier). Bindings are not written on edges.
- Disk is drawn, not coloured: folder terminal with rail and direction arrow for every `load_*` and
  `save_*` node; colour stays reserved for status.
- Context outside the compiled graph: a setup strip before the graph (phase `setting_up`, board
  selection, device resolution) and an exports strip after it (`scientific_files`, `tall_csv`,
  `blender`, real operations with progress, no edges).
- Camera lanes inside tracking only when the backend reports per-camera counters (ask).

### 6.3 Configure interaction (outline, not yet presented)

- Click a node → inspector shows title, id, resource, backend label, inputs and outputs with kinds and
  producer nodes, then the existing settings section(s) for that node mounted as-is: observation node
  → Detectors + Tracking device; match_and_triangulate → Camera geometry (calibration chip) +
  Triangulation; filter_trajectories → Post-processing filter rows; align_reference → alignment rows;
  reconstruction_input / fit / reconstruct → skeleton anchor; saves → run destination summary
  (read-only); annotate_camera_N → "Save annotated videos" (graphAnnotate); exports strip → Exports
  and Blender sections. Several nodes referencing one section edit one shared value.
- Stage range stays a run-wide control; the graph reflects it. No wire editing, no per-node rerun,
  no pause, no step.
- Edits update the shared draft; a server-side preview, when it exists, re-resolves the graph; stale
  previews are rejected.

### 6.4 Run view (outline, not yet presented)

- Operation ids equal node ids: paint each node from its `TaskOperation` (status, fraction, count +
  unit, elapsed, ms per motion frame, detail). Unknown totals are indeterminate; never invent a
  percentage. Blocked nodes show "Cannot run because required work failed" with the prerequisite
  names. Cancelled nodes show "Stopped before starting".
- Task-level: phase and detail in the setup strip until the first operation reports; `timing` in a
  run summary (elapsed, motion frames, ms per motion-capture frame). Concurrent node durations are
  never summed into run time.
- Exports strip rows render like `OperationProgressBars` rows.
- Finished state: per-node elapsed, outputs (file paths once the backend reports artifacts), failures
  with detail; Open folder and Load in playback as today.
- Fixture rule: any progress shown in mockups is labelled "Illustrative fixture, not a recorded run".

### 6.5 Visual language mapping from the lab to FreeMoCap tokens (outline)

- Canvas ground `color-bg-primary` with a subtle dot grid in `color-border-muted`; node body
  `color-surface-raised` with `color-border-hairline-strong`, header text `text.md` 600, slot type in
  monospace `text.sm`; selected node `color-info` stroke; running `color-info` stroke + bar; complete
  `color-success` icon and stroke; failed or blocked `color-danger`; waiting `color-text-inactive`;
  edges `color-border-primary`, lit edges `color-info`; annotation branch dashed; disk folder in
  `color-text-muted` with `color-info-surface` fill, arrow says direction. Inspector uses the
  settings-layout ladder. Modal chrome unchanged.

## 7. Asks for the integration agent (backend), to hand over as a list

1. A plan-preview route that returns the resolved `GraphDefinition` (nodes, typed ports, edges,
   topological order) plus a stable plan identity for a given `PosthocMocapPipelineConfig` and
   recording, without loading inference, building handlers or reserving a run. Must also return
   stage membership per node, which nodes are setup or export context, and validation messages.
2. Plan identity and node-to-stage membership on every task snapshot, so a running task resolves its
   own executed plan rather than the draft being edited.
3. Per-camera counters inside `load_and_track` (camera id, completed, total, unit) if camera lanes are
   wanted; otherwise keep the single counter.
4. Artifact paths per save node and per export (file names and folders) in the finished snapshot, so
   disk terminals can list what was written.
5. Keep operation ids equal to node ids (already true) and document it as a contract.

Frontend-only changes (no backend): shared draft state for stage and run choices; modal stays open on
Process; snackbar "Show graph"; graph view component; `color-error` → `color-danger` cleanup and the
magenta toast border removal while touching the progress styles.

## 8. Mockup deliverables for the design session

1. List view as it exists (reference frame): nav + eight sections with summary chips, footer.
2. Graph view, Draft state, full run, left-to-right: run-wide chip bar, five stage bands, all nodes
   from 3.4, annotation branch for three cameras, disk terminals, setup and exports strips, inspector
   open on Detect poses with the real Detectors rows.
3. Node anatomy spec: sizes, slot dots, type labels, state icons, progress bar, disk terminal, zoom
   level-of-detail rules.
4. Draft state with stage range 3 to 5 from a saved run (bands 1 and 2 as "Reuse saved", the saved-3D
   graph) and a new-run save mode chip.
5. Launched state mid-run: tracking at a partial count in camera images, one annotate node running,
   downstream waiting, setup strip collapsed, snackbar visible with "Show graph".
6. Finished state complete: per-node elapsed, exports strip complete with channel counts, run summary.
7. Failed state: reconstruct_skeletons failed, save_recording blocked with the prerequisite named,
   exports not started, inspector showing the failure detail.
8. Top-down orientation variant and a narrow-width variant (modal at its minimum 600 × 420).
9. A token mapping sheet (lab vocabulary → FreeMoCap semantic tokens) and the Skull swatches used.

## 9. Open questions for the user

- Should bands be selectable on the graph as a shortcut to the stage range, or stay read-only with the
  chip bar as the only control? (Handoff says run-wide choices belong above the graph.)
- Default modal size in graph view: auto-maximize, or a larger fixed default?
- Should the legacy pipeline (`pipelineImplementation: current`) hide the Graph switch or show it
  disabled with a note?
- Per-type slot colour families (a few hues) versus neutral dots with type text only.
