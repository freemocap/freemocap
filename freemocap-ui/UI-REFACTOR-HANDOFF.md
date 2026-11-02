# UI refactor handoff

Branch `sfn26-ui-refactor`, checkout `project/repos/freemocap-ui-refactor`.
Each commit that changes the UI gets a section here: what changed, what to run,
what to look at. Test reports go to `.test-artifacts/reports/<short-hash>.md`
in this checkout (ignored by git).

Pushes: commits land locally first; the owner or the local test agent pushes.

## Plan

- [x] **1.** Port the Skull colour, icon and progress-colour edits onto the current `sfn26-ui-refactor` files and commit them after checking that every image file is free of the signed block.
- [x] **2.** Write `freemocap-ui/UI-REFACTOR-HANDOFF.md`, saying what each commit changed and what the local agent should run against it, and commit it.
- [ ] **3.** Inventory the current `freemocap-ui` screens against the FreeMoCap UI design system and publish the mismatch list as a board on the design canvas.
- [ ] **4.** Redesign the Mocap processing modal's list view on the canvas from that inventory and implement the approved version in `mocap-setup-modal.tsx` and its settings sections.
- [ ] **5.** Move the stage range, starting run, save mode, pipeline and tracking device from modal-local state into the shared mocap store so both views build the same request.
- [ ] **6.** Add a backend plan-preview route that returns the real graph definition for a given processing request.
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
