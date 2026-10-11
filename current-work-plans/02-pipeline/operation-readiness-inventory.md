# Posthoc operation identity and readiness inventory

Audit: 2026-10-11, isolated typed-dataflow worktree. This is code evidence and
an interview agenda, not an implemented graph contract. Numerical parity remains
the first comparison target. See [settled decisions](dataflow-foundations.md).

## Scientific operations

Source paths below are relative to the repository root.

| Operation | Data and identity | Actual readiness / ordering | Evidence |
| --- | --- | --- | --- |
| Load video frames | Video source, source frame ordinal, image dimensions, timing | Ordered reader per video; cameras can progress independently | `freemocap/core/pipeline/posthoc/mocap_video_node.py` |
| Track observations | Camera/frame, tracker/model identity, named keypoints | Model-specific state ordering; camera batches are execution policy | `freemocap/core/pipeline/inference_service.py` |
| Resolve timing | Source frame selection, camera timelines, group timeline | Current selection must match declared video range; recorded group timestamps or mean camera times | `freemocap/core/reconstruction/recording_timing.py` |
| Assign camera geometry | Video source IDs, calibration models, sampled observations | Current matcher samples across the recording including the final frame; assignment can require late evidence | `freemocap/core/tasks/calibration/camera_matching/posthoc_matching.py` |
| Triangulate | Matching frame observations from declared cameras, named points, resolved geometry | Frame-local once geometry and all required messages exist; missing detections are valid data, not producer failure | `freemocap/core/tasks/triangulation/triangulator.py` |
| Single-camera projection | One camera observation | Distinct planar operation with pixel units; not metric multicamera triangulation | `freemocap/core/reconstruction/posthoc_reconstruction.py` |
| Fill trajectory gaps | Points, timestamps, measured-support provenance | Future evidence required for interpolation; imputed values must remain distinguishable from measured support | `freemocap/core/reconstruction/trajectory_gap_filling.py` |
| Filter trajectories | Points, timestamps, filter settings | Current zero-phase filtering needs completed trajectory runs; rate uses median recording intervals | `freemocap/core/reconstruction/posthoc_filtering.py` |
| Estimate reference alignment | Raw/filtered points, measured support, geometry, ground/model settings | Current recording-wide evidence determines a common transform of points and geometry | `freemocap/core/reconstruction/mocap_alignment.py` |
| Fit model scale | Measured-supported points and named model | Recording-wide evidence; fit frozen before reconstruction | `freemocap/core/reconstruction/recording_reconstruction.py` |
| Reconstruct skeleton | Aligned points, frozen fit, model identity | Per-model chronological roll state; models may be independent | `freemocap/core/skeletons/reconstruct_skeleton.py` |
| Calculate biomechanics | Reconstructed landmarks, mass/COM definitions | Current COM calculation is frame-local; stage name alone does not imply temporal dependence | `freemocap/core/skeletons/reconstruct_skeleton.py` |
| Reprojection | Geometry, observed pixels or reconstructed points | Distinguish triangulation residuals from reconstructed-model projection and video drawing | `freemocap/core/tasks/triangulation/triangulator.py` |
| Save scientific products | Complete declared coverage, schema, provenance, validation | Acceptance barrier for that product only; incomplete scientific product is not accepted | `freemocap/core/pipeline/posthoc/saved_stage_processing.py`; owner decision |
| Save annotated videos | Per-camera images and requested overlays | Independent per-camera completeness; ordered encoding, no reason to gate unrelated scientific work | `freemocap/core/pipeline/posthoc/mocap_video_node.py`; owner decision |

## Identity boundaries

- Camera source identity and calibration camera identity are distinct; matching
  establishes their association. A filename is not proof of geometry assignment.
- Group frame ordinal, per-source frame ordinal and timestamp are distinct.
  Equal timestamps must not be invented as the join condition.
- Existing saved samples already carry run/group/source/reference/channel,
  named element/component and frame axes, with explicit timestamps and units:
  `freemocap/core/recording/sample_encoding/arrow_schema.py`.
- Source naming and camera-group construction already exist in
  `freemocap/core/recording/result_processing/observation_inputs.py`.
- Shape alone is insufficient for port compatibility: point namespace, model,
  coordinate frame, units, timing domain and provenance can change meaning.
- A completed empty observation, a failed operation and an unavailable dependency
  must remain distinct. Requiring every camera message does not require every
  camera to detect every point.

## What may block what

Data evidence, declared state order and bounded resource capacity may delay a
consumer. A save or display operation must not become a scientific dependency
unless its actual output is required. Whole-record scientific evidence is not
the same as waiting for a stage to be saved.

Current full-record observation collection, checkpoint writes before downstream
work and annotation completion before the next detection iteration are existing
coordination choices, not automatically scientific requirements.

Transport also needs explicit guarantees: current pubsub includes blocking puts
and lossy subscriber delivery; current shared image rings do not provide arbitrary
multi-consumer leases. Reuse infrastructure only with an appropriate delivery and
lifetime contract. Telemetry must never become a prerequisite for computation.

## Interview round 1 — resolved by owner

Scientific veracity is mandatory throughout development, not merely a first
comparison target. Preserve scientific behavior; performance never authorizes
invalid scientific output. Private temporary files are permitted and are not
accepted scientific products. Coordinate frames are part of data identity.
Reuse the existing camera-assignment mechanism; review its actual behavior before
settling the new graph's acceptance policy. The recommendations below were the
questions asked, not permission to weaken scientific requirements later.

1. Preserve current recording-wide scientific evidence requirements for the first
   parity target, exposing them as explicit dependencies? Recommendation: yes;
   alternative numerical algorithms belong to separately measured changes.
2. Treat resolved source-to-calibration assignment as an explicit prerequisite,
   supplied from validated existing data or produced by the current matching
   policy? Recommendation: yes; never bypass matching merely for earlier progress.
3. Make reference-frame identity explicit on scientific data and show alignment
   as an operation rather than hiding it inside a stage? Recommendation: yes;
   prevent mixing raw/aligned data or applying a transform twice.
4. Permit private temporary disk storage before save acceptance, with incomplete
   products never exposed as accepted outputs? Recommendation: yes, with cleanup
   ownership and failure state explicit; this avoids unbounded memory retention.

After these answers, refine exact work keys, stream completion/failure signals,
buffer ownership and sink transaction boundaries. Do not implement the scheduler
until the resulting contracts have been reviewed with the owner.

## Camera-assignment check-in

Reviewed `matching_models.py`, `matching_evaluation.py`, `matching_fitness.py`,
`posthoc_matching.py` under `freemocap/core/tasks/calibration/camera_matching/`,
and the caller in `freemocap/core/tasks/mocap/posthoc_mocap_task.py`.

1. The recorded adapter samples uniformly across the full recording, including
   the final frame (normally up to 24 samples). Source IDs matching calibration
   IDs provide an initial assignment. Source identity remains distinct from
   calibration identity; camera models are not renamed or recalibrated.
2. Samples alternate between search and held-out validation sets. Evidence must
   connect the source set; candidate assignments require matching image sizes.
   The adapter rejects sampled frames containing multiple detected instances
   rather than assuming detector-local instance order establishes correspondence.
3. The initial assignment passes only when both sample sets have acceptable
   geometry fitness. Otherwise a bounded assignment search finds a candidate,
   evaluates held-out fitness and checks separation from the runner-up.
4. Fitness triangulates without outlier rejection, so a bad camera cannot simply
   disappear from the test. It checks ray conditioning, finite reconstruction,
   positive depth and per-camera reprojection error. Default thresholds include
   90% valid fraction, median error <=2 and p90 <=5, expressed in pixels scaled
   to a 1000-pixel image diagonal, not native image pixels. These are acceptance
   criteria, not proof of all downstream scientific accuracy.
5. Outcomes distinguish initial_accepted, matched, disabled, insufficient,
   ambiguous, poor and search_limit. Current default failure policy is CONTINUE:
   `resolve` permits a provisional assignment if one exists. STOP rejects the
   uncertain statuses but still allows DISABLED. Missing assignment always fails.
   Existing `test_posthoc_matching.py` explicitly tests provisional continuation;
   tests were inspected, not executed in this documentation audit.

Owner decision: distinguish compute continuation from scientific save acceptance
when assignment is provisional or checking is disabled. Block
acceptance of dependent 3D scientific products until assignment has acceptable
evidence (or an explicitly defined validated alternative); continue independent
2D/annotation work. Do not silently copy CONTINUE into sink acceptance, and do not
represent DISABLED as verified. Exact evidence for a validated alternative remains
to be specified if that path is wanted.

## Next contract — draft for review

Reuse existing recording descriptors and timing definitions rather than create a
competing scientific identity schema. Keep execution-attempt identity separate
from saved run identity: runtime events and stale messages must be attributable to
the actual execution, including when a saved run is overwritten or reused.

Proposed logical work identity consists of execution, operation, and the applicable
partition/sample identity. Camera observations identify source camera and group
frame ordinal; timestamps retain their existing meaning and are not arrival-time
join keys. Group results identify the group and frame; model operations add model
identity. Recording-wide operations have explicit coverage instead of a fictitious
frame number. This is a semantic outline, not a mandated tuple or new file schema.

Readiness should distinguish:

- Required keyed data has arrived and passed its boundary checks.
- Any declared chronological state predecessor is satisfied.
- Required collection coverage has completed successfully, where the scientific
  algorithm needs that coverage.
- Resources are available. Waiting for capacity is distinct from missing inputs.

A successful empty detection still satisfies delivery. A producer's explicit
completion/failure outcome determines whether more data can arrive; silence or
an empty queue never establishes successful completion. Save acceptance separately
checks exact expected coverage and scientific validation. These proposals carry
forward the owner's failure/completeness rules; concrete message types remain open.

### Interview round 2 — owner decisions

Optionality belongs to graph definition. Once requested and wired, an input is
required for that product. Arrival timing never silently changes output content.

Item readiness and stage completion are separate. Downstream work can start as
soon as its particular inputs are ready, without waiting for upstream stages to
finish. Successful stage completion requires all its required dependencies to
succeed and its declared coverage to be satisfied. If one camera fails midway,
previously computed triangulation does not establish stage success or authorize
accepted downstream scientific products. Continue every independently satisfiable
branch; do not turn a local failure into unconditional global cancellation.

Annotation is a terminal sink with no scientific consumers. For each camera/frame
it waits for the image and every requested overlay (including skeleton and board),
composes them, and writes in frame order. It completes on its own schedule; its
completion must not gate tracking, triangulation or other scientific work.

Complete annotation videos from successful cameras remain useful outputs. The
owner also permits partial annotation videos from failed cameras for debugging.
These must be identified as incomplete diagnostic outputs, with actual coverage
and failure reason, never presented as complete videos or accepted partial
scientific results. A retained annotated frame must still satisfy its requested
overlay dependencies; missing results must not be invented.

The earlier independent-reader suggestion is an implementation option, not an
owner-selected requirement. The implementation must prevent annotation buffers,
locks or delivery acknowledgments from imposing a hidden wait on scientific
producers. Terminal topology establishes no downstream scientific dependency;
transport and resource ownership must preserve that property with bounded memory.
Private temporary storage is permitted. Shared hardware contention remains a
measurable physical constraint, not a justification for an annotation barrier.

### Contract-test cases to implement after design review

| Scenario | Required behavior |
| --- | --- |
| All three observations for frame k arrive before camera streams finish | Triangulation for k may run once its other scientific inputs are ready |
| One camera subsequently fails | Triangulation stage cannot succeed; incomplete scientific product cannot be accepted |
| Two cameras complete after the third fails | Their independently satisfiable annotation sinks finish |
| Failed camera has fully annotated earlier frames | Retain a clearly incomplete diagnostic video where encoding permits |
| Board result arrives after skeleton result for a requested annotated frame | Annotation waits for board; scientific consumers of skeleton data do not wait for annotation |
| Annotation stalls or has no available encoder capacity | No scientific dependency waits on annotation; bounded transport/lifetime behavior is tested separately |
| Required producer succeeds with an empty detection | Delivery is satisfied; preserve missing-point semantics rather than report producer failure |

After review: specify delivery/lifetime interfaces and executable contract tests
for joins, state ordering, missingness, failure propagation and sink acceptance.
