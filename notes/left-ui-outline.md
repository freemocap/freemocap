Outline for the realtime left UI 

Each part is a checkbox with collapsible tree veiew for the parameters underneath it. 
Sections are closed by default, and the user can click to expand them.
When it makes sense the collapsed header should show a summary of the settings, similar to the camera config panel.
Anything that can be disabled should offer at tooltip explaining WHY it is disabled

#  > Real time Pipeline 
This is a turn-on/turn-off-able long running pipeline that processes images from the cameras (2d tracking) and optionally combines the 2d views to do 3d keypoint triangulation and skeleton reconstruction (using pipelines expecting incoming data streams vs the completed post-hoc piplines in the other setction) 
- [ ] 2d Tracking
  - [ ] Charuco (w/ settings collapsed by default)
  - [ ] Skeleton ( w/ mediapipe settings collapsed by default. use Realtime preset)
- [ ] 3d Reconstruction
  - [ ] Triangulate (w/ settings, just use plaecholders for now. Also include a picker for the caliberation toml we should use for the triangulation. Follow conventions currently in the Calibration panel)
  - [ ] Filter (showing parameters for filtering, Fabrik, One Euro etc)
  - [ ] Skeleton (showing paramters for skeleton, such a rigid body stuff, etc)

# > Cameras
- For camera controls. Current form is pretty good! 

# > Recording
- For recording videos
- Current form is pretty good, BUT shoudl include something to allow users target calibration or mocap videos (i.e. some top level option to target videos as 'calibration' or 'mocap' videos, to be auto-processed with the currently specified post-hoc calbration, mocap (or both) posthoc pipeline. I guess it should show a checkbox for each pipeline we should put the resulting recording through. This feature should have the same effects as the 'record calibration videos' and 'record mocap videos' buttons in the assocaited post-processing pipeline
- 
# > Post Processing Pipeline(s) (post hoc pipelines)
This panel is to trigger more fire-and-forget style pipelines to processing calibration or mocap videosets. It creates similarly structured pipelines to the realtime pipeline (camera/video nodes feeding into an aggregation node), but rather than operating on the basis of incoming data, these are for pre-recorded datasets. Eventually this will be part of a batch processing method that spawn multiple processing pipelines. we should have some sense of a progress reporting component showing the progress of a triggered pipeline (tagged by pipeline id returned from the endpoint)    
- > Capture Volume Calibration
  - Similar to the current Calibration panel. 
  - Folder status checker should have a watcher that checkes the selected directory ever few seconds, rather than requiring manual re-checks to get updates
  - 
- > Motion Capture
  - Form should copy similar structures to the realtime pipeline, but can hold different values. Default settings are Posthoc
  - Must have the concept of a 'recording id' baked in at a high level. The recording id is the same as the recording name is the same as the name of the recording folder
  - Calibration toml selector is a good idea, but ugly and clunky and not self-explaining. Way too many top level settings, should have heirarcical nested settings (similar in structure to the realtime pipeline, but there will be different options, e.g. butterworth filtering options that cant be done on a realtime stream bc they require the full data set avbailable)  
  - Process selected recording should be a the TOP not the bottom

---

# Implementation Plan

Phased plan to implement the above changes. Phases 2 and 3 can be done in parallel after Phase 1.

## Phase 1: Shared Pipeline Config Components (Foundation)

Create reusable tree components consumed by both realtime and posthoc pipelines.

### New directory: `freemocap-ui/src/components/pipeline-config/`

#### 1.1 `PipelineStageTreeItem.tsx`
A generic checkbox + collapsible tree node. Follows the pattern in `camera-config-tree-view/CameraTreeItem.tsx`.

```
Props:
  label: string
  checked: boolean
  onToggle: (checked: boolean) => void
  disabled?: boolean
  disabledReason?: string        // tooltip shown when disabled
  summaryWhenCollapsed?: string   // shown in header when collapsed
  children: ReactNode             // settings content
```

Uses MUI X `TreeItem` with a custom content slot containing the checkbox. When `disabled`, wraps in a `Tooltip` with `disabledReason` explaining WHY (per outline requirement).

#### 1.2 `PipelineConfigTree.tsx`
Renders the hierarchical pipeline structure using `SimpleTreeView` + `PipelineStageTreeItem`:

```
Props:
  context: "realtime" | "posthoc"
  detectorConfig: MediapipeDetectorConfig   // from settings-types.ts
  filterConfig: SkeletonFilterConfig
  onDetectorChange: (patch: Partial<MediapipeDetectorConfig>) => void
  onFilterChange: (patch: Partial<SkeletonFilterConfig>) => void
  calibrationTomlPath?: string
  onCalibrationTomlChange?: (path: string) => void
  // Per-stage enable/disable:
  charucoEnabled: boolean
  onCharucoToggle: (v: boolean) => void
  skeletonEnabled: boolean
  onSkeletonToggle: (v: boolean) => void
  triangulateEnabled: boolean
  onTriangulateToggle: (v: boolean) => void
  filterEnabled: boolean
  onFilterToggle: (v: boolean) => void
  rigidBodyEnabled: boolean
  onRigidBodyToggle: (v: boolean) => void
```

Tree structure:
```
[ ] 2D Tracking
  [ ] Charuco — board size params (extracted from CalibrationControlPanel.tsx lines 484-520)
  [ ] Skeleton — MediapipeConfigPanel (default preset: Realtime if context="realtime", Posthoc if context="posthoc")
[ ] 3D Reconstruction
  [ ] Triangulate — CalibrationTomlPicker + placeholder settings
  [ ] Filter — SkeletonFilterConfigPanel (show butterworth section only when context="posthoc")
  [ ] Skeleton — rigid body params (placeholder UI for now)
```

When collapsed, each section header shows a summary of its settings (e.g. "MediaPipe Heavy, conf 0.5" or "One Euro β=0.5, FABRIK 50 iters").

#### 1.3 `CalibrationTomlPicker.tsx`
Redesigned from `MocapTaskTreeItem.tsx` lines 401-452. Current version is described as "ugly and clunky."

New design — single compact row:
```
[StatusIcon] [Source label] [Truncated path (monospace)] [Browse button]
```

Source labels: "Auto-detected", "From calibration panel", "Manually selected"

```
Props:
  tomlPath: string | null
  source: "auto" | "calibration-panel" | "manual"
  onSelect: (path: string) => void
  onUseAutoDetected: () => void
```

Uses `useElectronIPC().openFileDialog()` for the Browse button.

### Files to create:
- `freemocap-ui/src/components/pipeline-config/PipelineStageTreeItem.tsx`
- `freemocap-ui/src/components/pipeline-config/PipelineConfigTree.tsx`
- `freemocap-ui/src/components/pipeline-config/CalibrationTomlPicker.tsx`

---

## Phase 2: Restructure Realtime Pipeline Panel

### 2.1 Rewrite `ProcessingPipelinePanel.tsx`
**File:** `freemocap-ui/src/components/processing-pipeline-panel/ProcessingPipelinePanel.tsx`

Replace the flat `FormControlLabel` switches (lines ~56-112) and embedded `MediapipeConfigPanel` / `SkeletonFilterConfigPanel` with:
```tsx
<PipelineConfigTree
  context="realtime"
  detectorConfig={backendPipeline.mediapipeDetectorConfig}
  filterConfig={backendPipeline.skeletonFilterConfig}
  onDetectorChange={(patch) => sendSettingsPatch('pipeline.detector', patch)}
  onFilterChange={(patch) => sendSettingsPatch('pipeline.filter', patch)}
  charucoEnabled={backendPipeline.calibration_detection_enabled}
  onCharucoToggle={(v) => sendSettingsPatch('pipeline.calibration_detection_enabled', v)}
  skeletonEnabled={backendPipeline.mocap_detection_enabled}
  onSkeletonToggle={(v) => sendSettingsPatch('pipeline.mocap_detection_enabled', v)}
  // 3D toggles — local state until backend support added:
  triangulateEnabled={localTriangulate}
  onTriangulateToggle={setLocalTriangulate}
  ...
/>
```

Keep `PipelineConnectionToggle`, `PipelineSummary`, and `PipelineConnectionStatus` unchanged.

### Files to modify:
- `freemocap-ui/src/components/processing-pipeline-panel/ProcessingPipelinePanel.tsx`

---

## Phase 3: Merge Calibration + MoCap into Post Processing Panel

### 3.1 Create `useDirectoryWatcher.ts`
**File:** `freemocap-ui/src/hooks/useDirectoryWatcher.ts`

```
Hook: useDirectoryWatcher(path: string | null, validateFn: () => Promise<void>, intervalMs = 3000)
Returns: { isWatching: boolean, lastChecked: Date | null, triggerRefresh: () => void }
```

Runs `setInterval` calling `validateFn()` when `path` is truthy. Cleans up on unmount or path change. Replaces the manual "click refresh to check folder status" pattern in `CalibrationControlPanel.tsx` (lines 174-183) and `MocapTaskTreeItem.tsx`.

### 3.2 Create `CalibrationSubsection.tsx`
**File:** `freemocap-ui/src/components/post-processing-panel/CalibrationSubsection.tsx`

Migrate from `CalibrationControlPanel.tsx` (589 lines) with these changes:
- Wrap in a collapsible `Accordion` or nested tree item (not a top-level `CollapsibleSidebarSection`)
- Use `useDirectoryWatcher` for automatic folder status polling (keep manual refresh as override)
- All existing functionality preserved: board config, solver section (`CalibrationSolverSection.tsx`), recording controls, path input, `DirectoryStatusPanel`, calibrate button

### 3.3 Create `MocapSubsection.tsx`
**File:** `freemocap-ui/src/components/post-processing-panel/MocapSubsection.tsx`

Migrate from `MocapTaskTreeItem.tsx` (506 lines) with these changes:
- **"Process Selected Recording" button at TOP** (currently at bottom, line ~492)
- Recording path/ID selector at top level — `recording_id` concept baked in prominently
- Replace flat `MediapipeConfigPanel` + `SkeletonFilterConfigPanel` with `<PipelineConfigTree context="posthoc" />`
- Use redesigned `CalibrationTomlPicker` from Phase 1
- Use `useDirectoryWatcher` for auto-refresh
- Hierarchical nesting for all settings (no more flat top-level params)

### 3.4 Create `PostProcessingPanel.tsx`
**File:** `freemocap-ui/src/components/post-processing-panel/PostProcessingPanel.tsx`

Single `CollapsibleSidebarSection` titled "Post Processing Pipeline(s)" containing:
```
> Capture Volume Calibration — CalibrationSubsection
> Motion Capture — MocapSubsection
```

Both subsections closed by default. Each subsection header shows a summary chip when collapsed.

### 3.5 Update `LeftSidePanelContent.tsx`
**File:** `freemocap-ui/src/components/ui-components/LeftSidePanelContent.tsx`

- Change `DEFAULT_SECTION_ORDER` from `['connection', 'cameras', 'recording', 'pipeline', 'calibration', 'mocap']` to `['connection', 'cameras', 'recording', 'pipeline', 'postprocessing']`
- Add `postprocessing` entry in `SECTION_COMPONENTS` mapping to `PostProcessingPanel`
- Remove `calibration` and `mocap` entries
- The existing `loadSectionOrder()` validation (lines ~57-75) already resets to defaults when stored IDs don't match, so localStorage migration happens automatically

### Files to create:
- `freemocap-ui/src/hooks/useDirectoryWatcher.ts`
- `freemocap-ui/src/components/post-processing-panel/PostProcessingPanel.tsx`
- `freemocap-ui/src/components/post-processing-panel/CalibrationSubsection.tsx`
- `freemocap-ui/src/components/post-processing-panel/MocapSubsection.tsx`

### Files to modify:
- `freemocap-ui/src/components/ui-components/LeftSidePanelContent.tsx`

---

## Phase 4: Recording Panel — Pipeline Tagging

### 4.1 Add recording tag state
**File:** Recording Redux slice (locate via `freemocap-ui/src/store/slices/recording/`)

Add to state:
```ts
runCalibrationPipeline: boolean  // default false
runMocapPipeline: boolean        // default false
```

Add reducers: `setRunCalibrationPipeline`, `setRunMocapPipeline`

### 4.2 Update `RecordingInfoPanel.tsx`
**File:** `freemocap-ui/src/components/recording-info-panel/RecordingInfoPanel.tsx`

Add a "Post-recording pipelines" section (after recording settings, before or after MicrophoneSelector):
```
[ ] Run Calibration Pipeline after recording
[ ] Run MoCap Pipeline after recording
```

These checkboxes mirror the "record calibration videos" / "record mocap videos" buttons in the calibration/mocap panels. When checked, stopping a recording auto-triggers the corresponding post-hoc pipeline.

### 4.3 Wire stop-recording to pipeline dispatch
**File:** `freemocap-ui/src/components/recording-info-panel/RecordingCompleteDialog.tsx` (or the stop recording handler)

On recording stop, if `runCalibrationPipeline` is true, dispatch the calibration processing action with the completed recording path. Same for `runMocapPipeline`.

### Files to modify:
- Recording Redux slice
- `freemocap-ui/src/components/recording-info-panel/RecordingInfoPanel.tsx`
- `freemocap-ui/src/components/recording-info-panel/RecordingCompleteDialog.tsx`

---

## Phase 5: Polish & Context-Aware Config

### 5.1 Context-aware `MediapipeConfigPanel.tsx`
**File:** `freemocap-ui/src/components/mocap-control-panel/MediapipeConfigPanel.tsx`

Add prop: `defaultPreset?: "realtime" | "posthoc"` — controls which preset chip is selected by default. Currently hardcoded.

### 5.2 Context-aware `SkeletonFilterConfigPanel.tsx`
**File:** `freemocap-ui/src/components/mocap-control-panel/SkeletonFilterConfigPanel.tsx`

Add prop: `context?: "realtime" | "posthoc"`. When `context === "posthoc"`, show additional **Butterworth filter** section (low-pass filter params that require the full dataset — not available in realtime).

### 5.3 Disabled-state tooltips
Audit all checkboxes/toggles across the new components. Anywhere something can be disabled (e.g., 3D Reconstruction disabled when pipeline not connected, smooth segmentation disabled when segmentation off), add a `Tooltip` with `disabledReason` explaining WHY it's disabled.

### 5.4 Collapsed summary headers
Ensure every collapsible section shows a meaningful summary when collapsed:
- 2D Tracking: "Charuco + MediaPipe Heavy"
- 3D Reconstruction: "Triangulate + One Euro + FABRIK"
- Calibration subsection: "Calibrated" / "No calibration"
- MoCap subsection: "Ready" / "Processing 45%"

### 5.5 Cleanup
- Remove unused imports from `LeftSidePanelContent.tsx`
- Verify drag-reorder works with 5 sections instead of 6
- Run `npm run build` to catch type errors
- Manual test: expand/collapse all sections, check summaries, check tooltips

---

## Dependency Graph

```
Phase 1 (Foundation)
  ├──> Phase 2 (Realtime Pipeline)  ──┐
  └──> Phase 3 (Post Processing)  ────┼──> Phase 5 (Polish)
                └──> Phase 4 (Recording Tagging)
```

## Files Summary

### New files (10):
- `freemocap-ui/src/components/pipeline-config/PipelineStageTreeItem.tsx`
- `freemocap-ui/src/components/pipeline-config/PipelineConfigTree.tsx`
- `freemocap-ui/src/components/pipeline-config/CalibrationTomlPicker.tsx`
- `freemocap-ui/src/components/post-processing-panel/PostProcessingPanel.tsx`
- `freemocap-ui/src/components/post-processing-panel/CalibrationSubsection.tsx`
- `freemocap-ui/src/components/post-processing-panel/MocapSubsection.tsx`
- `freemocap-ui/src/hooks/useDirectoryWatcher.ts`

### Modified files (7):
- `freemocap-ui/src/components/processing-pipeline-panel/ProcessingPipelinePanel.tsx`
- `freemocap-ui/src/components/ui-components/LeftSidePanelContent.tsx`
- `freemocap-ui/src/components/mocap-control-panel/MediapipeConfigPanel.tsx`
- `freemocap-ui/src/components/mocap-control-panel/SkeletonFilterConfigPanel.tsx`
- `freemocap-ui/src/components/recording-info-panel/RecordingInfoPanel.tsx`
- `freemocap-ui/src/components/recording-info-panel/RecordingCompleteDialog.tsx`
- Recording Redux slice (path TBD)

---

# Progress Log

## Phase 1: Shared Pipeline Config Components — COMPLETE
- [x] `PipelineStageTreeItem.tsx` — generic checkbox + collapsible tree node with disabled tooltip support
- [x] `PipelineConfigTree.tsx` — hierarchical 2D Tracking / 3D Reconstruction tree using the stage items, embeds MediapipeConfigPanel and SkeletonFilterConfigPanel
- [x] `CalibrationTomlPicker.tsx` — compact single-row redesign (status icon + source label + truncated path + browse button)
- All three files created in `freemocap-ui/src/components/pipeline-config/`
- TypeScript compiles clean (no errors)

## Phase 2: Restructure Realtime Pipeline Panel — COMPLETE
- [x] Rewrote `ProcessingPipelinePanel.tsx` — replaced flat FormControlLabel switches + embedded MediapipeConfigPanel/SkeletonFilterConfigPanel with `PipelineConfigTree context="realtime"`
- 2D toggles (Charuco/Skeleton) wired to backend via `settings/patch` WebSocket messages
- 3D toggles (Triangulate/Filter/Skeleton) use local state until backend support added
- Disabled state + tooltip reason passed through when pipeline not connected
- TypeScript compiles clean

## Phase 3: Merge Calibration + MoCap into Post Processing Panel — COMPLETE
- [x] `useDirectoryWatcher.ts` — polls directory validation on interval (3s default), replaces manual refresh
- [x] `CalibrationSubsection.tsx` — migrated from CalibrationControlPanel into Accordion, uses useDirectoryWatcher
- [x] `MocapSubsection.tsx` — migrated from MocapTaskTreeItem with key changes:
  - Process button moved to TOP
  - Recording ID displayed prominently
  - CalibrationTomlPicker replaces old ugly two-button layout
  - PipelineConfigTree replaces flat MediapipeConfigPanel + SkeletonFilterConfigPanel
  - useDirectoryWatcher for auto-refresh
- [x] `PostProcessingPanel.tsx` — CollapsibleSidebarSection wrapping both subsections
- [x] `LeftSidePanelContent.tsx` — updated to 5 sections (removed calibration + mocap, added postprocessing)
- TypeScript compiles clean

## Phase 4: Recording Panel — Pipeline Tagging — NOT STARTED
## Phase 5: Polish — NOT STARTED
