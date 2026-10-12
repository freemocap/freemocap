# Managed annotation workers

Status: recording-owned lifetime confirmed by owner, 2026-10-11; implementation
and focused/full-recording validation complete in the experimental runner.

## Settled requirements

- Annotation remains a terminal graph branch. Its success, failure, admission or
  progress delivery must not be a prerequisite for scientific computation.
- Preserve existing drawing, video encoding and scientific algorithms. Keep the
  realtime pipeline and dependency repositories unchanged.
- Reuse managed worker lifecycle machinery. A process-isolation experiment is not
  justification for a second application-wide worker registry.
- Pass camera observations and source-video identity to annotation work. Load
  pixels inside the annotation worker; do not serialize video frames between
  processes or retain whole decoded videos.
- Distinguish scientific completion from all-requested-products completion. A
  full-run throughput claim includes startup and every requested sink.
- A failed annotation job must not stop healthy cameras or science. Worker owner
  shutdown flags must not accidentally become the recording's global cancel flag.
- Retain the thread execution alternative for controlled comparisons. Leave the
  encoder's current settings unchanged; the single-thread experiment did not
  establish a useful replacement default.

## Decision tree

1. Worker lifetime (settled Q1): **recording ownership**, per owner's explicit
   choice. Start a bounded worker set for the recording; reuse it across that
   recording's camera jobs; release job data after completion and shut every
   worker down when the recording finishes. No workers persist between runs.
   Startup and shutdown are included in full-run timings.
2. Given lifetime, implement the smallest explicit job boundary: recording-run and
   camera identity, source video, requested annotation configuration, observations,
   output destination, and terminal result. Do not duplicate graph definitions.
3. Verify job cancellation and worker death against existing managed-worker
   semantics. No retry may silently publish duplicate or incomplete products.
4. Validate thread/process equivalence and startup-inclusive full graph behavior.

## Concrete checks before promotion

- Two recordings processed successively cannot exchange observations, cancellation
  state, result messages or output paths.
- One annotation failure leaves scientific work and another camera runnable.
- Cancellation during drawing/encoding produces a terminal outcome and closes
  owned video resources. Shutdown leaves no owned worker alive.
- Slow annotation does not hold compute capacity or change scientific readiness.
- Compare all saved scientific channels; verify every annotation's full frame
  coverage and drawing parity. Report numerical, image and encoded-file checks
  separately rather than implying encoded bitstream equality.
- Report worker startup/input-transfer time, scientific finish time, all-sink
  finish time and per-operation durations. Run variants sequentially on the same
  observations and configuration to avoid competing benchmarks.

Existing measurements and their limitations are in [the performance audit](performance-audit.md).

## Implemented boundary

`CameraAnnotationJob` contains one camera's source metadata, observations, tracker
configuration, recording destination and execution identity. `write_camera_annotation`
is the shared numerical/drawing/video operation for both comparison modes.
`RecordingAnnotationWorkers` uses `WorkerRegistry.create_worker` with process mode
and distinct shutdown flags [@skellycamManagedWorkers2026]. Two processes may serve
three camera jobs, but cannot be reused for a different recording execution.

One dedicated duplex connection per worker carries a correlated job/result pair;
no progress subscription participates in completion. Waiting on that result occupies
an annotation handler only. Native worker death fails its current job; surviving
workers remain eligible for other camera jobs. A normal job exception returns an
explicit failure and leaves its worker available. Video resources are closed in
the shared operation's `finally` block.

Process launch happens at recording start. Import/initialization may overlap
tracking; remaining readiness wait is charged to annotation. The graph has no edge
from annotation to science. After all admitted work drains, the recording owner
signals and joins its workers. The full benchmark clock includes launch and cleanup.
The borrowed application registry's global shutdown method is never called.

The application/realtime route is unchanged. The experimental runner owns worker
lifetime; the comparison CLI selects `--annotation-execution process` (default)
or `--annotation-execution thread` for the control. Low-level graph construction
accepts an explicitly owned annotation service and otherwise uses the thread
operation; constructing a graph alone does not launch processes.

## Validation status

The focused worker/graph/scientific suite passes 24 tests. The fresh test-data
thread/process comparison passes all 29 scientific channels with zero numerical
difference and identical encoded-video hashes. See the performance audit for
full-run timings and the longer sample's verification status. Abrupt process
termination can leave an unpublished temporary video; it does not certify or
publish an incomplete result.

The longer sample also passed all 36 saved scientific channels with maximum
absolute error 0.0; all three annotation videos contain 1,108 frames.
