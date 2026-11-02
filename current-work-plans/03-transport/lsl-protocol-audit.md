# LSL implementation audit — 2026-11-02

The lifecycle fix is verified with native local sockets. The present36-outlet
layout is a project choice, not an LSL requirement or the preferred grouping
recommendation. A grouped-layout follow-up is recommended below; this fix does not
silently change existing stream schemas.

## Source-to-decision audit

| Area | Official guidance / installed behavior | Project decision and evidence |
| --- | --- | --- |
| Discovery | Outlets advertise through UDP; inlets subscribe over TCP. [@lslUserGuideDiscovery] | Prepare outlets before admitting frames for transmission. LabRecorder Update discovers them; subscription is separate from saving a file. |
| Receiver readiness | have_consumers is nonblocking; wait_for_consumers is available; pushing without consumers is unnecessary but not prohibited. [@lslOutletConsumerReadiness] | Use per-outlet have_consumers. Do not block the worker while its upstream queue fills. Partial selection works, including provenance independently. Waiting is a project lifecycle policy, not a claim that missing subscribers caused LSL itself to block. |
| Buffering | For irregular streams max_buffered is in100-sample units. Chunk size0 sends each push as a chunk. [@lslOutletConsumerReadiness; @pylsl1186InstalledWheel] | max_buffered1 means100 samples, not one second. This is separate from our8-frame output queue. No queue enlargement: preparation frames and wholly unsubscribed frames are counted separately, without retaining historical payloads. Connected overload still fails explicitly. |
| Clock | LSL timestamps belong to its monotonic local clock; receiver clock correction/XDF import are separate. [@lslTimeSynchronizationGuide] | Map original SkellyCam perf_counter_ns by a measured same-host clock anchor, never delivery time. Preserve original camera/source nanoseconds as decimal strings. Native checks disable inlet post-processing and compare timestamps directly. No raw SkellyCam value is changed. Long-duration cross-clock drift remains unmeasured. |
| Numeric layout | FAQ recommends a common numeric vector for compatible values and warns that multiple streams with shared timestamps complicate receivers. [@lslNumericGroupingFaq] | Current one-outlet-per-channel-block facilitates per-block selection, but duplicates metadata and adds startup/receiver cost. It is valid API usage, not the documented preferred layout. |
| Copies/chunks | Installed1.18.6 push_sample constructs a ctypes array; push_chunk accepts contiguous NumPy arrays through its pointer path. [@pylsl1186InstalledWheel] | np.frombuffer avoids our initial decode copy, but current push_sample is not zero-copy. Existing measured all-connected throughput is sufficient; a grouped numeric vector should benchmark the public NumPy chunk path. No batching may replace individual acquisition times with estimated times. |
| Metadata | Channel count/format and descriptive XML stay fixed for an outlet lifetime. Resolver metadata is partial; inlet.info retrieves the full description. [@pylslInfoSource; @lslOutletConsumerReadiness] | Labels, row/component identities, units, model metadata, camera identities and image size remain explicit. Equal immutable metadata is reconciled once per model; changed row order still fails validation. Overlay coordinates are pixels even when3D quantities are millimeters. |
| Recording | LabRecorder Update lists streams, selected streams are saved after Start, and XDF preserves synchronization information. [@labRecorderWorkflow; @lslTimeSynchronizationGuide] | Connected never means recording to disk. Preserve XDF and compare numeric samples, frame IDs, exact provenance and raw clock mapping before scientific acceptance. This audit did not validate an XDF file. |

## Measured lifecycle evidence

Canonical Python uses pylsl1.18.6/native liblsl118 (v1.18.0.b6). The isolated native
harness runs real composition for4 cameras, human and board models at20fps, with
fresh but equal metadata objects and simultaneous CBOR encoding. It advertises36
outlets. Latest socket-enabled result: readiness4.215s; all36-connected pushes
average0.968ms, maximum1.305ms; queue peak4 of8; zero overflows, drops or source
frame gaps. Thirty numerical/provenance pairs match values and acquisition time.
Partial subscription, independent discovery, disconnection returning to waiting,
and release of all owned outlets/workers pass. Preparation excluded85 frames
explicitly; these are not connected-recording losses.

An8-frame queue covers only0.4s at20fps. The old lifecycle admitted frames during
multi-second advertisement; the new phase prevents that startup backlog. Earlier
sandbox-native timings understated real socket costs and are not readiness proof.
Equal metadata identity churn also reproduced sustained overflow before cache
reconciliation; that separate controlled case is not proof that live metadata churn
caused the user's particular failure.

Evidence in the W6 isolated checkout, under `.test-artifacts/streaming-outputs/`:
`lsl-native-readiness.py`, `lsl-native-readiness-result.json`. The harness requires
normal local socket access; restricted Windows socketpair setup stalled before the
async test began. Canonical regression XML: `lsl-readiness-regression.xml` in the
same relative artifact directory.29 tests passed,1 native opt-in test skipped,
2 reference-data cases deselected; native harness evidence is separate. Four UI
status/control tests pass. No camera, GPU, app restart, installation or Git mutation
was performed by this work.

## Live status evolution regression

A real-composer sequence with generated support false, true, then false reproduced
another startup failure. The first changing identity was standard_human instance0,
MAPPED_KEYPOINTS_3D: labels, units, sample_status_appended and sample_status_labels
changed because MessageComposer conditionally supplies temporal statuses. Changing
fitted_scale_mm independently did not change the outlet schema. This reproduces a
producer/adapter incompatibility; the short passive live capture contained no pose
instances and did not establish the exact transition in the user's failed run.

LSL projection version2 reserves one status value per row after all original numeric
components. It imports TEMPORAL_STATUS_LABELS from the existing source contract.
NaN means the source did not declare a row status; it never means current input or
an inferred measurement. Metadata describes this layout and absence meaning.
Per-frame provenance lists status_declared_channel_identities. Original numerical
values, units, row order, exact source nanoseconds and mapped acquisition timestamps
are unchanged. Status vocabulary, row, unit and model-definition changes still fail
explicitly; schema errors identify the channel and changed fields. No source producer
or HTTP/SDK schema changed.

The focused suite passed31 tests, with1 opt-in native skip and2 reference cases
deselected. A separate socket-enabled native run repeated the status sequence while
fitted scale evolved at20fps:36 outlets connected,30 matched numerical/provenance
pairs,66 emitted frames, zero source gaps/drops/overflows, queue peak1 of8. Readiness
was3.784s; all-connected emission averaged1.852ms and peaked2.551ms. Disconnection
returned to waiting and all owned outlets/workers closed. See isolated artifacts
lsl-native-status-evolution.py and lsl-native-status-evolution-result.json and the
canonical lsl-status-evolution-regression.xml.

## Optional channel availability

The actual JointAnglesProducer also reproduced a second failure: its channel is
absent when no joint-angle payload exists, then appears when reconstruction supplies
angles. The adapter now retains an advertised outlet across source absence and
publishes no numerical sample for that missing block. Reappearance reuses the same
outlet identity and must pass its original row, unit, model and status-vocabulary
validation. A newly declared channel gets its own outlet from the actual source
schema; no row names or missing angles are invented.

Late advertisement runs on one owned worker with one waiting batch. Frozen descriptor
snapshots contain metadata, not historical frame payloads. Existing channels continue
while new outlets are prepared. Queue saturation is explicit in provenance; deferred
channels retry only when a later source frame declares them. Coverage distinguishes
available, absent, preparing, deferred, published and unsubscribed identities. Connected
receivers with temporarily absent data are not counted as missing receivers.

Stop and source replacement cancel queued work, wait for an in-flight constructor,
and release results before changing the source/session. Cancellation cannot interrupt
a blocking native constructor. Tests cover this wait, stale-result rejection, duplicate
prevention, queue saturation, advertisement errors and cleanup. Outlets remain alive
for the pipeline lifetime; a late outlet must be selected by the receiver. Discovery
alone does not establish that an ongoing LabRecorder recording includes that outlet.

The final native sequence used 36 initial outlets and added JOINT_ANGLES later, with
all 37 connected. It verified 23 present joint frames against original values/statuses,
12 absent frames with no fabricated sample, and 30 other numerical/provenance pairs.
The joint outlet identity stayed unchanged. Readiness was 3.358 seconds; connected
emission averaged 2.053 milliseconds and peaked at 2.782 milliseconds. Queue peak was
1 of 8, with zero output drops or overflows. One source scheduling gap (index 1 to 3)
occurred during initial preparation, before receiver connection, and remained visible
in counters. Disconnect returned to waiting. Both an initial outlet and the late outlet
became undiscoverable after cleanup, and all owned workers ended. Artifacts are
lsl-native-availability.py and lsl-native-availability-cleanup-result.json in the
isolated checkout's ignored streaming-outputs directory; the earlier availability
run is retained separately.

Final focused validation enabled native sockets and the existing processed test-data
reference: 40 tests passed with no skips. Native reference replay compared 221 connected
samples and 82,212 numerical values across 222 recorded frames. The second processed
sample-data reference passed both checks: 1,107 connected samples and 411,804 values
across 1,108 frames. Both preserve the recorded relative-time grid with an explicitly
chosen replay origin, not a claim of recovered historical hardware timestamps.
Canonical reports are lsl-availability-reference-regression.xml and
lsl-availability-sample-reference.xml. Citation validation passed 70 entries with no
errors. This is local adapter/receiver evidence; actual user-directed live/XDF
acceptance remains open. No producer, frontend, HTTP or SDK interface changed in this
follow-up, and W6 did not restart the app or use cameras/GPU.

## Recommended grouping follow-up

Prefer one coherent float32 numerical sample per selected source frame, plus its
exact-nanosecond string provenance stream. The numerical layout should declare
block offsets, shapes, channel kinds, model/instance/camera identities, row/component
labels and units in complete metadata. Current numeric payloads and small status
codes fit float32 without new loss; source nanoseconds must not be squeezed into
float32 or float64. Apply requested channel/model filters before fixing that layout.
A small number of model-level streams is an alternative if independent model
subscription has demonstrated value. [@lslNumericGroupingFaq]

This would reduce startup/discovery and timestamp-join complexity, but changes
receiver selection and needs a versioned layout contract and decoding tests. It is
not implemented in this bounded lifecycle fix. Do not describe36 outlets as best
practice, or infer measured palm contact/pose validity from successful transport.
Remaining acceptance: combined SDK/UI integration, coordinator-controlled restart,
user-directed LabRecorder/XDF test, long-duration synchronization and platform checks.

## Accepted live viewing and saved recording — 2026-11-02

The user confirmed Nexus Dynamics LSL Viewer and the streamer are working; the
coordinator closed live-viewing and saved-recording acceptance. The actual XDF
contains 37 streams with 158 samples each over 8.991 seconds. Raw timestamps,
footer counts, published identities and status declarations reconcile without
additional missing recorded samples. Its 112 internal skipped frame-number slots
were already reported by the sender; numerical missingness/support estimates do
not imply LSL packet loss or establish anatomical accuracy. The original ZIP is
unchanged. Detailed evidence is in the W6 isolated checkout's ignored
.test-artifacts/streaming-outputs/xdf-review/index.html and summary.json.

This acceptance supersedes earlier open-live/XDF statements above. The LSL blocker
is retired. Grouping remains a future proposal, with no new redesign authorized.
Broader platform/long-duration work belongs to later compatibility validation.
