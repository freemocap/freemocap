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
- [ ] **3.** Inventory the current `freemocap-ui` screens against the FreeMoCap UI design system and publish the mismatch list as a board on the design canvas.
- [ ] **4.** Redesign the Mocap processing modal's list view on the canvas from that inventory and implement the approved version in `mocap-setup-modal.tsx` and its settings sections.
- [ ] **5.** Move the "Processing stages" choices (start stage, stop stage, saved run to start from, overwrite or keep that run) from `MocapStageSelection` component state into the shared mocap Redux store, so the list view and the graph view read and edit the same values.
- [ ] **6.** Backend work in "Backend asks" below, built by the local agent; this branch reviews it and consumes it.
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
