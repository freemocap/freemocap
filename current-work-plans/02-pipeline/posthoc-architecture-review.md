# Mocap/posthoc architecture review

Status: planning and alignment, 2026-09-06. Review before the next implementation chunk.
This is a navigation and decision guide, not a new data model or implementation specification.

## Task and execution mode

| Task | Realtime | Posthoc |
| --- | --- | --- |
| Mocap | Implemented; shares scientific computation with posthoc | **Current architecture/refactor scope** |
| Calibration | Not implemented; deferred | Existing separate task; not being redesigned here |

Task and execution mode are independent axes. Other tasks may be added later; do not build a
framework for hypothetical tasks now. The mocap interface may launch calibration/posthoc first,
then load its geometry artifact. That does not make calibration a mocap stage. Shared media/input
improvements may benefit both tasks without merging their lifecycle or scientific responsibilities.
The current realtime pipeline is mocap/realtime even where the implementation omits that qualifier.

## Purpose and scope

A recording describes a captured volume and its observations. People, boards, animals and other
objects are possible subjects; no singular human/tracker is the recording's defining entity.
The goal is a coherent posthoc path that shares scientific computation and vocabulary with realtime,
while allowing inspection, partial processing, reprocessing and deliberate retention of results.

Playback is accepted for the current checkpoint. Its bundle/cache implementation is a consumer,
not the authority for future recording structure. The misleading blue Charuco missing-corners
annotation is deferred; inspect board definition, observation IDs and frame association later.

## Settled boundaries

- Recording folder name is recording_id. Do not introduce a second take/session hierarchy.
- Recording metadata describes capture/context; numerical measurements and model outputs do not
  belong in recording_info. Model definitions needed to interpret results belong with those results.
- Parquet uses long component/value rows and existing self-describing channels/ontology as its
  starting point. Exact descriptors, column semantics and storage layout remain reviewable.
- No separate timing Parquet. Timing must remain interpretable alongside measurements.
- Current mocap video groups are synchronized upstream: identical frame counts, one shared ordinal,
  no cross-video FPS comparison. Missing timestamp files permit inferred frame-number/FPS timing.
- Across future independent sensor groups, timestamps are the shared temporal coordinate;
  frame_number is local to a group. This does not authorize asynchronous mocap video playback.
- Calibration is a separate task producing camera geometry. Mocap consumes geometry only when a
  requested operation requires it. Downstream-only work and suitable single-camera work need none.
- A worker failure fails its pipeline, not the app or unrelated pipelines. Cancellation is scoped.
- Keep/overwrite is deliberate user choice, not automatic retention of every intermediate attempt.
- Reuse existing domain models; do not reshape geometry, fits or definitions into redundant wrappers.
- Remove superseded code when migrating callers. No editable dependency substitutions or Git mutations.

## Distinctions to preserve

| Concept | Meaning | Must not be inferred from |
| --- | --- | --- |
| Media file | Stored bytes, file properties and location | A physical camera identity |
| Capture source | Origin of an observation sequence within a recording | Current device enumeration order |
| Physical camera | Device/optical viewpoint, with evidence about identity | A convenient filename or array index |
| Sensor group | Shared sampling sequence and synchronization contract | Tracker/model identity |
| Calibration assignment | Explicit binding of capture sources to existing geometry | Accidental dictionary ordering |
| Observation | Tracker output with its sampling and spatial context | A completed reconstruction |
| Reconstructed instance | A modeled subject/object and its computed state | The entire recording |
| Reference frame | Coordinate system in which a value is expressed | Which process produced it |
| Processing result | Outputs selected for use or deliberate retention | Every worker invocation or retry |
| Export | Regenerable representation of selected saved results | Canonical recording metadata |

These are semantic distinctions, not instructions to create one class/table/ID for every row.
Reuse existing types where they already express the distinction.

## Walk the full path

| Boundary | Required meaning | Review question |
| --- | --- | --- |
| API request | Requested task, inputs, processing scope and retention choice | Does the request describe intent without requiring client knowledge of worker internals? |
| Input resolution | Available media, timing, observations and geometry bindings | What is known, missing, contradictory or explicitly assigned? |
| Stage planning | Required computations and reusable completed results | Which actual input changes invalidate which outputs? |
| Execution | Existing sub-repo algorithms with appropriate scheduling | Is FreeMoCap orchestrating rather than duplicating domain computation? |
| Publication | Coherent completed results with interpretation metadata | What is visible after success, cancellation or failure? |
| Persistence | Recording context, observations/results and their relationships | What is authoritative, and what can be regenerated? |
| Playback/export | Views of selected media/results | Can consumers function without imposing today's folder names or API payload shape? |

Realtime and posthoc should share data meaning and numerical operations. Their scheduling differs:
realtime may prioritize recent work; posthoc processes required samples deterministically. Do not
inherit held observations or latest-frame dropping when implementing exact-frame playback.

## Current implementation versus target

The app completes posthoc processing and supports client playback. Existing plans describe retained
integer run IDs, stage checkpoints and Parquet descriptors; treat their specific representation as
an implementation under review, not justification for more infrastructure around it.

The recording-data-model proposal's directory tree is provisional. Its passages assigning group
clock metadata to recording_info need the capture-versus-derived distinction applied: capture facts
may belong there; processing-derived alignment belongs with the corresponding result. Existing
plans naming default exports do not authorize rebuilding exports before their contract is reviewed.

Playback now consumes a shared bundle. That bundle is an API view, not a new scientific entity or
on-disk manifest requirement. A request-scoped inventory can avoid repeated probing without becoming
a permanent duplicate recording model. SkellyCam probing is integrated in some playback callers;
raw timing association, filename-stem collisions and explicit derived-media links remain unresolved.

## Recommendations needing agreement

1. **Recording organization:** separate capture context from observations/results and optional exports
   conceptually first. Choose concrete directories/files after agreeing their contents and lifetimes.
2. **Media relationships:** identify media without parsing camera IDs. Persist source/derived-video
   associations explicitly at creation; arbitrary imports can remain unresolved until an operation
   requires the association. Manual matching precedes any geometric search implementation.
3. **Result descriptors:** keep units, coordinates, model interpretation and necessary input bindings
   with the outputs they describe. Avoid a general provenance/event-history framework.
4. **Stage reuse:** define a small dependency table against concrete inputs before changing checkpoint
   APIs. Decide whether keep retains an independently readable result, and what overwrite invalidates,
   using worked examples rather than inventing more lifecycle IDs.

## Proposed review order and examples

First agree the distinctions above. Then review one request end to end using:

- Imported synchronized videos without timestamps: inferred timing, observations permitted without
  calibration; triangulation waits for a valid geometry assignment.
- A calibration recording with sparse board detections: inspect saved observations independently of
  solve success; absence of a detection is not an application crash.
- Existing observations with different geometry: reuse detection, recompute affected geometry outputs.
- Existing reconstruction with different model/measurement settings: identify the earliest affected
  computation rather than rerunning image detection automatically.
- Keep versus overwrite after a failed stage: identify exactly which completed result remains readable.

For each example, specify API intent, stage inputs/outputs, files published and failure visibility.
Only then settle the minimal media relationship representation and migrate callers. Resume recording
row/descriptor review after those dependencies are explicit. Camera permutation search, broader
export formats and overlay consolidation remain separately scoped follow-ups.

## Implementation gate

The user approved proceeding in bounded chunks on 2026-09-06; unresolved choices are discussed as they arise. The next agreed chunk should name the
boundary being changed, its owning repo, the concrete obsolete callers to remove, and one useful
acceptance scenario. Keep the plan proportional; no generic workflow engine or universal asset graph.
