# New graph: where the processing time goes

Audit of the preserved 2026-10-12 paired reference runs. No new timing run or
performance change was made for this audit. The old pipeline and its measurements
remain intact. See [paired results](paired-pipeline-results-2026-10-12.md).

## Measurement boundary

Three cameras, 222 motion-capture frames for test data and 1,108 for sample data.
CUDA RTMPose plus ChArUco, annotated videos, Parquet and Blender. No CSV/NPY/NPZ
exports were requested. Calibration was reused. These are single measurements,
not repeated-run estimates or literal UI-click latency measurements.

Evidence: `C:/Users/jonma/freemocap_data/testing/ab/graph/` contains each dataset's
`current/processing.log`; `ab/comparison.json` preserves the configurations and
old/new comparison. Both datasets passed comparison of all 36 saved channels,
with maximum absolute numerical difference zero.

| Elapsed boundary | Test seconds | Sample seconds |
| --- | ---: | ---: |
| Mocap pipeline, including requested exports | 32.629 | 112.250 |
| Entire reference worker lifecycle | 46.107 | 140.824 |
| Reference channel validation after mocap completion (log timestamps) | 5.570 | 19.853 |
| Remaining worker time outside mocap and that validation | 7.908 | 8.721 |

The last row is a residual, not a measurement of one operation. It includes
startup/preflight and other reference-workflow overhead. Do not attribute all
worker lifecycle time to the application's progress bar. UI request receipt,
worker admission, and delivery of the final WebSocket message are not jointly
measured by this benchmark.

## Operation landscape

Handler elapsed time includes any waits inside that handler. It is not CPU busy
time or GPU kernel time. Concurrent rows must not be added together.

| Operation | Test seconds | Sample seconds |
| --- | ---: | ---: |
| Load videos and detect requested points | 10.627 | 47.650 |
| Match cameras and triangulate | 1.818 | 7.665 |
| Fill gaps and smooth trajectories | 0.027 | 0.427 |
| Orient recording coordinates | 0.797 | 3.525 |
| Prepare skeleton input | 0.005 | 0.015 |
| Fit body dimensions | 2.187 | 9.548 |
| Calculate skeleton positions and rotations | 4.913 | 22.786 |
| Prepare detected points for saving | 0.226 | 0.455 |
| Save detected points | 1.256 | 7.484 |
| Prepare 3D points for saving | 0.003 | 0.005 |
| Save intermediate 3D results | 7.283 | 31.069 |
| Save final reconstructed recording | 1.597 | 7.241 |
| Annotate video 1 | 5.224 | 21.930 |
| Annotate video 2 | 5.227 | 21.922 |
| Annotate video 3 | 4.135 | 18.422 |
| Export to Blender, including preparation | 10.151 | 13.090 |

## Tracking: work versus exposed waits

| Within load-and-track | Test seconds | Sample seconds |
| --- | ---: | ---: |
| Tracker process_batch calls | 8.631 | 44.595 |
| Create tracker/session | 1.558 | 1.572 |
| Wait for camera reader batches | 0.018 | 0.054 |
| Inference service queue wait | 0.025 | 0.128 |

The batch calls handle all requested detector stages, including board detection,
pre/postprocessing and CPU work. Calling these numbers GPU-only time would be
incorrect. Batch size is three images; one inference batch is in flight.
Video readers run ahead with bounded queues. Their total decode work is not
measured here: these small waits measure how little loading delays consumption.

Mean batch time is 38.880 ms (test) and 40.248 ms (sample): about 25.72 and 24.85
motion-capture frames/s inside the tracker call. First batches take about 99 ms.
Only 24 body-detector runs were reported in each recording, versus 666/3,324
camera images. The existing bounding-box reuse mechanism is active; the detector
is not being rerun on every image. The logs identify CUDA on the RTX 3090.

## What the dependency structure actually does

`recording_pipeline.py` binds recording-level outputs. Video loading streams into
tracking, but triangulation, annotation and observation saving start only after
the complete tracking collection returns. This is an explicit whole-recording
boundary, not an unexplained scheduler stall.

After tracking, annotation has its own two-process capacity. Cameras 1 and 2 run
together; camera 3 waits for a slot. Numerical work and intermediate saves run
alongside them. `application_pipeline.py` waits for the complete graph and worker
cleanup before invoking application exports.

The preserved logs establish that annotation finished before the final recording
save in BOTH cases. Consequently there is no exposed annotation tail delaying
Blender in these measurements. The all-graph export gate is still a potential
delay in other configurations, but removing it is not a demonstrated speedup here.

Sample timeline, approximate offsets from pipeline creation (progress messages
are sampled; these are not exact scheduler timestamps):

| Event | Elapsed seconds |
| --- | ---: |
| Tracking finished; annotation/triangulation/saving underway | 48 |
| Dimension fitting and intermediate 3D saving underway | 59 |
| Skeleton reconstruction underway | 69 |
| Last annotation finished | 88 |
| Intermediate 3D save finished | 91 |
| Skeleton reconstruction finished; final save begins | 92 |
| Final save finished; Blender begins | 99 |
| Pipeline complete | 112 |

The 31-second intermediate save is mostly overlapped with fitting/reconstruction.
Removing 20 seconds from that save does NOT imply 20 seconds off total latency.
However, shared CPU/memory/GIL contention may slow its neighbors; this run alone
does not prove or quantify that contention. Test data's intermediate save ends
about 0.16 seconds after reconstruction; sample's ends about 1.3 seconds before it.

## Highest-value next experiments

1. **Separate intermediate-save cost from interference.** Replay identical saved
   inputs using existing component diagnostics: save alone, reconstruction alone,
   then concurrent. Compare both operation times and their combined completion
   time. Validate identical saved channels. The 31.069-second save is a lead, not
   proof of slow disk bandwidth. Existing validation reports zero scalar fallback
   rows; the save still includes construction, validation and publication work.
2. **Connect the remaining batched skeleton math.** Core's
   `core/reconstruction/posthoc_reconstruction.py` still loops through frames in
   both fitting and reconstruction. Measure these separately (9.548 and 22.786
   seconds for sample). Preserve stateful temporal calculations and measured-only
   fitting evidence; do not replace them with a different scientific computation.
3. **Break down tracker batch work by detector/preprocessing/inference/postprocessing.**
   It accounts for 44.595 seconds of the sample run. Camera waits and service queue
   waits are too small to explain that cost. Compare any change against the same
   RTMPose + ChArUco configuration, not an unmatched realtime workload.
4. **Measure Blender preparation separately.** Logs show roughly 3.3 seconds of
   preparation before actual export in each pipeline, plus a reference preflight
   before pipeline creation. Check safe reuse of verified preparation. Do not count
   reference-only duplicate preflight as an application regression.
5. **Measure actual click-to-complete separately from reference validation.** Keep
   reference validation; label it as test overhead. Record request admission and
   final server completion using the same run ID before making UI latency claims.

## Observability gap

The executor already captures operation start/end times in memory, but the app
persists only handler duration summaries. It does not persist dependency-ready,
resource-admitted or worker-start timestamps as a timeline. Thus exact dependency
wait versus resource queue wait cannot be recovered retrospectively. Annotation
workers also already collect detailed job and startup measurements that the app
does not include in its performance summary. Preserve these existing measurements
in the next diagnostic run rather than building a second scheduler or profiler.

No performance behavior was changed in this audit. The next optimization should
be judged on whole-run latency and numerical parity, not merely a faster isolated
row or the sum of overlapping rows.
