# Graph Lab and application integration audit

Audit date: 2026-10-28. Source inspection only; no application changes, pipeline runs, or new performance measurements. This note describes the checkout on disk, not proof that the currently launched application uses that exact revision.

## Conclusion

The Graph Lab visual approach can serve as a second view of the application's processing configuration and live progress. It is not a drop-in replacement. Reuse the application's scientific execution, request validation, run handling, task registry, and WebSocket transport. Adapt the lab's renderer and interaction design to those contracts. Do not transplant the synthetic scheduler or maintain a second handwritten description of the production graph.

A node click should open settings for that operation; Run should submit the same processing request as the existing modal. Once launched, the graph should display the server's retained task state. The existing settings view and progress list can remain alternate views of that same state.

## What exists today

Paths below are relative to the core repository root.

| Responsibility | Existing implementation | Implication |
| --- | --- | --- |
| Settings modal | `freemocap-ui/src/components/mocap-setup/mocap-setup-modal.tsx` and its section components | Reuse detector, calibration, filtering, export, and Blender editors. Do not rebuild their domain logic inside SVG. |
| Stage and run selection | `mocap-stage-selection.tsx` in the same directory | Already supports a contiguous start/stop range, saved inputs, source run, overwrite, and new run. Graph selection must preserve these semantics. |
| Request construction | `freemocap-ui/src/store/slices/mocap/mocap-thunks.ts`, `buildPosthocConfig` | Both views must build the same request. Most settings are Redux state; stage selection and execution choices also have modal-local state that needs a shared draft owner. |
| Server configuration | `freemocap/core/tasks/mocap/mocap_task_config.py` | Pydantic owns accepted settings and stage-range validation. Typed data flow is already the default. |
| HTTP commands | `freemocap/api/http/mocap/mocap_router.py` | Existing routes launch processing, inspect saved stages, and cancel tasks. The process response acknowledges launch; it is not completion. |
| Executable definitions | `freemocap/core/pipeline/dataflow/definition.py` | Immutable nodes, typed ports, edges, binding rules, and compiler validation already exist. |
| Graph construction | `recording_pipeline.py` and `saved_spatial_pipeline.py` in that directory | Different source/stage choices build different actual graphs. Export these definitions rather than reconstructing edges in the frontend. |
| Execution | `recording_executor.py` | Recording-level dependency dispatch with compute, annotation, and recording-I/O pools. Frame loading/tracking stream internally. |
| App integration | `application_pipeline.py` | Resolves inputs and provider, reports operations, runs the graph, and then invokes final exports. |
| Final exports | `freemocap/core/pipeline/posthoc/export_completion.py` | Blender and file exports run concurrently; scientific and tall CSV exports serialize because they share a manifest transaction. This work is outside the app's main compiled graph. |
| Live progress | `progress_messages.py`, `operation_progress.py` under `core/pipeline/posthoc/` | Operation identity, label, state, counts, units, elapsed time, and time per motion frame already exist. |
| Transport and rendering | `api/websocket/websocket_server.py`, UI `services/server/task-progress.ts`, `components/pipeline-progress/OperationProgressBars.tsx` | Server sends complete retained task snapshots every 0.5 seconds. UI applies server revisions and displays operation state. Keep this architecture. |

## The important mismatches

### The lab is not the current execution graph

The synthetic graph at port 8766 separates frame readers, inference session, pose tracking, board detection, joins, and other operations. The production recording graph exposes `load_and_track` as one operation and `match_and_triangulate` as another. Its executor accepts recording-level, same-key bindings only, although the definition vocabulary supports other granularities.

Consequently, a lab edge suggesting per-frame readiness is not evidence of that behavior in production. The current triangulation operation consumes completed observations. We must not draw the lab topology and attach production percentages to it as if the diagrams described identical execution.

For an initial integration, show the actual coarse operations. Camera lanes can be expandable progress inside the loading/tracking operation when the backend supplies those counters. Label these as internal work, not independent scheduler nodes. Deeper executable subgraphs are a separate implementation decision.

### Configuration is not one field per node

Some controls apply to several operations: recording selection, run destination, stage range, calibration, detector configuration, and execution provider. Keep run-wide controls above the graph. Associate operation-specific editors with nodes. Multiple nodes may refer to one shared configuration section; they must not acquire separate copies of its values.

Do not initially offer arbitrary wire editing. Selecting a tracker, saved source, stage range, or export changes the server-resolved graph. Matching port types alone is insufficient to authorize a scientifically valid workflow.

### Preview is not yet a lightweight public contract

The existing builder returns a serializable compiled definition, but also constructs handlers, loads calibration, builds model definitions, and requires resolved inputs. Application setup resolves automatic board selection before building the graph. There is no graph-preview route in the inspected mocap router.

Separate pure topology planning from expensive resource preparation before calling it on each settings edit. Reuse the same planning result to construct execution handlers. Automatic board selection can appear as unresolved setup work in a preview; report the resolved definition when known. Do not run inference or reserve a destination run merely because a user opens the graph.

### Progress needs a stable link to the graph

Production operation IDs often already equal graph node IDs. However, current task snapshots do not include graph topology, graph identity, node-to-stage membership, configuration bindings, disk artifacts, or dependency wait reasons. Progress operations appear as their producers report them; the full set of waiting operations is not supplied as a graph.

Add a backend-owned description of the plan, then retain execution state against its node IDs. Final exports need explicit representation too. Until their composition is made declarative, distinguish the compiled processing subgraph from surrounding setup/export phases instead of inventing dependency edges.

The lab's synthetic viewer polls its own HTTP API and exposes hold, step, and injected failure controls. Those are lab capabilities, not established production controls. Use the application's WebSocket snapshots and existing cancellation command. Add pause or node controls only if the backend implements and advertises them.

## Proposed shared contract

These are responsibilities, not a final schema:

- **Processing draft:** recording, scientific settings, requested stage range, source run, and save policy. Shared by settings and graph views.
- **Processing plan:** backend-resolved nodes and typed connections, stable IDs, stage membership, configuration-section references, declared sources/sinks, artifact descriptions, unresolved setup information, and validation messages.
- **Run snapshot:** task ID, the executed plan identity, immutable launch settings, node states, counts and units, per-camera progress where available, timings, failure/dependency information, and saved output receipts.

Generate transport types from backend schemas where practical; add serialized fixture tests across Python and TypeScript. The current UI has explicit Zod task schemas, so schema generation must be an intentional integration change rather than an assumed existing facility.

Execution never waits for the graph view. The backend retains bounded progress state; the transport reads it and the UI displays it. Closing, hiding, slowing, or disconnecting the view must not change scheduling or output. Runtime task snapshots must carry or resolve their own executed plan: do not overlay a running task on whatever configuration the user is editing now.

## User interaction

1. Choose a recording and source run; choose overwrite or keep as a new run.
2. Select the scientific stages. Show saved inputs as sources and requested outputs as sinks. Explain the actual prerequisites the backend includes, including coordinate alignment before saving requested aligned 3D results.
3. Click a node to open the existing relevant settings editor in an inspector. Edits update the shared draft and request a revised server preview. Reject stale preview responses when later edits have superseded them.
4. Run sends the validated request over HTTP. Recheck saved-input revisions and configuration at launch; reject or return an updated plan if the preview has become stale.
5. Associate the returned task ID with its executed plan. Display backend operation progress on the nodes, stacked camera progress where provided, and a run summary. Unknown totals remain indeterminate; never invent a percentage or infer success from elapsed time.
6. Allow inspection of inputs, settings used, failures, timings, and output paths after completion. A rerun creates a fresh draft rather than changing the historical execution view.

Node positions and dimensions stay stable while zooming. Preserve the accepted typed slots, curved edges, disk colors, camera bars, and inspector. Keep layout coordinates as presentation state; they are not part of the scientific graph.

## Recommended implementation order

- [ ] Define and test a backend plan description from the existing graph builders, including saved-2D and saved-3D variants. Identify setup/export ownership explicitly.
- [ ] Establish a preview/execution planning seam and plan identity. Prove preview has no processing or save side effects and launch checks stale inputs.
- [ ] Extend retained task snapshots with plan linkage and backend node state; preserve the current progress-list consumer.
- [ ] Build a read-only graph view against captured production plan/snapshot fixtures in the lab. Cover full runs, partial stages, reruns, concurrent annotation, failure, and cancellation before connecting live controls.
- [ ] Extract shared draft ownership and mount existing settings editors from graph selection. Prove settings-view and graph-view requests are identical.
- [ ] Add the graph as an optional view in the app, using existing HTTP launch/cancel and WebSocket snapshot handling. Keep the existing modal/list available.
- [ ] Validate complete user flows with the established reference test dataset and measure observer overhead with the graph closed, open, and reconnecting.

The first useful milestone is a faithful read-only visualization of the actual production plan and its recorded progress. It proves identity and observability before adding a second configuration surface.

## Required checks before calling it integrated

- Exact node/edge correspondence between preview and the executed plan, or an explicit server-issued resolved revision.
- Existing 15 contiguous start/stop combinations for five scientific stages, using the opt-in test-dataset stage matrix; include saved-source and keep/overwrite scenarios.
- Config request equivalence for RTMPose, MediaPipe, board options, CPU/CUDA support rules, alignment, filters, exports, and Blender.
- Disconnect/reconnect, late subscription, multiple viewers, dropped intermediate updates, cancellation, failure, and partial completion. A retained snapshot must restore the complete display without replaying every event.
- Units distinguish camera images, motion frames, and export channels. Node duration is not automatically CPU time; concurrent node durations must not be summed into elapsed run time.
- Annotation progress cannot control scientific scheduling. Display must describe actual current dependencies, including any whole-recording boundaries, rather than conceal them.
- Existing contract, stage, provenance, and operation tests remain in place. Add focused plan/transport/UI tests; reuse reference-dataset infrastructure for real-run checks.

No new numerical pipeline or benchmark framework is required for this UI integration. No application source was changed for this audit.
