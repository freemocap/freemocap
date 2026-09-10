---
mdx:
  format: md
plan_status: ongoing
plan_migrated: "2026-09-10"
---

# Camera geometry matching proposal

Status: 2026-09-08 — revised after workflow agreement; numerical implementation first, integration follows.

## Scope and audit findings

Match N observation sources injectively to M existing CameraModels (N <= M). An unused
calibration camera is allowed; an active source must never disappear to improve the score.
This establishes an assignment consistent with observations, not physical device identity.

Current integration points:

- `core/tasks/calibration/shared/calibration_camera_binding.py`: live exact-ID then index
  matching; no geometric validation. Exact IDs are described too strongly as trustworthy.
- `core/tasks/calibration/shared/calibration_state.py`: caches binding by calibration
  generation and live IDs/indexes, and caches subset triangulators.
- `core/reconstruction/posthoc_reconstruction.py`: calls
  `Triangulator.from_calibration_for_cameras`, which requires exact calibration IDs.
- `core/pipeline/realtime/realtime_aggregator_node.py`: publishes bindings and uses their
  inverse for per-source projections. Must consume the same accepted assignment as 3D.
- `core/tasks/triangulation/triangulator.py`: existing undistortion, batched DLT and
  distortion-aware projection. Reuse these; do not duplicate triangulation.
- `core/tasks/calibration/shared/compare_calibrations.py`: also contains a local DLT helper.
  Do not build matching on this parallel implementation; reconcile it separately when touching
  calibration health. Its existence means the Triangulator docstring's uniqueness claim is too broad.
- SkellyTracker `Observation.to_keypoints` supplies qualified point names and visibility.
  Observation image_size is (height,width); CameraModel image_size is (width,height).
  Conversion must be explicit and tested with non-square images.

A new calibration solve already knows which source supplied each camera's observations.
It must not need matching before it can solve. The common matcher applies when using loaded
geometry in realtime, posthoc mocap, or a recorded calibration validation workflow. The
posthoc calibration panel exposes the setting for applying existing geometry; computing
fresh geometry does not search permutations of a calibration that does not yet exist.

## Recommended policy and setting

One typed `CameraMatchingConfig`, serialized through existing settings/API mechanisms.
User-facing checkbox: **Automatically match cameras to calibration**, proposed default ON.
One setting definition, with live and processing configuration taking explicit snapshots.
Changing a running posthoc task's settings does not mutate its inputs.

Start with the best total, injective assignment available from explicit relationships, IDs and
structured indexes. Preserve index-based attempts; describe their evidence honestly.
ON: spot-check the initial assignment first. If usable evidence shows acceptable geometry,
keep it without a permutation search. Otherwise search alternatives on sampled observations.
OFF: do not search alternatives; still attempt reconstruction using the available assignment.
Missing or poor tracks mean insufficient evidence, not proof that the assignment is wrong.

No per-frame search. No implicit calibration solve. Never modify CameraModel IDs, intrinsics,
extrinsics or calibration files to make an assignment fit. Reprojection and camera rendering
must share the same assignment and coordinate basis as triangulation.

## Inputs and evidence

Agreed execution policy: realtime uses a rolling fitness estimate from usable observations.
One isolated bad frame never triggers search. After one unsuccessful search for a calibration/
source generation, suspend triangulation and further search until new calibration, changed
sources, or explicit retry. Missing evidence alone leaves collection pending rather than
consuming this attempt. Posthoc performs a sampled preflight and defaults to continuing with
the best available assignment and finite reconstruction outputs, carrying poor-fitness details.
A typed continue/stop policy will expose strict stopping as an option. Do not fabricate a
missing prerequisite, discard useful observations, or label a best-effort result as verified.
Permutation search never recalibrates the candidate models.

Input request contains existing camera models, ordered source labels/image sizes, matching
config and a bounded set of synchronized observations. Reuse Observation/Keypoints; the
numeric adapter joins by synchronized frame and qualified point identity, never array position.

Correspondence means the SAME physical point in different views. ChArUco corner IDs on the
same resolved board provide this. Named skeleton keypoints are usable only when the tracked
instance is unambiguous across views. Do not assume detector-local person index is a shared
identity. Mixed or unassociated instances produce insufficient evidence, not guessed matches.
The board is not mandatory and no extra detector is enabled implicitly. Square size is not
estimated by matching. Do not use skeleton fitting/anatomical plausibility to choose geometry.

Initial sampling proposal: at most 24 synchronized frames, with at most 64 shared qualified
points per source pair per frame, selected deterministically with spatial coverage. Use the
same selected data for every candidate. Split frames, not individual correlated points, into
12 search and 12 validation frames. Posthoc samples across the recording from saved observations;
live samples at most 5 multiframe observations/second into a bounded collector. Copy numeric
observations only, not images. A short recording may use fewer frames subject to evidence gates.

Missing detections do not count as errors. Use finite coordinates passing detector-specific
validity gates; do not treat visibility from different detectors as calibrated probabilities.
Balance scores per frame and source pair so dense face points cannot dominate a sparse board.

Require a connected source co-observation graph. Disconnected components cannot establish
one global assignment reliably; return insufficient evidence. No hard-coded camera count.
N=1 cannot use multiview matching and is explicitly not applicable.

## Computation: cached pair fitness, then assignment search

For a source i and candidate camera a, undistort observed pixel u using a's K and distortion
coefficients, yielding normalized x=(x,y,1). Cache these coordinates for each (i,a), once.
Require matching image geometry initially. A known resize/crop transform may be applied
explicitly; do not infer it from aspect ratio or filenames. An unexplained size/rotation
mismatch is incompatible input, not an invitation to guess intrinsics.

For each source pair (i,j) and distinct camera pair (a,b), compute a cached cost C_ij(a,b).
Use existing batched two-view DLT, with E_a=[R_a|t_a] and E_b=[R_b|t_b]. For each point:

    A = [x_i E_a[2]-E_a[0]; y_i E_a[2]-E_a[1];
         x_j E_b[2]-E_b[0]; y_j E_b[2]-E_b[1]]
    X_h = right singular vector of A with smallest singular value
    X = X_h[:3] / X_h[3]

Reject a numerically degenerate homogeneous solution or non-positive depth
(R_a X+t_a)_z or (R_b X+t_b)_z. Degenerate/behind-camera points receive the maximum
penalty; never omit them and thereby reward a bad candidate. Count these failures separately.
Near-parallel rays require a conditioning check; positive depth alone is insufficient.

Project X with existing distortion-aware project() into each original image. For image
width w,height h define resolution-normalized pixel error:

    e_i = 1000 * ||project_a(X)-u_i||_2 / sqrt(w_i^2+h_i^2)
    e_pair = sqrt((e_i^2+e_j^2)/2)
    rho(e) = min((e/tau)^2, 1)
    C_ij(a,b) = mean_over_frames(mean_over_valid_input_points(rho(e_pair)))

These units are pixels at a 1000-pixel image diagonal. Tau is a proposed noise tolerance,
not the existing normalized-coordinate triangulation threshold. Invalid geometry gets rho=1.
Candidate-independent absent observations are excluded before scoring. Per-pair coverage and
uncapped residual quantiles accompany the bounded score.

Given injective assignment p, minimize:

    J(p) = mean_over_supported_source_pairs(C_ij(p(i),p(j)))

This is a pairwise assignment problem, NOT a linear assignment problem; a Hungarian solver
alone is not correct. Build the pair table once, then deterministic branch-and-bound:

1. Assign sources with fewest compatible camera candidates first, then highest evidence degree.
2. Accumulate costs for edges whose two endpoints are assigned.
3. Lower bound = accumulated cost + independent minimum remaining cost for each other edge,
   constrained by assigned endpoints and unused cameras. Relaxing consistency between remaining
   edges makes this optimistic, hence safe for pruning.
4. Maintain best and second-best distinct complete assignments. Prune only branches whose
   lower bound cannot improve the second-best. IDs may order trials, never change costs.
5. Exact completion certifies the best and runner-up for this objective. Stop at a work budget
   with SEARCH_LIMIT, not a falsely confident winner. No arbitrary top-K shortlist acceptance.

Complexity: pair scoring O(N^2 M^2 K) small batched SVD/projection operations for K samples;
assignment worst case remains M!/(M-N)!. Do not promise polynomial runtime. Initial proposed
bounds: 250,000 expanded search nodes, chunked pair evaluation with cancellation between
chunks, one matching job per pipeline and no parallel inference-model copies. Benchmark
2,3,4,6,8,12-source cases before choosing shipping budgets. A budget limits work, not valid
camera counts. Report explored work and unresolved competitors.

Why not start with epipolar-only pruning? DLT plus projection reuses working code and also
checks depth. A later proven optimization can use epipolar residuals; an unproven approximation
must not eliminate the correct candidate. Start with a measurable correct reference search.

## Validation and acceptance

Freeze the search winner, then validate on held-out frames with all available assigned views,
using existing plain DLT (outlier rejection OFF). Camera-dropping/outlier selection would let
an incorrect assignment conceal its bad cameras. Compute per-source pixel errors, positive-depth
fraction, conditioning/usable count, and frame coverage. Also evaluate winner vs runner-up
pair scores on the validation frames. If the winner fails, do not quietly select another result.

Proposed research defaults, to be tested and agreed before becoming production thresholds:

- Each source participates in at least 6 search and 6 validation frames with >=6 corresponding
  points per qualifying frame. Pair graph must be connected on both partitions.
- At least 90% of tested points have finite, well-conditioned positive-depth reconstruction
  for each source. Initial minimum ray angle 1 degree; test sensitivity to capture volume scale.
- Per-source median reprojection error <=2 and 90th percentile <=5 normalized pixels.
- tau=5; exact search objective gap J(second)-J(best) >=0.05. Require validation gap >=0.05 too.
  These are deterministic gates, NOT probabilities or a claimed 95% confidence interval.
- If only one assignment is structurally compatible, there is no runner-up gap; all absolute
  fitness/evidence checks still apply, and report that uniqueness came from input constraints.

Return typed outcomes: MATCHED, INSUFFICIENT_EVIDENCE, AMBIGUOUS, INCOMPATIBLE,
SEARCH_LIMIT, plus explicit diagnostics. Malformed inputs/numerical programming errors raise;
expected inability to establish a mapping is an outcome. The task layer applies the configured
continue/stop policy. Poor fitness alone must not prevent best-effort posthoc output.

Important limitations: two-camera or symmetric rigs can admit equally good assignments even
with positive depth. A global rigid symmetry can preserve reprojections while changing world
orientation. More samples cannot break an exact symmetry. Matching also cannot verify absolute
metric scale from unknown point correspondences. Report ambiguity rather than claim physical
identity; an explicit assignment or independently identified reference is then necessary.

## Runtime integration and persistence

One pure numeric matcher under `core/tasks/calibration/camera_matching/`, using two-word
modules `matching_models.py`, `matching_evidence.py`, `matching_search.py` only as complexity
justifies them. This belongs beside the existing FreeMoCap geometry code, not in SkellyCam
(media ownership) or SkellyTracker (detection). No duplicate camera-model wrapper.

Use a typed result containing an injective source-to-calibration-ID map and fitness diagnostics.
CameraModels remain the existing objects. One factory resolves that map to ordered existing
models for all triangulation/projection consumers. Replace competing live/posthoc binding rules.

Realtime: collect evidence while attempting the initial binding and displaying detection/2D.
Run matching in a managed background worker, never on the camera read or rendering path.
Publish provisional fitness explicitly. Atomically install the result at a multiframe boundary; clear dependent
triangulator/reconstruction caches. Recheck only after calibration content, source set/image
geometry or explicit user action changes. Reject late results from obsolete generations.
Use rolling observation fitness to trigger one search after sustained poor results, not a
single bad frame. Exhausted searches latch until the inputs change or explicit retry.

Posthoc: consume saved/detected observations, match once before geometry-dependent stages,
then use the frozen assignment throughout. Matching must not cause detection to run twice.
An unresolved fitness check leaves observations/videos available. With continue policy, use
the available assignment and produce the downstream prerequisites that can actually be computed;
with stop policy, stop before geometry processing. A structurally absent assignment cannot be
invented. Fresh calibration publication keeps its source association directly;
subsequent application to another source set goes through this same policy.

Store the accepted association and diagnostics with the processing geometry/result description,
not measurement data in recording_info.json. Exact schema placement belongs to the upcoming
recording contract review. Until agreed, keep matching transient and recompute; never silently
rewrite a calibration TOML. Any future reuse must validate source/configuration and calibration
content, not just a path or modification time.

## Implementation sequence after agreement

1. Pure math/search tests and synthetic benchmark. No API/UI yet.
2. Replace the two binding policies with one typed assignment consumer; preserve model identity.
3. Add bounded live collector/background lifecycle and posthoc observation adapter.
4. Wire the shared checkbox, matching status, errors and result details using existing UI patterns.
5. Real app QA with permuted labels/order, calibration subsets, wrong geometry and ambiguous views.

Tests must establish recovery of seeded permutations with distortion/noise, rejection of wrong
geometry, positive-depth and degeneracy handling, ambiguous symmetric rigs, missing observations,
multiple-instance ambiguity, non-square image conventions, source subsets, arbitrary labels,
budget exhaustion and stale-job cancellation. Compare branch-and-bound with brute-force
enumeration for small cases. Hold out entire frames. Measure added realtime latency while
matching; no performance claims until measured.

## Implementation checkpoint

Numerical foundation implemented in `camera_matching`: typed configuration, fixed-assignment
fitness using the existing Triangulator, and bounded pair-cost assignment search. Search tests
compare best and runner-up with exhaustive enumeration, including extra calibration cameras,
ties and budget exhaustion. Fitness tests use distorted synthetic observations and distinguish
wrong assignments from missing detections. These helpers are not yet connected to pipelines.

Pair-cost construction and held-out validation are implemented. The initial assignment is
checked first and skips search when healthy. Candidate scoring balances errors by frame,
penalizes invalid geometry, and preserves a provisional best candidate on search-budget
exhaustion. Disconnected/insufficient evidence does not trigger search. Twenty numerical
tests pass, including permutation recovery, held-out disagreement and best-effort retention;
lint passes. No pipeline behavior or UI setting has been changed yet.

Remaining in the numerical step: detector-aware sampling/instance evidence adaptation,
outlier-contaminated/multiple-instance evidence evaluation, and timing benchmarks. Then wire
the initial-binding fast path, rolling live policy with exhausted-search latch, posthoc continuation
and shared settings. Do not treat the helper tests as end-to-end app validation.

Real-data QA fixture supplied by the user:
`C:/Users/jonma/freemocap_data/recordings/freemocap_test_data_vid_switch`.
Its synchronized video filenames have been changed. Compare inferred source-to-geometry
assignment against `freemocap_test_data` using actual video content, not renamed labels.
Check healthy initial binding, renamed inputs, recovery after ordering changes and posthoc
best-effort output. Preserve the supplied videos; this fixture is for integration QA after wiring.

Observation sampling and lifecycle helpers are implemented and tested: explicit qualified point
selection, visibility masking, synchronized frame validation, width/height conversion, bounded
live numeric window and evenly distributed recorded samples. Retry ownership rejects simultaneous
jobs, ignores obsolete calibration generations and suspends unsuccessful searches until reset.
Insufficient observations preserve the previous assignment. These helpers do not yet submit
worker jobs or alter active pipelines. Next integration must choose detector-qualified point
identities, feed the windows, dispatch managed background work and apply one accepted mapping
to triangulation, reprojection and published camera geometry. Settings and app QA remain pending.

Posthoc integration checkpoint: the mocap task now evaluates sampled observations before
triangulation and uses a source-keyed mapping of existing CameraModels. The task config accepts
`cameraMatching`; continuation defaults to CONTINUE. A missing assignment remains a missing
prerequisite, while poor fitness with an assignment can continue. The result is reported through
task progress and logs. Image reference descriptors now include `calibration_camera_id`, preserving
the source/geometry relationship without rewriting model IDs or the calibration file.

Two integration tests cover renamed/permuted sources through actual triangulation and strict
versus continue policy; seven affected observation/publication tests pass. The initial adapter
samples at most 24 frames (or twice configured minimum coverage), takes up to 64 qualified names
in detector order, and excludes frames reporting multiple root-stage bounding boxes. This does
not solve cross-view multi-person association: detector-local single-person selection can still
be inconsistent between views, so fitness remains essential. More sophisticated stage-balanced
point selection and measured search performance remain follow-up work.

Next: live managed-worker dispatch/binding installation and shared UI settings. The renamed
recording has been located but has not yet been processed through the real app with this code.

## Ready for first app QA

Live dispatch is connected: one aggregator-owned background thread, 24 numeric samples at
most five per second, no image copies. Healthy initial bindings continue while sampled fitness
runs; an unsuccessful search suspends triangulation and retries until calibration/configuration
changes. Missing evidence retains the initial binding. Late generation results are ignored and
worker exceptions propagate to pipeline failure. Applying a recovered mapping resets dependent
reconstruction/filter state. The wire and frontend schema accept the geometry match status.

Shared control component is exposed in Mocap Setup > Triangulation Settings and the realtime
3D reconstruction settings. Posthoc additionally exposes continue-on-poor-fitness. Each mode
has its own setting value using the same typed options. Fresh calibration solving is unchanged.

Verification: 27 affected backend/integration tests and frontend TypeScript check passed.
This includes actual background thread installation and full mocap annotation/publication.
A stale test filename was corrected to the existing `input.mp4.annotated.mp4` convention.

App test:
1. Restart normally; process `freemocap_test_data_vid_switch` with automatic matching ON.
   Inspect 3D and compare with the original recording. Capture the `Camera matching` log
   showing source assignments and fitness. Continue-on-poor-fitness defaults ON.
2. Repeat original recording; confirm reconstruction remains sensible.
3. Start live mocap; confirm display remains responsive through the first five seconds and
   later checks. Toggle automatic matching OFF/ON in 3D reconstruction settings; confirm the
   pipeline remains usable. If a search fails, expect 2D to continue with 3D suspended.
4. Stop/restart live mocap and refresh the UI; check lifecycle cleanup and settings display.

Remaining: real-data fitness threshold tuning, robust stage-balanced/instance-aware evidence,
large-rig performance and cancellation during pair-table construction. Background jobs have
a bounded sample size and search-node budget but pair scoring still scales with rig size;
no claim of arbitrary-rig realtime performance. User app QA is pending.

Math API reference: OpenCV calibration/projection/triangulation documentation:
https://docs.opencv.org/4.12.0/d9/d0c/group__calib3d.html
The scoring, search and acceptance policy above are our proposed design, not OpenCV guarantees.
