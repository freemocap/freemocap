# Executable Graph Lab

## Payload validation and resource ownership — 2026-10-06

`contracts.py` defines seven versioned dataclass contracts for the first adapter
boundary: timing, detector configuration, session descriptor, frame descriptor,
publication plan, frame receipt and publication receipt. Both input consumption
and output publication validate these payloads. Contract fields are exported to
the viewer from the same definitions and participate in graph identity.
Unexpected fields, wrong scalar/container types, nonfinite timestamps and a
provider that violates the fallback policy are rejected. Other scientific
payloads are explicitly marked `fixture-only`; these are not finished production
array/model schemas. VideoFrame currently describes a synthetic frame, not a
pixel-buffer transport. Receipts currently support only simulated publication.

`Node.resource_uses` declares session and camera-writer lifetimes independently
of CPU/GPU/encoder dispatch capacity. `lifecycle.py` derives each resource's users
from the compiled work graph. An inference session is released as soon as its
users finish, even while annotation remains held. Each camera writer closes
before its final frame receipt can be published. The run owns the handles;
immutable artifacts carry descriptors only. Acquisition registers a synchronous
owned shell before any asynchronous initialization or processing can suspend.

Cleanup is scheduled on success, failure and cancellation. Cancellation during
close does not interrupt cleanup. A run cannot become terminal before handlers
and cleanup settle. Cleanup exceptions remain visible and fail the owning
branch; they never silently become successful publication. Other resources are
still closed. Cleanup is attempted once per acquired handle. Real adapters must
provide their own close implementation, bounded shutdown policy and any recovery
procedure for a failed close; the synthetic close opens no external resource.

The node inspector now renders resource state and payload fields directly from
backend metadata. This is a small generic addition to the existing viewer; it
does not author graph connections. Left-to-right remains the startup default.

Validation: 26 tests, including malformed payloads, rejected provider fallback,
early session release, cleanup on failure/cancellation, cancellation during close
and writer-close failure blocking video completion. The next stage is to define
the real frame-buffer/observation transport and connect a small pose-only run in
core. No production source, environment or dependency has changed here.

## Explicit boundary contracts — 2026-10-06

The executable graph now includes these prerequisites. They are ordinary typed
nodes and bindings, so the existing viewer displays exactly what execution waits
for; no second diagram or viewer-specific topology was added.

- **Resolve recording timing:** camera identities, frame numbers, synchronized
  timestamps and timing provenance. Decode consumes this grid; inference checks
  the camera set and synchronized frame. The fixture remains uniformly 30 Hz.
- **Configure pose detector → Open inference session:** model references,
  requested provider, fallback policy and camera batch membership. The session
  descriptor reports `actual_provider=simulated`; it is never evidence of CUDA.
- **Select ChArUco board:** a required explicit board-definition input. Automatic
  selection is a different graph variant that still needs design.
- **Load selected calibration → Resolved camera models:** multicamera matching
  consumes the selected document and all observation evidence. This is an
  intentional recording-wide barrier grounded in `PosthocMatchingRequest`.
  A future validated camera-assignment path could remove that barrier; the lab
  does not assume it away. Single-camera runs use a planar fallback without a
  calibration read. Pose-only and calibration-solving tasks need no input TOML.
- **Plan artifact publication:** supplies recording identity and publication
  semantics to scientific and annotation sinks. Scientific receipts include
  input-work provenance. The video writer's last ordered frame includes its
  simulated close/publication; the completion join validates all camera/frame
  receipts and each final stream receipt. There is still only one video writer.

All receipt payloads explicitly report `durable=false` and simulated publication.
No models, videos or calibration files are opened. Session descriptors carry no
live handle. The resource-owner pass above now exercises cleanup with synthetic
handles. Real adapters must implement device/file teardown. Temporary-file cleanup, atomic publication,
checksums and recovery require real adapters and integration tests.

Validation: 20 tests cover graph/view agreement, all task variants, required
inputs, failure isolation, timing validation, session readiness, camera-matching
evidence, incomplete/duplicate video receipts and publication provenance.

The next implementation boundary is a real recording/timing reader and a real
detector-session owner, tested on a small recording through the pose-only graph.
Before that adapter runs, define typed production payload schemas and resource
cleanup tests. Keep the existing coordinator out of the new graph. Reconstruction
still needs explicit model definitions, measured-support and alignment contracts.

## Application mapping — 2026-10-06

The node names and payload vocabulary now refer to inspected FreeMoCap code.
Each backend node exports `source_refs` (`repository-relative file:symbol`) in
the same graph definition used for execution and display. Descriptions identify
the real boundary and the remaining simulation. Slot types are **proposed
domain contracts**, not Python class identities or claims that the small JSON
fixtures implement production schemas. All handlers remain synthetic.

Inspected core HEAD: `c8c458f3a96d51f1123055785dbf0db030a60a34`, with unrelated
working-tree changes present and preserved. No production code was changed.

| Graph operation | Application boundary | Intended data |
| --- | --- | --- |
| Recording context / Decode synchronized video | `VideoGroupHelper`, `MocapVideoNode`, `ReadFrame` | Recording identity, camera IDs, frame grid, BGR images |
| RTMPose camera batch | `InferenceService`, `tracker_session_requests` | Camera-keyed `Observation` results from configured RTMPose/RTMW and person detector |
| Detect ChArUco corners | ChArUco work currently in `MocapVideoNode` | Board observations with a selected board definition |
| Assemble camera observations | `MocapDetectionFrame.observations` | Tracker and board stages per camera/frame |
| Resolved camera models | `run_posthoc_mocap_task`, `CalibrationResult`, camera matching | Resolved `CameraModel` collection |
| Triangulate keypoints | `triangulate_observation_buffers` | `RAW_KEYPOINTS_3D`, weights and reprojection diagnostics |
| Prepare 3D trajectories | `prepare_recording_points` | Gap-filled/filtered coordinates, timestamps, filtering report and measured-support mask |
| Fit recording-wide model scale | `reconstruct_skeletons_for_recording`, `FittedRecordingScale` | Fit and its model/evidence provenance |
| Reconstruct anchored skeleton | `reconstruct_skeleton`, `SkeletonReconstruction` | Mapped observations, rigid landmarks, segment origins and rotations remain distinct |
| Publish processing checkpoint | `publish_posthoc_observations` and checkpoint publication | Parquet samples, definitions and stage provenance |
| Solve ChArUco calibration / Publish calibration TOML | `run_posthoc_calibration_task`, `_save_result` | Calibration result and TOML |
| Render observation overlays / Write annotated video | `build_observation_annotator`, `AnnotationVideoOutput` | Drawn pixels, ordered encoding and publication lifecycle |
| Collect video completion receipts | `FinishVideo` coordination | Completion bookkeeping; not another video writer |

### Differences that must be resolved before real adapters

This is the **replacement design**, not the current production execution graph.
`detect_mocap_recording` still waits for annotation futures; the annotation
command also detects and merges ChArUco observations. `run_mocap_pipeline`
collects the recording's observations before numerical processing. Independent
board detection, annotation decoding and per-frame triangulation are proposed
scheduling boundaries, not existing behavior.

The boundary-contract pass above adds timing, detector/session descriptors,
explicit board selection and calibration loading/matching. Real session resource
ownership, automatic board selection, tracked model definitions, coordinate alignment, measured-support provenance,
checkpoint reuse/invalidation, and durable publication remain to implement. In particular,
scale fitting cannot depend on coordinates alone. The combined reconstruction
payload must not merge `MAPPED_KEYPOINTS_3D`, `LANDMARKS_3D`, `SEGMENT_ORIGINS`
or rotations into an ambiguous generic point stream. The current toy payload
does not yet carry those products.

Production publishes intermediate checkpoints, not only the lab's final sink.
Production annotation has temporary files, close/publish phases and derivation
metadata; an in-memory receipt is not proof of durable publication. Inspection
also found path drift: `RecordingStructure` declares `videos/annotated`, while
`AnnotationVideoOutput` currently uses `ANNOTATED_VIDEOS_FOLDER_NAME` from
`default_paths.py` (`annotated_videos`). The lab retains the canonical intended
directory, with `<source filename>.annotated.mp4` naming; this is not a claim
that the current writer has migrated. Resolve this at the real writer boundary.

The first real slice remains recording/video timing → RTMPose camera batch →
observation checkpoint, with an independent annotation branch. The prerequisites
are now graphed; production payloads and resource ownership remain to implement.
No old executor wrapper or legacy node is part of that migration.

An isolated architecture experiment for FreeMoCap. Real dependency scheduling and
controls operate on small synthetic artifacts. No production pipeline is imported
or changed by this prototype, and no real recordings are opened.

**Migration decision:** the eventual production implementation is a complete
replacement. There will be no legacy node, adapter wrapping the old coordinator,
or retained alternate executor. This lab precedes that replacement; it does not
claim that the production migration has happened.

## Run

From this directory, using Python 3.10 or newer:

```powershell
python -B server.py --port 8766
```

Open <http://127.0.0.1:8766/>. The single HTML file has no external assets or build
step. Serve it through this backend rather than opening it as a file. Ctrl+C
stops the server. No dependencies need to be installed. The interpreter already
present in this workspace can also be used:

```powershell
& '..\..\repos\freemocap\.venv\Scripts\python.exe' -B server.py --port 8766
& '..\..\repos\freemocap\.venv\Scripts\python.exe' -B -m unittest -v test_lab
```

The lab lives in the workspace's ignored `.test-artifacts/` directory, outside
the independent production repositories. Keep this directory to keep the demo;
it is intentionally not a tracked production deliverable.

## What to try

The page has four regions. The top bar holds run state, elapsed time, work
counts, scientific-branch status and the run controls (Start run, Pause/Resume,
Step, Cancel, Download snapshot). The left panel composes the configuration.
The canvas fills the remaining height. The right panel inspects the selected
node. Execution events sit in a collapsible drawer under the canvas.

**Left to right** (default) and **Top down** change orientation without changing
the plan or run. **Expand cameras** projects the compiled work into camera
lanes; **Collapse cameras** returns to logical operations.

Layout is a layered (Sugiyama-style) pass computed from the backend edges:
nodes are ranked by dependency depth, producers are pulled forward next to their
earliest consumer, layer order is swept to minimise wire crossings, and wires
that span several layers are routed through channels between nodes rather than
behind them. No positions are authored.

The canvas supports dragging its background to pan and wheel/trackpad zoom
anchored at the cursor. Focus the canvas and use arrow keys to pan with a
keyboard. The first view opens at a readable scale (fit when the whole graph
fits at 75% or more, otherwise 75% starting at the source nodes). **Fit all** is
an overview; **100%** restores readable scale around the viewport center, and
**Focus node** centers the selected operation at 100%. Below 50% zoom, slot
labels and metadata hide so the overview shows only structure.
**Expand workspace** hides the side panels; Escape or **Exit expanded
workspace** restores them. Navigation changes only the view, never the
executable plan or run state.

Hovering a node highlights its wires and direct neighbours and dims everything
else; the selected node keeps its wires emphasised. Wires into a running node
animate (disabled under reduced-motion).

Each node is a compact card: title, one metadata line
(`resource · scope · ordered`, prefixed `cam N` in camera lanes), input slot
rows, output slot rows, then a progress bar with a completed/total count.
Left-to-right nodes expose input sockets on the left edge and output sockets on
the right; top-down nodes expose inputs along the top edge and outputs along the
bottom. Wires have no floating captions: each wire starts at its named producer
slot and ends at the named receiving slot.

Socket and wire colours derive from payload type; a slot row names its type
when the type differs from the slot name, and the Legend lists every type
colour. Filled sockets are required inputs; hollow sockets are optional; a
dashed grey socket with `· off` is an unconnected optional input. Non-trivial
key rules show as a short tag on the input row: `3→1` fan-in (`all_sources`),
`1→3` fan-out (`frame`), `bcast` (`broadcast`) and `barrier` (`sealed`);
`same_key` shows no tag. Solid wires are the scientific branch; dashed wires
feed the annotation branch, whose nodes also use a warmer card fill.

Runtime state is an icon in each node's top-right corner plus the border colour:
blue pulse = running, green check = complete, amber pause = held, red cross =
failed, red slash = blocked, grey cross = cancelled, hollow circle = not
started. Tooltips on nodes, slots and wires give the full slot contract and
binding.

Disk I/O is drawn as a separate kind of connection, never as a data wire.
A node whose `io_role` is `read` or `write` gets a cut-corner card (in-memory
nodes keep rounded corners), a tinted fill, a `LOAD`/`SAVE` tag in its header
and a disk terminal hanging off the card perpendicular to data flow, like a
ground symbol in a schematic: a folder joined to the card by a thick double
rail. **Load from disk** (blue): the arrow leaves the folder and enters the
node. **Save to disk** (purple): the arrow leaves the node and enters the
folder. The terminal hangs below the card in left-to-right layout and to the
right of it in top-down layout, and its rail animates while the node runs.
Both roles remain simulated.

The inspector shows the node's branch and camera scope, state, Hold/Release and
Fail next item, progress with per-state counts, one card per input slot
(type, required/optional, source slot, key rule and fan-in/fan-out cardinality),
one card per output slot with its consumers, wait reasons, execution details
(resource, scope, ordering, partitions, disk role, handler time, identity), and
collapsible work keys and latest artifact. Disk-touching nodes are labelled
`LOAD FROM DISK` or `SAVE TO DISK` above the node name.

`InputSlot(name, data_type, required)` and `OutputSlot(name, data_type)` declare
contracts separately from bindings. A binding identifies the source node and
**source slot**, target input slot and key rule. Compilation rejects missing
required inputs, unknown slots, incompatible types, duplicate slot names,
invalid key relationships and cycles. Matching types alone are insufficient:
camera/frame scope and key mapping also have to match.

An optional input can be unconnected and receives an empty tuple. If connected,
it is awaited like any other declared dependency, including failure propagation.
This avoids timing-dependent output. Observation join always declares optional
`boards`; the configuration controls whether that slot is wired. Turn off
**Include board observations** to inspect and execute the unconnected case.

Handlers publish a mapping of output-slot name to immutable artifact. The
executor validates names/types/work identity before atomic publication and
hydrates consumers from the explicitly bound source slot. Current synthetic
handlers each publish one slot named `out`; the runtime output mapping supports
multiple declared slots. The UI is an inspector/controller, not yet a manual
wire-drawing editor. Task definitions own the connections.

Board detection is one work stream per camera: cameras can overlap, while this
prototype preserves frame ordering inside each camera. Expanded lane counts and
edges are computed from actual work keys and dependencies, with per-camera live
progress. Pose inference joins those camera images into one batch per frame;
the observation join gathers board results per frame. A sealed-stream fan-in
waits for all frames and is distinct from the per-frame camera join. Camera
lanes do not promise a dedicated worker: resource slots cap admitted concurrency.
Holding or failing a node from an expanded lane controls its logical operation
across all cameras; the inspector states this scope explicitly.

1. Resolve Motion capture with three cameras and annotations enabled.
2. Select **Encode videos**, click **Hold node**, then **Start run** (top bar).
3. Watch the scientific branch finish while encoding remains held. Inspect the
   node's declared inputs, work keys, and wait reasons.
4. Click **Release node** to finish annotation. Shared CPU/I/O capacity can cause
   contention, but annotation completion is not a scientific data prerequisite.
5. Enable Start paused for another run. Step admits exactly one work item;
   Resume enables continuous dispatch. Pause stops future admissions, while
   already admitted work finishes. Cancel prevents late result publication.
6. While a node is held, arm **Fail next item**, then release it. An annotation
   failure permits scientific completion and a partial overall result. A
   scientific failure blocks its descendants.
7. Switch between Motion capture, Pose tracking, and Camera calibration. Toggle
   annotations and board observations, adjust source count, frame count, worker
   capacity, and synthetic costs. Resolve shows the exact plan that will run.
   Calibration always requires board observations regardless of the optional
   board setting used by pose/motion-capture tasks.
8. Refresh during a run: the page reconnects to the backend's most recent run.
   The download icon in the top bar saves its graph and runtime state together.

One run is admitted at a time. The server retains its last six runs in memory;
restarting the server discards them. A held run must be released or cancelled
before starting another.

## Source map and ownership

| File | Owns |
| --- | --- |
| `graph.py` | Node/port/key contracts, task variants, validation, work expansion, graph identity and inspection representation |
| `engine.py` | Immutable artifacts, synthetic handlers, readiness scheduling, resource admission, ordering, lifecycle and diagnostics |
| `server.py` | Loopback HTTP transport and run registry |
| `viewer.html` | Layered graph layout computed from backend edges, node/slot rendering, configuration and run controls, inspector, snapshot rendering; no separately authored task topology |
| `test_lab.py` | Contract, execution, ordering, failure and cancellation tests |

`definitions(config)` produces nodes with typed input bindings. `compile_graph`
validates cycles, producer/type compatibility, key relationships and duplicate
identities, then expands them into work items. `Plan.describe()` exports those
same definitions as nodes and edges for the viewer. The definition/configuration
digest accompanies runtime snapshots, and the viewer rejects a mismatched run.
The graph/execution consistency test checks that visualization edges correspond
to the actual resolved execution inputs.

There is one authoring location for relationships. Presentation layout is
computed from those relationships. Runtime status is reported by the executor,
not inferred from a frontend animation or a second graph description.

## Scheduling contracts

Each work item is identified by node, frame and camera where applicable.
Each input port names its producer, payload type and key mapping:

| Rule | Meaning |
| --- | --- |
| `same_key` | Consume the producer at the same camera/frame or frame key |
| `all_sources` | Fan in every camera for one frame |
| `frame` | Fan out a frame result to camera-specific work |
| `broadcast` | Supply a recording-wide artifact to each consumer |
| `sealed` | Require every item in a finite upstream stream |

Handlers receive only their declared, materialized input artifacts. They never
wait on other nodes' futures or dispatch downstream operations. The scheduler
admits an item once its inputs, partition ordering and resource capacity allow
it. Completion or a control command wakes the scheduler. Independent ready
operations overlap; CPU, I/O, GPU and encoder capacities are separate.

Ordering is explicit per camera for decoding/encoding and per frame stream for
the simulated tracker/reconstruction. The pose operation consumes all cameras
as one batch for a frame. The offline filter deliberately waits for a sealed
recording: a real future-sample algorithm needs that barrier. Annotation is a
separate branch and re-reads synthetic images independently. Artifacts are
immutable JSON values, preventing annotation from modifying scientific results.

The inspector distinguishes missing input, ordered predecessor, held state,
pause and resource contention. It exposes sample missing work keys, completed
counts, active capacity, handler wall time and a bounded event history. Node
failure blocks data/ordering descendants; it does not cancel independent work.

## HTTP surface

| Method/path | Purpose |
| --- | --- |
| `GET /api/catalog` | Task catalog and configuration defaults |
| `POST /api/preview` | Validate configuration and resolve the graph |
| `POST /api/runs` | Start with `{config, held, paused}` |
| `GET /api/current` | Reconnect to the latest graph and run |
| `GET /api/runs/{id}` | Live execution snapshot |
| `POST /api/runs/{id}/control` | `{action, node}`; pause/resume/step/cancel/hold/release/fail |

The UI polls every 250 ms; the executor itself is event-driven. HTTP binds only
to loopback. It is a single-user development controller, not a deployed service.

## What this proves, and what remains

This demonstrates executable definitions driving the UI, keyed hydration,
explicit fan-in/fan-out, ordered partitions, independent annotation progress,
configuration variants, lifecycle controls and failure propagation.

The simulation uses asyncio sleep to model overlapping work. GPU slots are
**simulated**: no CUDA, RTMPose, MediaPipe, real CPU parallel computation or media
encoding occurs. Synthetic timings are not performance predictions. Geometry,
filtering and reconstruction values are toy calculations, not scientific output.

The finite plan is pre-expanded (at most 5,000 work items) and scanned on wakeup.
Artifact JSON payloads have an 8 MiB per-run limit; this is not a bound on total
Python process memory. Artifacts remain resident until run eviction; exhaustion
fails work rather than providing streaming backpressure. Publication is in
memory, with no durable files, retry recovery, checkpoints or resumable runs.

Before production replacement, the same contracts need resource-specific
workers (including an actual GPU owner), measured batching, bounded source
windows, artifact release/spill, fair admission, durable outputs, process cleanup
and recovery semantics. A shared resource can still slow independent branches;
the graph alone does not guarantee throughput. Production adapters and real-data
performance/correctness tests belong to the later replacement, after review of
this isolated experiment.
