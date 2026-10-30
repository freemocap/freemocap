# Handoff: production pipeline graph UX/UI

Updated 2026-10-30. Read this before implementing the UI prototype.

## Goal and scope

Create a separate graph-based configuration and progress interface for FreeMoCap's existing post hoc pipeline. The intended destination is an alternate or supplemental view of the current Mocap processing modal and operation progress list. The user wants the same scientific configuration and execution, expressed more clearly through typed nodes, slots, connections, node settings, and concurrent progress bars.

For now, work only in the Graph Lab experiment. Do not modify or connect controls to the running application. Preserve the accepted synthetic exploration. Do not redesign the pipeline scheduler to accommodate the UI.

Core repository: `C:/Users/jonma/code-stuff/github/freemocap/project/repos/freemocap`.
All paths below are relative to that repository unless stated otherwise.

## Responsibility split

**UX/UI agent owns:** layout, styling, node/port presentation, pan/zoom, selection and inspection, configuration interaction design, progress presentation, accessibility, and browser verification. Work in `experiments/executable_graph_lab/production_view/`. Coordinate before changing `capture.py` or `server.py`, which belong to the integration work.

**Integration agent owns:** production source audit, graph capture, transport/configuration mapping, schema and identity decisions, checking that displayed dependencies and state reflect actual execution, and subsequent integration review. Backend changes require a separate scoped decision; they are not authorized by this prototype assignment.

If a required field or control is absent, record the missing capability and proposed contract in the return handoff. Do not silently invent it or implement a replacement server. Do not add scheduling, scientific validity, completion, or dependency rules to frontend code.

The user will relay handoffs between agents. Do not message another chat without explicit authorization. Leave all changes unstaged and uncommitted. Follow workspace and repository AGENTS.md, including artifact ignores and preservation of other work.

## Read these first

1. `experiments/executable_graph_lab/README.md`: accepted visual direction and experiment boundaries.
2. `experiments/executable_graph_lab/APPLICATION-INTEGRATION-AUDIT.md`: architecture inventory, mismatches, proposed contracts, and integration sequence. Written 2026-10-28; verify against current code before relying on it.
3. `experiments/executable_graph_lab/synthetic/viewer.html`: the accepted visual reference from THIS conversation. This is the full synthetic graph, not an external reference.
4. `experiments/executable_graph_lab/production_view/`: unfinished implementation described below.

There is substantial ongoing unrelated work in the application checkout, including dataflow and transport files. Inspect current status and relevant diffs. Do not overwrite, revert, move, or tidy other agents' work.

## Visual high watermark

The accepted reference is the full synthetic viewer served at port 8766, with typed input/output slots, curved connections, left-to-right default, alternate top-down view, disk I/O styling, camera progress lanes, and a node inspector. It is a design reference, not production execution evidence.

Start it from the core repository with the existing environment:

```powershell
.venv/Scripts/python.exe -B experiments/executable_graph_lab/synthetic/server.py --port 8766
```

Check whether the port is already occupied before starting another instance. Open `http://127.0.0.1:8766/`; the HTML alone requires its server. Do not change this exploration while building its successor.

Local visual evidence: `.test-artifacts/graph-lab-live/fixed-zoom-styling.png`. It exists at handoff time but is ignored and does not travel with Git. It shows the corrected distant overview; inspect the viewer itself at readable zoom for the styling reference.

Non-negotiable lessons from user feedback:

- Keep node shape, size, position, port positions, and layout stable during zoom. No zoom-triggered rearrangement or compact alternate geometry.
- Use the existing coherent typography and colors. Do not overlay independently enlarged white text. Labels must remain inside their boxes; unreadable text at distant zoom is acceptable.
- Inputs attach to left/top, outputs to right/bottom. Put type and input requirements on the slots rather than cluttering edges with text.
- Do not repeat `BCAST` or delivery jargon. Shared-input semantics belong in inspection details when useful.
- Avoid a generic recording-context box feeding everything. Show the actual declared payloads; if the production graph does not expose a dependency, document that limitation rather than adding fictional edges.
- Distinguish disk reads, disk writes, and computation. Show camera work as separate progress lanes when the backend supplies that information.
- Counts must include units and context: camera images versus motion frames, camera count, and per-camera totals. Unknown progress is indeterminate, not an invented percentage.
- Use plain labels such as load, save, detect poses, calculate 3D points, and fit skeletons. Preserve technical identifiers in the inspector.

## What exists in the new folder

`production_view/capture.py` is an UNVERIFIED draft. It calls actual production builders with the test recording metadata and selected calibration, loops over the 15 contiguous start/stop ranges with annotation on/off, and serializes their definitions. It constructs an inert save session to avoid reserving run output folders and never intentionally invokes returned handlers. It uses explicit board information from calibration and CPU configuration for inspection. Saved-stage variants describe topology, not proof that saved prerequisites exist.

`production_view/server.py` is an UNVERIFIED read-only HTTP server draft, intended for port 8768. It has a catalog endpoint and static asset routes. It is not a production server or WebSocket adapter.

`production_view/layout.js` is the layered layout routine copied from the exploration. `style.css` contains initial theme/button styles. **There is no viewer.html or viewer.js yet.** No successful capture, completed UI, or live progress integration has been verified. Do not assume the earlier attempted launch succeeded.

Integration agent must validate capture before these data are treated as reliable. Avoid coupling the new renderer to the synthetic scheduler's contracts. Use the actual graph definition shape (`nodes`, typed `inputs`/`outputs`, source/target port references) and isolate any display adapter.

## Application code to inspect

| Concern | Paths |
| --- | --- |
| Settings modal and editors | `freemocap-ui/src/components/mocap-setup/mocap-setup-modal.tsx` and sibling files |
| Stage/run selection | `freemocap-ui/src/components/mocap-setup/mocap-stage-selection.tsx`; `freemocap-ui/src/services/recording/posthoc-processing.ts` |
| Config state and request assembly | `freemocap-ui/src/store/slices/mocap/mocap-slice.ts`; `mocap-thunks.ts` in the same folder (`buildPosthocConfig`) |
| Accepted config | `freemocap/core/tasks/mocap/mocap_task_config.py` |
| HTTP launch, saved stages, cancellation | `freemocap/api/http/mocap/mocap_router.py` |
| Executable graph contracts | `freemocap/core/pipeline/dataflow/definition.py` |
| Actual graph variants | `freemocap/core/pipeline/dataflow/recording_pipeline.py`; `saved_spatial_pipeline.py` |
| Setup and operation reporting | `freemocap/core/pipeline/dataflow/application_pipeline.py` |
| Export orchestration outside the compiled graph | `freemocap/core/pipeline/posthoc/export_completion.py` |
| Backend progress contracts | `freemocap/core/pipeline/posthoc/progress_messages.py`; `operation_progress.py` |
| WebSocket snapshots | `freemocap/api/websocket/websocket_server.py`, `_posthoc_progress_sender` |
| Client snapshot contracts/reducer | `freemocap-ui/src/services/server/transport/message-contract.ts`; `freemocap-ui/src/services/server/task-progress.ts`; `freemocap-ui/src/store/slices/pipelines/pipelines-slice.ts` |
| Existing progress UI | `freemocap-ui/src/components/pipeline-progress/OperationProgressBars.tsx`, `PipelineGroupCard.tsx`, `ProcessingTiming.tsx` |

## Contract boundaries to preserve

Configuration edits eventually produce the existing HTTP processing request. Run acceptance returns a task/pipeline ID; completion arrives through retained server state. Existing WebSocket task snapshots contain operation IDs, labels, states, counts, units, and timing. The UI displays what the server reports, without waiting for other messages to decide whether scientific data are valid.

Use one configuration draft for both settings and graph views in eventual integration. Node selection should expose the existing relevant settings, not duplicate their logic in SVG. Run-wide choices such as recording, start/stop stages, source run, and overwrite/new-run belong above the graph. A running task needs its own immutable launched configuration and graph identity, separate from any draft being edited.

The current application does not yet expose a complete graph-preview transport contract. Do not presume this is a frontend-only change already solved. Prefer the existing server command/report architecture; report the smallest missing boundary fields to the integration agent.

The production graph is coarser than the exploration: `load_and_track` combines reading and tracking; `match_and_triangulate` combines camera matching and 3D calculation. Setup and final exports have surrounding application orchestration. Preserve these actual boundaries. Expandable internal details must be identified as internal work, not separately scheduled nodes. Configuration fields, scientific saved stages, executable operations, and per-camera work are related but not interchangeable.

Do not enable arbitrary wire editing, pause, step, hold-node, injected failures, or per-node rerun merely because the synthetic viewer has those controls. Only display actionable controls supported by a reviewed backend capability. No progress animations or completed states may imply actual processing in this definition-only prototype.

## Suggested first UX deliverable

Finish a read-only graph viewer that consumes reviewed production definitions. Offer full-run and stage-range views; preserve the actual nodes and edges. Show setup/export context separately and label it as outside the compiled graph. Provide a useful node inspector for ports, resource, source identity, and configuration context. Clearly distinguish definition inspection from live processing.

Design the future node-settings/progress interaction alongside this, but keep unsupported controls visibly nonfunctional or out of the prototype. Any fabricated progress examples must be explicitly labeled illustrative fixtures, never recorded/live results. Actual snapshot replay requires agreement on capture and operation-to-node identity with the integration agent.

The prior single-agent six-step checklist was proposed but not approved. The user has now split responsibilities. Do not execute the old list as if it granted ownership of backend capture or production integration. Propose a focused UI checklist if using the linear-checklist skill.

## Return handoff for integration review

Write `experiments/executable_graph_lab/production_view/UX-RETURN-HANDOFF.md` with:

- Changed files and launch instructions.
- Screenshots at readable and distant zoom, both orientations, and a narrow viewport; record any layout limitations.
- Exact input contract and any mapping from server operation IDs to displayed nodes.
- Supported interactions, mocked interactions, and absent backend capabilities.
- Any requested schema additions, with reasons and example payloads; no silent backend assumptions.
- Checks performed, results, and remaining failures. Verify zoom does not change node geometry or cause label overflow.

The integration agent will review data identity, graph fidelity, request equivalence, snapshot handling, and separation from execution before application changes are considered.

## Suggested skills

Use `linear-checklist-task` for the agreed UI work sequence and `clear-technical-writing` for labels and handoff text. Use browser/computer-use guidance for visual verification. A prototype/design skill may help if appropriate, but do not publish to an external hosting service or replace the local repository workflow.
