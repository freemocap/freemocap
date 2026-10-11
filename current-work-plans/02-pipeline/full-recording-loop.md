# First complete dataflow recording loop

## Problem and outcome

The experimental route proves loading, tracking and raw triangulation, but cannot
yet produce the reconstructed recording that downstream tools consume. Close that
scientific loop before optimizing or replacing the application's current route.

## Contract

1. Process a complete synchronized multicamera recording using the existing timing,
   inference service, camera assignment and numerical implementations.
2. Retain bounded image queues. Observation and trajectory arrays may span the
   recording; no whole recording of decoded images is retained.
3. Express actual operation prerequisites in the executable definition. Ready
   independent operations may run concurrently; a failed operation blocks only
   descendants. Terminal annotation cannot gate scientific reconstruction.
4. Use existing filtering, measured-support masks, alignment, recording-wide model
   fitting, reconstruction, center-of-mass calculation and canonical serialization.
   Preserve camera-coordinate transformations and saved reference descriptors.
5. Save only complete scientific coverage. Camera-fit warnings follow the existing
   continuation policy and remain observable. Never reduce the required camera set.
6. Compare new and existing scientific completion on identical observations,
   configuration and independent calibration copies. Compare all saved channels,
   their identities, masks and values, not merely whether files exist.
7. Keep the current and realtime routes available and unchanged in behavior. This
   first route is a backend/CLI experiment; application transport/UI follows later.

## Implementation plan

1. Add a small recording-operation executor backed by the typed graph definition.
   Validate handlers and input/output ports before execution. Record operation
   timings, failures and blocked descendants; no UI callback is required to advance.
2. Compose scientific completion from existing primitives: completed tracking →
   camera matching/triangulation → trajectory filtering → reference alignment →
   recording fit/reconstruction → canonical save → requested scientific exports.
   Use recording-level dependencies honestly; do not imply that full-trajectory
   filtering or the current camera matcher operates on isolated frames.
3. Add independent per-camera annotation sinks using the established annotator and
   video writer, rereading pixels so encoder speed cannot retain inference images.
4. Add a runnable full-recording comparison using the existing dataset machinery
   and private output directories, with readable timing and numerical reports.
5. Test scheduling/failure behavior without hardware, then actual scientific
   completion and saved-channel parity using the established reference recordings.

## Acceptance and limits

First acceptance is a complete multicamera human recording, through SkellyForge
reconstruction and canonical output, with numerical comparisons against the current
task. Subsequent configurations must either run explicitly or reject before writing;
no silently ignored options. Detector support at the tracking boundary does not
by itself establish downstream parity. Annotation, export variants and stage-resume
coverage must be reported separately. Blender executable availability is an external
validation prerequisite, not grounds to invent a successful export.

No performance claim without equivalent outputs and measured comparable runs.
Tests should prove independent branches continue after unrelated failure and that
scientific completion cannot be inferred from partial observations. All work stays
unstaged in this worktree; no production route is switched as part of this milestone.


## Implemented first loop — 2026-10-11

- `core/pipeline/dataflow/recording_pipeline.py` composes existing scientific functions
  into the executable graph. `recording_executor.py` dispatches ready operations
  through separate compute, annotation and recording-I/O pools.
- Loading/tracking stream bounded images internally. Their graph output is a complete
  observation collection; automatic matching currently needs that recording-level
  evidence. This is not yet a generic frame-token executor.
- Observation and spatial saves are independent durable checkpoints. Reconstruction
  does not wait for checkpoint I/O. Final save waits for previous writers to finish,
  avoiding concurrent mutation of the same canonical recording.
- Filtering, alignment, dimension fitting and skeleton reconstruction retain the
  existing numerical implementations. The existing combined fit/reconstruct function
  delegates to the extracted fit function and its existing reconstruction function.
- Camera-assignment diagnostics belong to processing metadata, separate from retained
  detector provenance. A regression verifies continued poor fitness, units and camera
  diagnostics survive checkpoint reuse.
- Annotation rereads frames with existing drawing/encoding tools; each camera has an
  independent terminal sink. Two successful cameras still produce videos if the third
  fails. Complete scientific publication remains blocked in that case.

### Evidence

The full 3-camera, 222-frame-per-camera RTMPose/CUDA run passed saved-output comparison:
29 channels, including skeleton landmarks, rotations, joint angles and derived points.
Largest observed channel difference was 9.10e-13; frame/timestamp identities and
missing-value masks matched. Camera/reference/model/fit metadata were compared too.
Graph wall time was 78.902 s; tracking/loading took 22.282 s, fitting 15.428 s,
reconstruction 14.268 s and final recording save 13.621 s. Concurrent operation
intervals are recorded; their durations must not be summed as wall time.

The existing scientific task took 42.963 s on the same observations. These durations
are different workloads: the graph also runs inference, annotations and export.
They do not demonstrate a performance improvement. Local report:
`.test-artifacts/full-recording-loop/test-final/report.txt` and `report.json`.
That run predates the assignment-processing-metadata fix, which has separate
read-back regression coverage. An earlier comparison attempt hit Windows error 1175
while the current path replaced a file; its failed report is preserved in `test-reviewed`.

69 focused unittest tests pass, plus 8 bibliography tests and 17 validated references.
The pytest-based dataset-workflow module could not run because pytest is absent in
this existing environment; no dependency installation was performed.

### Remaining integration work

Keep this experimental route alongside current processing. Next: equivalent-workload
end-to-end benchmarks, downstream detector/export coverage, saved-stage resume, then
HTTP control and nonblocking WebSocket reports. The existing UI is not wired to this
route. Blender export and automatic board discovery are explicitly rejected. Backend
port contracts currently validate semantic compatibility; they are not a complete
runtime Python payload-type registry. Live operation events and finer streaming graph
visibility remain separate work, not implied by the serialized recording graph.


### Longer recording with ChArUco

The full 3 x 1,108-frame sample recording also passed with RTMPose/CUDA, explicit
ChArUco, filtering, body/board reconstruction, NPZ export and all three annotated
videos (each verified as 1,108 frames). All 36 saved channels matched the current
scientific path; maximum absolute difference was 1.37e-12.

| Measured work | Seconds |
| --- | ---: |
| Whole graph, including tracking/annotation/export | 467.664 |
| Current scientific completion on shared observations | 292.548 |
| Load and track | 97.828 |
| Match and triangulate | 60.244 |
| Filter trajectories | 1.477 |
| Align reference | 7.058 |
| Fit model dimensions | 104.960 |
| Reconstruct skeletons | 78.961 |
| Save observations | 34.312 |
| Save spatial checkpoint | 85.696 |
| Save final recording | 90.854 |
| Scientific export | 9.649 |

Annotation durations were 253.973, 249.299 and 120.527 seconds, with two annotation
slots. These overlap scientific processing. The runs establish computational parity,
not a throughput improvement. Whole-recording checkpoint serialization and fitting
are substantial measured costs to investigate in symmetric benchmarks.

Local evidence is `.test-artifacts/full-recording-loop/sample-board/report.txt`,
`report.json`, `graph.json`, and the private output recordings. This run was launched
before the assignment-processing metadata correction; the correction is covered by
the persisted-warning regression, rather than retrospectively claimed for this file.
