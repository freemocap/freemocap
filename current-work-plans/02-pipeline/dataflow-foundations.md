# Dataflow: intellectual context and working terminology

Research note, 2026-10-10. Design exploration, not an implemented runtime.
Citation keys resolve in root `references.bib`; review fields record actual access.

## Intellectual location

Our umbrella is **dataflow models of computation**: graph structure describes
connections, while a model of computation defines their execution meaning.
“Typed executable dataflow graph” is our descriptive combination of established
concepts, not a claim to a single standardized formalism or newly invented field.

Historical roots include operand-driven dataflow computer architecture
[@dennisMisunas1974] and Kahn's process-network semantics [@kahn1974]. Those two
references were located through metadata, not fully reviewed: detailed theorem
claims remain a reading task. Lee and Messerschmitt's synchronous dataflow uses
known token production/consumption rates to enable static scheduling
[@leeMesserschmitt1987]. Ptolemy distinguishes multiple models of computation,
including static and dynamic dataflow, and discusses related Petri-net models.
Its account clarifies that synchronous dataflow does not imply a single global
execution clock [@leeNeuendorfferZhou2014].

Graph theory gives connectivity and reachability; type contracts constrain legal
composition; execution semantics define readiness, invocation and completion.
The proposed FreeMoCap design additionally needs resource ownership, bounded
delivery, external effects, scientific provenance and durable restart boundaries.
These additions are project design requirements, not guarantees inherited from
calling the system a graph. A DAG is a restricted graph topology, not a synonym
for dataflow. Feedback would require further explicit semantics.

## Applied references

| System | Relevant precedent |
| --- | --- |
| LabVIEW | Executable visual wiring and required-input readiness [@niLabviewDataflow]. |
| GStreamer | Source/sink pads, media capabilities, push/pull scheduling [@gstreamerPads; @gstreamerScheduling]. |
| DirectShow | Filter graph media transport, allocation and state [@microsoftDirectshowDataflow]. |
| ONNX | Typed operator graphs and validated input/output structure [@onnxIR]. |
| OpenCV G-API | Declarative vision graphs separated from implementation backends [@opencvGAPI]. |
| Dask | Python task dependency graphs and inspection of the computational graph [@daskSpecification; @daskVisualization]. |
| Apache Beam | Bounded and unbounded collections in a common processing model [@beamModel]. |
| OBS | Sources, filters and scene composition; an adjacent media example [@obsSources]. |
| SkellySpeak | Local reference for compiled graph authority and thin generated inspection contracts [@skellyspeakGraph2026]. |

These are intellectual references, not dependency selections. Their execution,
failure and persistence guarantees differ. Reuse must follow a concrete fit audit.

## Working glossary

These definitions are proposed unless marked as agreed in the design interview.

* **Operation:** reusable computation with declared inputs, outputs and behavior.
* **Node:** an occurrence of an operation in a graph; not necessarily a worker.
* **Port:** named typed input or output endpoint.
* **Binding:** explicit supply of an input from an output, constant or boundary.
* **Data item (token):** a value made available through a binding; it may reference
  separately owned image storage.
* **Firing:** one invocation for specified inputs and a key, such as a camera/frame.
* **Source:** boundary operation introducing externally obtained data. A saved
  calibration is a source relative to a reconstruction graph.
* **Sink:** operation delivering an external effect, such as saving or displaying.
  It may also emit a completion receipt.
* **Subgraph:** a composition with explicit boundaries.
* **Stage (agreed):** a durable, validated restart boundary. Other groupings are
  subgraphs; this is our workflow convention, not universal graph terminology.
* **Execution policy:** ordering, capacity, placement, buffering and delivery rules.

## Settled design choices and open work

Owner clarification, 2026-10-10: this is a ground-up reconstruction of the
processing model. Existing and historical implementations are evidence about
required capabilities and successful or failed boundaries, not compatibility
requirements. No legacy execution wrapper is desired. Compatibility with older
pipeline APIs is not a goal; any proposed changes to scientific data semantics
must still be explicit and tested rather than accidental.

Rollout update, 2026-10-11: preserve realtime as implemented and retain the current
posthoc execution path alongside a separately selectable new graph path during
development. Compare complete functionality, numerical results and measured
throughput before a later replacement decision. This is an authorized temporary
comparison arrangement, not reuse of old coordination inside the new graph.

The graph-lab screenshots are from the prototype developed in this same design
conversation. They are local design evidence, not an external system reference.
Retain their useful inspection ideas without treating their runtime as authoritative.

The owner's historical account motivates a focused audit of camera/video fan-out,
observation fan-in and shared GPU inference. Logical independence, batching and
physical concurrency must be distinguished. Thread execution is the preferred
starting point for non-camera work, subject to measured native-code/GIL behavior;
camera capture retains process isolation. Switchable placement must preserve
declared transport and ownership contracts. These are design directions, not a
claim that changing a worker flag makes every existing handler process-safe.

Durability and scheduling are distinct (agreed): saving a stage does not gate
downstream computation. Ready keyed data releases dependent work eagerly, subject
only to declared data, state-ordering and actual resource constraints. Whole-record operations
must declare that requirement; the current posthoc filter uses `sosfiltfilt` in
`freemocap/core/reconstruction/posthoc_filtering.py`. “Butterworth” alone does not
define whether an implementation is causal or requires future samples.

Batching is an internal execution decision (agreed), derived from requested models,
hardware capabilities and SkellyTracker's supported mechanisms. Users choose the
work, not GPU batch topology. Preserve logical camera/frame identity and expose
actual batches/providers in execution inspection. Model-declared ordering and
batch compatibility constrain this policy; changing placement must not silently
change scientific results. Existing posthoc already submits camera batches through
the shared inference service (`mocap_detection.py`, `inference_service.py`);
its orchestration constraints must not be confused with an absence of batching.

“Eager” means dispatch eligible work when capacity is available, not launch an
unbounded number of tasks or bypass state dependencies. An accumulator should
be named by its semantics: a keyed join matches camera results for a frame; a
collection waits for explicitly declared coverage. Disk save completion is a
separate event from either form of data readiness. Durable run branching/reuse
governs accepted artifacts, not artificial barriers between every processing step.

The interview settled fixed scientific settings/topology per execution: changing
them starts a new execution that may reuse valid saved results. Independent branches
retain independent outcomes; failed annotation does not erase successful science.

Failure propagation (agreed): complete all work whose declared inputs remain
satisfied. A failed producer blocks dependent work requiring its unavailable
output, not unrelated branches. Never substitute a smaller input set merely
because an algorithm could technically operate on it. A three-camera triangulation
requires all three declared camera results; failure of one does not authorize
two-camera triangulation. Annotation for each successful camera can still finish
and save because its own dependencies are satisfied. Report partial failure and
successful output references explicitly; do not report the whole execution as
successful or discard valid independent products. A valid empty detection remains
distinct from a failed or missing producer result.

Sink acceptance (agreed): eager in-memory computation does not imply permission
to save a scientific product. A scientific save sink validates required coverage,
completeness and validity before accepting that product. If one camera fails
partway through, already-computed triangulated frames do not become a saved
partial scientific result; the incomplete product is discarded. Independently
complete products, such as annotated videos from successful cameras, can still
be saved. This replaces the earlier suggestion to persist partial triangulation.
Input/type/key validation still applies during computation; sink validation is
an additional external-effect boundary, not the only validation in the graph.
Display authority (agreed, 2026-10-11): the backend sends self-describing messages
representing the state it wants displayed. The frontend faithfully reflects each
received update; it does not independently judge scientific validity/completeness
or wait for other results before displaying it. Any completeness, failure or
intermediate-result status is supplied by the backend, not inferred by the client.
Scientific save acceptance remains a separate backend responsibility and does not
gate display. This resolves the display question without adding a client-side
preview approval policy. Temporary storage mechanics remain undecided; temporary
bytes must never be mistaken for accepted scientific output.

Thread/process placement is separate from operation identity. Message transport is
separate from delivery guarantees. Image storage is separate from ownership and
lifetime. Python annotations alone will not enforce our intended contracts; graph
validation and appropriate runtime boundary checks must do so. The client/server
boundary adds reporting and control protocols without changing graph meaning.

Continue the capability audit and interview before implementing the runtime.
Owner clarification on readiness and completion: optional inputs become required
once selected in the graph definition. Ready items may compute before producer
stages finish, but stage success requires all required dependencies to succeed.
Annotation is a terminal sink, joining all requested overlays per camera/frame
and encoding in order; scientific processing never depends on its completion.
Partial annotation videos may be retained as explicitly incomplete debugging
artifacts. This does not authorize accepted partial scientific products or a
successful completion status for an incomplete annotation task.
Owner clarification: scientific veracity is an unconditional requirement, never
a performance trade-off or temporary comparison setting. Coordinate frames are
part of data identity. Private temporary files are permitted; they are distinct
from accepted scientific outputs. Reuse the existing camera-assignment machinery;
its provisional continuation policy requires explicit consideration at scientific
save acceptance. See [the operation inventory and camera-assignment review](operation-readiness-inventory.md).
See [the architecture proposal](typed-dataflow.md), whose unconfirmed choices
remain proposals. No speedup or formal correctness proof is claimed by this note.
