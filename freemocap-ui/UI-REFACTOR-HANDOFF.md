# UI refactor handoff

Branch `sfn26-ui-refactor`, checkout `project/repos/freemocap-ui-refactor`.
Each commit that changes the UI gets a section here: what changed, what to run,
what to look at. Test reports go to `.test-artifacts/reports/<short-hash>.md`
in this checkout (ignored by git).

Pushes: commits land locally first; the owner or the local test agent pushes.

## Pushing

The local agent pushes `sfn26-ui-refactor` to origin: after picking up new commits on this branch,
run `git push origin sfn26-ui-refactor` (set upstream on the first push). The design side commits
from an environment without GitHub credentials and cannot push. The owner does not push.

## Plan

- [x] **1.** Port the Skull colour, icon and progress-colour edits onto the current `sfn26-ui-refactor` files and commit them after checking that every image file is free of the signed block.
- [x] **2.** Write `freemocap-ui/UI-REFACTOR-HANDOFF.md`, saying what each commit changed and what the local agent should run against it, and commit it.
- [x] **3.** Inventory the current `freemocap-ui` screens against the FreeMoCap UI design system and publish the mismatch list as a board on the design canvas.
- [x] **4.** Redesign the Mocap processing modal's list view on the canvas from that inventory and implement the approved version in `mocap-setup-modal.tsx` and its settings sections.
- [x] **5.** Move the "Processing stages" choices (start stage, stop stage, saved run to start from, overwrite or keep that run) from `MocapStageSelection` component state into the shared mocap Redux store, so the list view and the graph view read and edit the same values.
- [x] **6.** Backend work in "Backend asks" below, built by the local agent; this branch reviews it and consumes it.
- [ ] **7.** Implement the Graph view in the playback Mocap processing modal by porting the Graph Lab renderer and inspector to React/TypeScript.
- [ ] **8.** Connect live operation progress from task snapshots to the Graph view nodes by operation id.
- [ ] **9.** Merge the latest `sfn26` into `sfn26-ui-refactor`, resolve conflicts, and hand the branch off for the merge back.

## 52b97572 Apply the Skull theme colours, theme-aware icons and danger tokens

What changed (freemocap-ui/src only):
- `styles/color.css`: gray, green, red, warning and blue ramps, their alpha tints,
  the surface ladder, `--color-border-control`, `--color-text-help`,
  `--color-text-inactive` and `--color-icon-idle` now use the Skull values from
  `design-system/tokens.json`. Added `--color-danger-text`, `--color-warning-text`,
  `--color-icon-dim`. Semantic token names are unchanged.
- `styles/icons.css`: dropdown arrows, subcategory, import and import-videos icons
  are masks filled with icon tokens. `--import-icon` and `--importVideos-icon` point
  to the real files with exact case (`import_icon.svg`, `importvideos_icon.svg`).
- Seven multi-ink SVGs recoloured to Skull values, including glow colour matrices:
  calibrating, connected, live_active, loader, stream, streaming, updateAvailable.
- Undefined `--color-error` replaced with `--color-danger` (fills, borders) or
  `--color-danger-text` (words) in pipelineProgress.css, transform-editor.css,
  OperationProgressBars.tsx, PipelineGroupCard.tsx, PipelineProgressBar.tsx,
  ZoomableVideoTile.tsx. The magenta debug border on the running progress toast
  is now `--color-info`.

Run:
- Full UI typecheck and the Playwright e2e suite. Expect no new failures.
  (A cloud copy without the built `@freemocap/client` package showed the same
  276 type errors before and after this commit.)
- The icon URL and undefined-CSS-variable checks, once the harness has them.
- Visual regression against the pre-refactor baseline: every screen changes colour;
  flag layout changes, unreadable text, and icons that render blank.

Look at: connection/streaming indicators, dropdown arrows, the import buttons,
the calibrating animation, a failed pipeline card, the running progress toast.

Known and left as is: the right-hand skeleton colour `#FF00FF` in
`viewport3d/helpers/skeleton-colors.ts` is deliberate data colouring.
Undefined tokens still in use elsewhere: `--color-bg-darker`
(calibration-module.css), `--color-text-tertiary` (log-terminal.css),
`--color-border` (tutorial.css).

## 086f7a70 Give primary, secondary and record buttons their own colour roles

- `styles/color.css`: new tokens `--color-primary-fill` (teal `--color-info-strong`), `--color-primary-fill-hover`,
  `--color-on-primary` (dark label, 6.2:1), `--color-record-dot` (`--red-400`), `--color-record-fill` (#a8473f, light
  label 4.55:1) and `--color-record-fill-dim` for the recording pulse.
- `styles/button-sm.css`: `.accent` is the primary role (teal fill, dark label and icon); `.secondary` and
  `.button.accent-outline` use the surface-control fill with the control border.
- `styles/camera.css` and `StartStopRecordingButton.tsx`: the idle record button is a secondary button with a red
  dot; only an active recording fills with the record colour.

Run: typecheck, unit and E2E suites, visual and contrast checks. Look at: welcome and tour buttons, Open Mocap
Processing, Process Mocap and Save in the mocap modal, Calibrate from active recording, Connect Cameras, Set up
calibration, Start Recording idle and while recording (the recording state needs the server), Stop Mocap
Recording in the mocap task panel. Contrast checks should now pass for these buttons.

## Processing stages colours and custom pipeline label

- Processing stages keeps its checkboxes and selection rules. Ticks use `--color-info-strong`; a running stage's
  rail is teal; "Run" and "Rerun" use the new `active` summary-chip tone (`--color-info-text`, `--blue-300`);
  "Removed after save" uses the new `caution` tone (`--color-warning-text`). Green stays for live/OK only.
- The pipeline dropdown's disabled entry reads "Select custom pipeline…" with the "Coming soon" tooltip.
  `processing-pipeline-select.spec.ts` and `mocap-graph-settings.spec.ts` follow the new name.

Run: E2E suite (both specs above and `staged-processing.spec.ts`), visual and contrast checks. Look at: Processing
stages with all stages running, with a saved run and a later start, and with an early finish over saved stages.

## Exports section on the settings rows

- `mocap-export-settings.tsx`: Data, Formats and Run now are settings groups; every data type and format is a row
  with an info button and a switch (`role="switch"`), followed by "Export selected formats after processing".
  "Export saved Run N" and "Saved results" rows hold the Export saved result and Reload saved results buttons.
  Status, alerts and the completed-export note keep their text. `export-settings.css` is deleted.
- `settings-layout.css`: `.settings-disclosure` gives Tall CSV and Blender's advanced package diagnostics the section
  chevron; `.settings-note-error` uses `--color-danger-text`.
- `e2e/recording-exports.spec.ts`: selects switches by role and loads the app stylesheet so switches are visible.

Run: `recording-exports.spec.ts` (3 cases), `tall-csv-export.spec.ts`, `blender-package.spec.ts`, then the full E2E,
visual and contrast checks. Look at: Exports with no saved result, with a saved run, during an export (Cancel export
row), after a completed export, with unavailable data selected; Blender's advanced diagnostics disclosure.

## a13aded1 Merge the processing plan backend; stage choices in shared state

- `a13aded1` merges `89224110` from `sfn26-ui-harness` (plan preview route, node stage and effects, operations
  initialised from the plan, plan on snapshots, files read and written). Backend asks 1–5 are in this branch.
- `store/slices/processing-stages/`: the Processing stages choices (saved run and sensor group, save mode, start and
  stop) and the saved-stage inventory live in Redux. `selectStageSelection`, `selectSourceRunId` and
  `selectStageRows` (per-stage outcome) are what the list and graph views read. Selection rules are unchanged.
- `MocapStageSelection` takes only `path`; the mocap modal reads the selection from the store.
- `staged-processing.spec.ts` renders the component inside the store provider.

Run: full E2E (especially `staged-processing`, `mocap-config-request`, the frozen modal request), unit and pipeline
suites, and the backend tests from `89224110` on this branch.

## Backend asks (local agent builds; UI branch reviews and consumes)

Current-code facts the UI relies on: `experiments/executable_graph_lab/production_view/DESIGN-SESSION-HANDOFF.md` section 0.
DLC is out of scope for this work; keep its current behaviour intact and do not plan around it.

The graph is a data flow from sources to sinks. A source is where data enters: a live source
(camera) or a record (video files, a saved calibration, saved results). A sink is where data ends:
written to disk, or sent for display. Every node that reads from or writes to disk, or sends for
display, must say so explicitly; the UI must never infer it from a node name.

1. **Planned graph before launch.** A route that takes a recording and a `PosthocMocapPipelineConfig`
   and returns the graph the backend would run: nodes, typed ports, edges, each node's stage, and
   validation errors. It must not start work, load models or reserve a run. Today the builders in
   `recording_pipeline.py` and `saved_spatial_pipeline.py` load the calibration and construct the
   workers while building, so the topology needs to be buildable on its own.
2. **Every operation known at launch.** When a mocap task starts, its snapshot lists every node of
   the graph as an operation with status `waiting`, in graph order, so the progress panel and the
   graph can lay out all progress bars before any work runs. A waiting node also reports which
   upstream nodes it is waiting for.
3. **Sources and sinks on each node.** Each node declares whether it is a source (live or record)
   or a sink (disk or display), and disk nodes report the files they read or wrote, in the
   snapshot when finished.
4. **Plan identity on snapshots.** The snapshot carries an identity for the plan it is running and
   each node's stage, so a running task is drawn from its own plan, not from the settings being edited.
5. **Operation id equals node id.** True in code today; state it as the contract in the code that builds operations.
6. **RTMPose confidence default.** The UI default is 0.004 (`mocap-slice.ts`), the backend default is
   0.4 (`mocap_task_config.py`). Check which value works on the reference recordings and report it;
   the UI will use that value.

## Screenshot request for plan step 3 (local agent)

The design side cannot run the backend (the camera library build downloads from a GitHub repo it
cannot reach). Capture the real app on the Mac at the current branch head with the backend running
and `freemocap_sample_data` available.

- Window or viewport 1600 × 1000, default theme. Also capture items 1, 3 and 6 in the light theme if
  the app has one.
- Save as PNG to `.test-artifacts/ui-inventory/NN-name.png` (ignored folder; the design side reads it
  directly). Add `.test-artifacts/ui-inventory/index.md` listing the commit, each file and what state it shows.
- Do not commit the images.

Screens without data are covered: the design side uses the surface and mocap-section captures from
your visual runs plus its own renders of the welcome, tour, menus and dialogs. Still needed, with the
server running and `freemocap_sample_data` loaded:

1. Playback with `freemocap_sample_data` loaded: videos, 3D view and timeline visible.
2. Recording browser with recordings listed.
3. A full mocap run on the sample data: progress panel and snackbar just after launch, during
   tracking, during reconstruction, and complete.
4. A failed run (for example, a missing calibration file) showing the failure in the progress panel.
5. Log terminal open with server output, and the settings modal.
