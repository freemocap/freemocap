# Integration status â€” 2026-10-12

## Isolation

Core: `project/repos/typed-dataflow`, branch `typed-dataflow`, existing unstaged work.
SkellyForge: `project/repos/skellyforge-worktrees/typed-dataflow`, branch
`typed-dataflow`, created at 0ede33e0a6e323dcd4f4b9de2e1b4fc9eff5e41d by explicit
owner request. Both SkellyForge worktrees are clean. No dependency source edits
needed moving: math changes were diagnostic in-process function replacements.
The core environment still imports the original installed SkellyForge; creating
a worktree does not update that dependency. No dependency installation occurred.

## Application integration

The experimental recording graph is now selectable in the main application's
Mocap processing settings. The current implementation remains the default.
Both frontend and backend must run from this worktree; an already-running older
application does not acquire these changes automatically.

1. Open a recording in playback and open its Mocap processing settings.
2. Under Processing stages, choose Processing pipeline: Experimental typed graph.
3. Start at 2D tracking; provide an existing camera calibration. If ChArUco is
   enabled, use Automatic for supported 5x3/7x5 layouts or select an explicit board.
   Automatic preserves the configured square length; it does not infer physical size. Use CPU/Automatic for MediaPipe; RTMPose
   supports the Automatic, CPU and CUDA GPU choices.
4. Process Mocap. Existing task progress and stop controls operate on the graph.

The existing HTTP process route and managed task own recording access, cancellation
and completion. The existing WebSocket sends task snapshots. Display connections
are not execution prerequisites. A fresh per-run calibration copy prevents alignment
from modifying the selected original or reusing a previously aligned copy.

Implementation entry points:
- `freemocap/core/pipeline/dataflow/application_pipeline.py`: application adapter,
  validation, progress, calibration isolation, existing export completion handler.
- `freemocap/core/pipeline/posthoc/mocap_pipeline.py`: implementation dispatch.
- `freemocap/core/pipeline/posthoc/posthoc_pipeline_manager.py`: preflight validation.
- `freemocap-ui/src/components/mocap-setup/mocap-setup-modal.tsx`: pipeline/device controls.

## Validation on 2026-10-12

33 focused unittest checks passed: application routing/export ownership/calibration
isolation, recording graph/executor, streaming tracker adapter, video sources and
annotation worker lifecycle. No dependencies were installed.

Two real application-path acceptance runs used the full 222-motion-frame,
three-camera test recording, CUDA RTMPose and explicit ChArUco. Filtering was disabled
for the test recording's 6 FPS; optional scientific exports and Blender were disabled.
These used FastAPI TestClient with the actual application lifespan, workers,
inference, saving and HTTP/WebSocket endpoints, not a mocked pipeline. Telemetry
was disabled only inside the diagnostic process.

- HTTP start -> cancel -> restart -> complete passed. Cancellation during native
  model startup took several seconds; it is not instantaneous.
- WebSocket delivered running progress. Disconnecting the viewer did not stop the
  recording. Reconnecting after completion returned the completed task snapshot.
- Output readback: a readable Parquet file with 1,865,466 rows and 11 columns;
  all three annotated videos contain 222 frames each.
- Observed complete run times: 38.12 seconds for the restart run and 31.12 seconds
  for the WebSocket run. These are acceptance observations, not controlled speedup
  comparisons; startup/cache state differs and completion was polled once a second.
- Changed frontend modules transpile, and the modal's local import tree bundles
  with external packages using the existing toolchain. This is not a full TypeScript
  typecheck or a desktop/browser click-through acceptance test.

Local evidence is ignored under `.test-artifacts/application-graph/`:
`http-real-3/{result,progress}.json`, `http-websocket-1/{result,progress}.json`,
and their private recording copies. Earlier numbered diagnostic attempts failed
before processing and are not acceptance evidence.

## Remaining boundaries

- Fresh observations, multiple cameras and explicit calibration are required.
  Saved-stage restart, stop-after-stage and pause/resume are not implemented here.
- Loading/tracking stream internally through the bounded adapter, but return all
  observations before the downstream recording-level graph starts. This is not
  yet the full fine-grained streaming graph.
- Native numerical/save calls drain at cancellation boundaries. Completed valid
  checkpoints may remain after cancellation. Mid-save and mid-science cancellation
  have not received real-recording acceptance coverage.
- Annotation and science are independent branches; overall task completion waits
  for all requested sinks. Optional exports run once through the existing app handler.
- Core performance improvements are working-tree changes. SkellyForge batched math
  remains measured experimental work, not an installed dependency change.
- Desktop click-through acceptance and additional real recordings are next, followed
  by saved-stage integration and the careful numerical/performance comparison work.


## Application settings repair — 2026-10-12

Automatic board selection now runs inside the application worker before detector
sessions and the recording graph are constructed. It uses the existing SkellyTracker
selector and SkellyCam sequential readers, with bounded image memory and cancellation
checks. The graph receives the resolved explicit board; the user's original AUTO
request is not mutated. If no supported board is found, the task fails with an
explanation rather than inventing board dimensions. This setup scan stops at the
first match and tracking then starts at frame zero.

Pipeline/device controls now use SettingRow and SettingSelectInput. The board editor
is portalled to document.body, centred and viewport-bounded, with a close button.
This avoids clipping under the transformed, scrolling processing modal; the scroll
area's mask has also been removed. Browser verification used the actual settings
components with mocked external services, not the running Electron window.

Acceptance: full 1,108-frame, three-camera sample recording completed through real
application HTTP/WebSocket endpoints with AUTO board selection and CUDA RTMPose.
All three annotated videos contain 1,108 frames and the final Parquet is readable.
The diagnostic disabled filtering and optional Blender/scientific exports; the
original recording was untouched. Evidence: `.test-artifacts/application-graph/
http-auto-sample-2/`. Sixteen focused backend tests and the frontend typecheck pass.
