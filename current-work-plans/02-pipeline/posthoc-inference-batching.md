# Post hoc inference batches and frame storage

Design investigation, 2026-10-12. No runtime implementation changes.

## Performance principle

Prefer bounded, vectorized operations over repeated Python scalar work where
inputs are independent. Preserve numerical behavior, temporal dependencies and
memory bounds. Broadcasting that creates large intermediates, or merely wrapping
a Python loop, is not an improvement by definition. Measure the complete operation.

## Existing storage and inference contracts

SkellyCam's frame dtype is an aligned record containing `frame_metadata` and an
`image` uint8 `(height, width, channels)` field. Its multiframe dtype has one field
per camera and permits differing image shapes. Pixels of an individual image are
dense, but consecutive records have metadata between images; an image-field view
across records generally has a stride larger than the image byte count. Ring
wraparound adds another boundary. Existing ring reads use `np.copyto`; this is not
an existing zero-copy GPU batch [@skellycamFrameStorage2026].

Shared memory avoids serialization across processes. Threads already share their
arrays. Neither makes ordinary NumPy memory GPU-resident or automatically pinned.
ONNX Runtime copies CPU inputs to the device during Run; I/O binding enables
explicit device buffers but does not eliminate the initial necessary transfer
[@onnxruntimeIoBinding].

The installed `OnnxSession.run_batched` stacks preprocessed float32 `(3,H,W)`
tensors into `(N,3,H,W)` with `np.stack`, then makes one inference call. The higher
`Tracker.process_batch` API has one frame number/timestamp for the whole batch,
and dictionaries keyed by camera. It cannot currently express multiple frames
of the same camera with their actual identities. Merely inventing camera keys
would break temporal-state ownership [@skellytrackerBatchSessions2026].

Inspection also confirms DetectionStage refreshes keypoint-derived boxes from
this frame's pose; the next crop can depend on that result. Its batched path
synchronizes detector refresh across cameras if any camera needs it. MediaPipe
VIDEO mode has stream-local state. Arbitrarily batching future frames would
therefore change current scientific behavior, even if results were sorted later.

## Proposed distinction

A scientific item has recording/run, camera, frame and detector-stage identity.
An inference batch is an execution choice containing compatible **ready** items;
it is not a synchronized motion-capture frame. Results retain their identities.
Triangulation joins all required camera observations by validated frame identity.
Per-stream state updates remain ordered. Batch formation has a memory limit and
flushes incomplete tails without dropping or fabricating observations.

Independent pre-established crops or stateless inference permit batching across
time. Current pose-derived crop feedback generally limits readiness to the next
frame of each independent camera stream for that model. Removing synchronized
frame-number admission alone does not unlock arbitrarily large batches. Changing
to every-frame detection, frozen boxes or predicted multi-frame crops is an
algorithm change requiring separate scientific evaluation, not a parity-preserving
scheduling optimization.

A possible data path is bounded frame loading, exact crop/resize preparation into
reusable model-input buffers, compatible ready-item inference batches, then
identity-based result distribution and ordered state updates. Parallel loading
and preparation can overlap inference where dependencies allow. Buffer ownership
must prevent reuse or ring overwrite until every consumer is finished.

## Measurements before implementation decisions

1. Replay fixed preprocessed inputs through supported batch sizes (for example
   1, 3, 6, 12, 24, 48) with the same model and precision. Check actual model batch
   dimension support. Measure completed-call throughput and numerical outputs.
2. Include crop/resize, normalization/layout conversion, stacking, host-to-device,
   kernels and output handling in a second measurement. Separate startup/warmup.
3. Measure peak host/device memory and tail batches. Choose the best measured
   throughput with headroom, not the largest batch fitting VRAM. NVIDIA explicitly
   notes cache-related exceptions to larger-is-faster [@tensorrtBatchSizing].
4. Compare the legal ready-work population under unchanged tracking behavior with
   the model's preferred batch size. This distinguishes GPU capacity from a real
   temporal dependency limit. Preserve detector refresh decisions for parity.
5. Rerun scientific parity and report seconds per motion-capture frame end to end.

Prior quaternion microbenchmarks do not predict neural-network speedup: ONNX
already executes tensor kernels. The opportunities here are batch utilization,
preparation and transfers. No speedup for larger post hoc batches is claimed yet.

## Proposed offline crop planning — 2026-10-12

User proposal: separate sparse person detection and crop planning from large-batch
pose inference. This deliberately changes crop generation, so exact old-pipeline
numerical parity is not expected. Scientific validation remains required.

Suggested experiment, not implemented:

1. Establish a cheap upper-bound opportunity first: replay fixed crops at larger
   model batches. If inference hardly improves, elaborate crop planning is not
   justified for speed alone.
2. Compare dense batched person detection, uniform sparse detection with margins,
   and adaptive interval refinement. Include total decode cost and retries.
3. For adaptive refinement, detect initial anchors, associate the same person,
   propose intervening boxes, and inspect midpoint detections. Batch midpoint
   queries from independent intervals. Split on disagreement, confidence failure,
   identity ambiguity or a maximum temporal gap. Retain a minimum gap and dense
   detection fallback; do not interpolate through unresolved absence/occlusion.
4. Consider a padded union box per short interval before more elaborate smooth
   trajectories. Larger crops reduce clipping risk but reduce effective subject
   resolution at fixed model input size; endpoint unions do not guarantee that
   intermediate motion stays inside. Midpoint agreement is also not proof.
5. Finalized intervals can emit per-frame crop transforms into bounded pose
   batches, preserving recording/camera/frame/person identity. Temporal filters
   consume ordered outputs; triangulation joins by camera/frame identity.
6. Flag questionable poses for explicit crop revision and rerun. Confidence alone
   is not scientific validation; compare annotated image evidence and independent
   quality metrics, including 3D/reprojection and coverage. Record crop revisions.

This is adaptive temporal subdivision, not ordinary binary search: arbitrary
motion has no monotonic predicate. A person can leave and return between every
sampled endpoint and midpoint. Without additional assumptions/evidence there is
no logarithmic guarantee of correct full-video crop coverage; worst-case detector
work is linear in frame count. Optical flow or cheap intermediate image checks
can supply evidence, but add costs and failure modes.

Related research demonstrates sparse expensive keyframe computation with flow
propagation, but is not this proposed box planner and proves no guarantee for it
[@zhuDeepFeatureFlow2017]. Decode sampled compressed-video frames carefully:
random seeks and a second pass may cost more than sequential reads. Retain box
metadata for the recording and bounded pixel buffers, not every decoded image.
The existing measured detector count was already low (24 camera-image detections
among 3324 images in one run); the proposed benefit is primarily removal of the
pose-to-next-crop dependency, not just fewer person detections.
